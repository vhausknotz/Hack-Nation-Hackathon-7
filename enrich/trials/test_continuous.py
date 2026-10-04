import json
import threading
import time

import pytest

from enrich.trials.continuous import AdaptiveGate


def test_adaptive_gate_learns_actual_prompt_size_and_backs_off_on_429():
    clock = [100.]
    gate = AdaptiveGate(64, 128, clock=lambda: clock[0])
    gate.acquire_request([{"role": "user", "content": "x"*4000}], 1200)
    for _ in range(30):
        gate.observed({"input_tokens": 1000, "output_tokens": 500, "seconds": 3})
    assert gate.snapshot(False)["rolling_actual_tpm"] == 45000
    assert gate.ratio < .30
    clock[0] += 16
    assert gate.snapshot()["target_concurrency"] > 64
    Error = type("RateLimitError", (Exception,), {})
    gate.failed(Error())
    assert gate.target < 64
    assert gate.factor < 1 and gate.cooldown > clock[0]
    clock[0] += 61
    assert gate.snapshot(False)["rolling_actual_tpm"] == 0


def test_continuous_refills_before_slowest_request_and_keeps_budget(monkeypatch, tmp_path):
    import azure.identity
    from enrich.trials import full_run as f, continuous
    monkeypatch.setattr(f, "OUT", tmp_path)
    conditions = {f"C{i}": {"id": f"C{i}"} for i in range(4)}
    monkeypatch.setattr(f, "conditions", lambda: conditions)
    monkeypatch.setattr(f.pilot, "render", lambda _: "Source")
    monkeypatch.setattr(f.pilot, "screening_excerpt", lambda *_: ("Source", []))
    monkeypatch.setattr(f.pilot, "messages_for", lambda *_: [{"role": "user", "content": "Source"}])
    monkeypatch.setattr(f, "export", lambda: None)
    monkeypatch.setattr(f.llm, "log_usage", lambda _: None)
    monkeypatch.setattr(f.llm, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(f.llm, "USAGE", tmp_path / "usage")
    monkeypatch.setattr(f.llm, "_client", None)
    monkeypatch.setattr(f, "usage", lambda: {"usd": 0., "calls": 0, "input_tokens": 0, "output_tokens": 0})
    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", lambda: None)
    monkeypatch.setattr(azure.identity, "get_bearer_token_provider", lambda *_: lambda: "test")
    class Client:
        def with_options(self, **kwargs):
            kwargs["http_client"].close()
            return self
    monkeypatch.setattr(f.llm, "client", lambda: Client())
    released = threading.Event()
    started = []
    def work(job, _):
        cid, nct = job[0]["id"], job[1]
        started.append(cid)
        if cid == "C0":
            assert released.wait(5), "Slow request blocked all subsequent work"
        elif cid == "C2":
            released.set()
        f.llm.log_usage({"usd": .0001, "input_tokens": 100, "output_tokens": 100, "seconds": .01})
        return {"condition_id": cid, "nct_id": nct}
    monkeypatch.setattr(f, "screen_one", work)
    db = f.connect()
    for i, cid in enumerate(conditions):
        nct = f"NCT{i:08}"
        db.execute("INSERT INTO studies VALUES (?,?,?)", (nct, "{}", "{}"))
        db.execute("INSERT INTO pairs(cid,nct,priority) VALUES (?,?,0)", (cid, nct))
    f.set_meta(db, "collection_complete", True)
    db.commit(); db.close()
    continuous.run(.1, initial=2, maximum=2)
    assert len(started) == 4
    db = f.connect()
    assert f.meta(db, "uncertain_reserved_usd") == pytest.approx(0)
    assert f.meta(db, "screening_usage")["usd"] == pytest.approx(.0004)
    assert f.meta(db, "screening_complete") is True
    db.close()
