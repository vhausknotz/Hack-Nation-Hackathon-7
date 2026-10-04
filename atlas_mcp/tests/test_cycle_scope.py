from tools.run_contribution_cycle import approved


def test_public_contribution_cannot_spend_outside_operator_allowlist():
    plan = {"allowed_contributors": ["agent:approved"], "approved_assets": [{"condition_id": "C1", "record_id": "NCT1"}]}
    claim = {"assertion": {"subject": "C1", "predicate": "has_asset", "object": "NCT1"},
             "provenance": {"intake_submission": "submission:test"}}
    assert approved({"contributor": "agent:approved"}, claim, plan, {"C1": {}})
    assert not approved({"contributor": "agent:other"}, claim, plan, {"C1": {}})
    assert not approved({"contributor": "agent:approved"}, claim, plan, {})
    claim["assertion"]["object"] = "NCT2"
    assert not approved({"contributor": "agent:approved"}, claim, plan, {"C1": {}})
    claim["assertion"]["object"] = "NCT1"
    claim["provenance"] = {}
    assert not approved({"contributor": "agent:approved"}, claim, plan, {"C1": {}})
