import json
from copy import deepcopy

import pytest

from agents import communities as c


def test_cached_claim_reuses_original_timestamp():
    old = {"assertion": {"subject": "C1", "predicate": "represented_by", "object": "org:test"},
           "evidence": [{"source_id": "one", "quote": "Families with C1"}], "provenance": {"prompt": "v1", "created": "before"}}
    class Store:
        def claims_where(self, *_):
            return [{"body": json.dumps(old)}]
    class Ledger:
        store = Store()
    fresh = deepcopy(old)
    fresh["provenance"]["created"] = "after"
    assert c.reuse_claim(Ledger(), fresh) == old
    fresh["evidence"][0]["source_id"] = "two"
    assert c.reuse_claim(Ledger(), fresh) == fresh


def test_condition_failure_is_checkpointed_and_only_failure_retried(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "CAMPAIGNS", tmp_path)
    monkeypatch.setattr(c, "load_conditions", lambda: {cid: {"id": cid, "name": cid} for cid in ("C1", "C2")})
    monkeypatch.setattr(c, "nearest_relatives", lambda *_: [])
    monkeypatch.setattr(c.llm, "usage_summary", lambda: {})
    monkeypatch.setattr(c.identity, "load_or_create", lambda *_: None)
    class FakeLedger:
        store = type("Store", (), {"close": lambda self: None})()
        def register(self, *_, **__): return None
        def publish_tree_head(self): return {"size": 0, "root": "test"}
        def verify_log(self): return {"ok": True}
    monkeypatch.setattr(c, "Ledger", FakeLedger)
    calls = []
    def first(condition, *_):
        calls.append(condition["id"])
        if condition["id"] == "C1": raise RuntimeError("network failure")
        return {"status": "complete"}
    monkeypatch.setattr(c, "scout_condition", first)
    with pytest.raises(RuntimeError, match="incomplete"):
        c.main(["resume-test", "C1", "C2"])
    receipt = json.loads((tmp_path / "resume-test.json").read_text())
    assert receipt["conditions"]["C1"]["status"] == "error"
    assert receipt["conditions"]["C2"]["status"] == "complete"
    assert calls == ["C1", "C2"]
    calls.clear()
    def second(condition, *_):
        calls.append(condition["id"])
        return {"status": "complete"}
    monkeypatch.setattr(c, "scout_condition", second)
    c.main(["resume-test", "C1", "C2"])
    assert calls == ["C1"]
    assert json.loads((tmp_path / "resume-test.json").read_text())["complete"] is True
