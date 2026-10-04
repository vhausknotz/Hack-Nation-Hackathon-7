from copy import deepcopy
import pytest
from atlas_mcp.cycle import Cycle, publish_stages

PLAN = {"version": 1, "max_review_attempts": 2, "allowed_contributors": ["test"],
        "approved_assets": [{"condition_id": "C1", "record_id": "NCT1"}], "publish_website": False}


class Backend:
    def __init__(self):
        self.calls = 0
        self.attested = set()
        self.fail_request = False
        self.fail_attest = False
    def drain(self): return {"processed": [], "log_verified": True}
    def candidates(self, plan): return [{"claim_id": cid} for cid in ("one", "two", "three") if cid not in self.attested]
    def review(self, candidate):
        self.calls += 1
        if self.fail_request: raise TimeoutError()
        return {"verdict": "supports", "reason": "Synthetic test"}
    def attest(self, candidate, judgment):
        if self.fail_attest: raise RuntimeError()
        self.attested.add(candidate["claim_id"])
    def publish(self, state, save, plan): pass


def run(root, backend, plan=PLAN):
    cycle = Cycle(root, plan)
    try: return cycle.run(backend)
    finally: cycle.close()


def test_lifetime_attempt_limit_survives_restart(tmp_path):
    b = Backend()
    run(tmp_path, b)
    run(tmp_path, b)
    assert b.calls == 2
    assert b.attested == {"one", "two"}


def test_ambiguous_paid_request_is_not_retried_or_refunded(tmp_path):
    b = Backend()
    b.fail_request = True
    state = run(tmp_path, b)
    assert all(a["state"] == "uncertain" for a in state["attempts"].values())
    b.fail_request = False
    run(tmp_path, b)
    assert b.calls == 2 and not b.attested


def test_crash_after_judgment_resumes_without_second_model_call(tmp_path):
    b = Backend()
    b.fail_attest = True
    with pytest.raises(RuntimeError): run(tmp_path, b)
    assert b.calls == 1
    b.fail_attest = False
    run(tmp_path, b)
    assert b.calls == 2 and b.attested == {"one", "two"}


def test_cannot_raise_budget_by_editing_plan(tmp_path):
    run(tmp_path, Backend())
    changed = {**deepcopy(PLAN), "max_review_attempts": 3}
    with pytest.raises(ValueError, match="Plan changed"): Cycle(tmp_path, changed)


def test_publication_failure_resumes_at_failed_stage():
    state = {"publication": {}}
    calls = []
    def export(): calls.append("export")
    def fail(): calls.append("fail"); raise RuntimeError()
    def deploy(): calls.append("deploy")
    with pytest.raises(RuntimeError): publish_stages(state, lambda: None, "rev1", [("export", export), ("deploy", fail)])
    publish_stages(state, lambda: None, "rev1", [("export", export), ("deploy", deploy)])
    assert calls == ["export", "fail", "deploy"]
    publish_stages(state, lambda: None, "rev1", [("export", export), ("deploy", deploy)])
    assert len(calls) == 3


def test_only_one_cycle_can_run(tmp_path):
    cycle = Cycle(tmp_path, PLAN)
    try:
        with pytest.raises(RuntimeError, match="writer"): Cycle(tmp_path, PLAN)
    finally: cycle.close()


def test_bad_ledger_stops_before_paid_review(tmp_path):
    b = Backend()
    b.drain = lambda: {"log_verified": False}
    with pytest.raises(ValueError, match="verification failed"): run(tmp_path, b)
    assert b.calls == 0
