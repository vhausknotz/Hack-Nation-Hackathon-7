from copy import deepcopy
from pipeline.project_collaboration import shared_research


def fixture():
    conditions = {cid: {"name": cid, "gene": {"symbol": gene}} for cid, gene in
                  [("A", "SNAP25"), ("B", "STXBP1"), ("C", "SYNGAP1"), ("D", "SNAP25")]}
    asset = {"id": "NCT1", "type": "registry", "claim_id": "claim:A", "restriction": "Age over 18",
             "review": {"status": "reviewed", "verdict": "supports_with_qualification"}}
    actions = {cid: {"assets": [{**deepcopy(asset), "claim_id": "claim:"+cid}], "communities": []}
               for cid in conditions}
    actions["B"]["assets"][0]["restriction"] = "Residents of France"
    return conditions, actions, {"A": {"neighbors": [{"id": "B"}]}}


def test_shared_record_preserves_each_eligibility_and_claim_without_same_gene_route():
    conditions, actions, neighbors = fixture()
    before = deepcopy(actions)
    routes = shared_research(conditions, actions, neighbors)["A"]
    assert [r["partner"]["id"] for r in routes] == ["B", "C"]
    assert routes[0]["partner_asset"]["claim_id"] == "claim:B"
    assert routes[0]["partner_asset"]["restriction"] == "Residents of France"
    assert routes[0]["is_computed_neighbor"] is True
    assert routes[1]["is_computed_neighbor"] is False
    assert actions == before


def test_no_inherited_eligibility_rejected_or_therapeutic_routes():
    conditions, actions, neighbors = fixture()
    actions["A"]["assets"] = []
    assert "A" not in shared_research(conditions, actions, neighbors)
    for verdict in ("does_not_support", "out_of_scope"):
        conditions, actions, neighbors = fixture()
        actions["B"]["assets"][0]["review"]["verdict"] = verdict
        assert all(r["partner"]["id"] != "B" for r in shared_research(conditions, actions, neighbors)["A"])
    for kind in ("trial", "therapy_program"):
        conditions, actions, neighbors = fixture()
        for action in actions.values():
            action["assets"][0]["type"] = kind
        assert shared_research(conditions, actions, neighbors) == {}


def test_type_disagreement_does_not_become_collaboration_and_limit_is_stable():
    conditions, actions, neighbors = fixture()
    actions["B"]["assets"][0]["type"] = "biomarker"
    routes = shared_research(conditions, actions, neighbors, limit=1)["A"]
    assert [r["partner"]["id"] for r in routes] == ["C"]
