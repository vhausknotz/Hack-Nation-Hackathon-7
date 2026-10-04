import pytest

from enrich.trials.full_run import NameIndex, reserve_usd, token_bound, single_run


def test_local_index_handles_aliases_punctuation_and_gene_boundaries():
    index = NameIndex([{"id": "C1", "gene": "SYT1", "name": "Baker-Gordon syndrome", "disease_name": "Baker-Gordon syndrome", "also_known_as": ["epilepsy"]},
                       {"id": "C2", "gene": "STXBP1", "name": "STXBP1-related disorder", "disease_name": "STXBP1 disorder", "also_known_as": []}])
    assert index.match("Participants with Baker Gordon syndrome.") == {"C1"}
    assert index.match("SYT10 or STXBP2 mutations and epilepsy") == set()
    assert index.match("STXBP1, SYT1") == {"C1", "C2"}


def test_reservation_covers_both_attempts_and_non_ascii_input():
    messages = [{"role": "user", "content": "é" * 1000}]
    bound = token_bound(messages)
    assert bound >= 2000
    assert reserve_usd(messages) >= (bound * 2 * .1 + 5296 * .5) / 1e6


def test_second_screener_cannot_share_budget(monkeypatch, tmp_path):
    from enrich.trials import full_run
    monkeypatch.setattr(full_run, "OUT", tmp_path)
    with single_run("screen"):
        with pytest.raises(OSError):
            with single_run("screen"):
                pass


def test_timeout_recovery_preserves_reservation_and_budget(monkeypatch, tmp_path):
    import json
    import httpx
    import azure.identity
    from openai import APITimeoutError
    from enrich.trials import full_run as f

    monkeypatch.setattr(f, "OUT", tmp_path)
    monkeypatch.setattr(f, "conditions", lambda: {"C1": {"id": "C1"}})
    monkeypatch.setattr(f.pilot, "render", lambda _: "Source text")
    monkeypatch.setattr(f.pilot, "screening_excerpt", lambda *_: ("Source text", []))
    monkeypatch.setattr(f.pilot, "messages_for", lambda *_: [{"role": "user", "content": "Source text"}])
    monkeypatch.setattr(f, "export", lambda: None)
    monkeypatch.setattr(f.time, "sleep", lambda _: None)
    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", lambda: None)
    monkeypatch.setattr(azure.identity, "get_bearer_token_provider", lambda *_: lambda: "test-token")
    class Client:
        def with_options(self, **_):
            return self
    monkeypatch.setattr(f.llm, "client", lambda: Client())
    monkeypatch.setattr(f.llm, "_client", None)
    monkeypatch.setattr(f.llm, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(f.llm, "USAGE", tmp_path / "usage")
    monkeypatch.setattr(f, "usage", lambda: {"usd": 0, "calls": 0})
    calls = []
    def work(*_):
        calls.append(1)
        if len(calls) == 1:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.org"))
        return {"condition_id": "C1", "nct_id": "NCT00000001"}
    monkeypatch.setattr(f, "screen_one", work)
    db = f.connect()
    db.execute("INSERT INTO studies VALUES (?,?,?)", ("NCT00000001", json.dumps({}), "{}"))
    db.execute("INSERT INTO pairs(cid,nct,priority) VALUES (?,?,?)", ("C1", "NCT00000001", 0))
    db.commit(); db.close()
    bound = reserve_usd([{"role": "user", "content": "Source text"}])
    # Enough for the first uncertain attempt, but not a second reserved wave.
    f.screen(bound * 1.5, 1, max_pairs=1)
    assert len(calls) == 1
    db = f.connect()
    assert f.meta(db, "stop_reason") == "budget_cap"
    assert f.meta(db, "uncertain_reserved_usd") == pytest.approx(bound)
    db.close()
    # A larger total cap permits recovery but does not erase the first reservation.
    f.screen(bound * 3, 1, max_pairs=1)
    db = f.connect()
    assert len(calls) == 2
    assert f.meta(db, "uncertain_reserved_usd") == pytest.approx(bound)
    assert db.execute("SELECT decision FROM pairs").fetchone()[0] is not None
    db.close()
