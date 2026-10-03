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
