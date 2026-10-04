import json

from pipeline.project_actions import organization_aliases


def test_alias_resolution_preserves_ambiguity_cycles_and_rejections():
    entries = [
        ("a", "b", "supports"), ("b", "c", "supports"),
        ("d", "e", "supports"), ("e", "d", "supports"),
        ("f", "g", "supports"), ("f", "h", "supports"),
        ("i", "j", "supports"), ("i", "j", "does_not_support"),
    ]
    class Store:
        def claims_where(self, _):
            return [{"claim_id": str(i), "predicate": "same_organization_as", "body": json.dumps({
                "assertion": {"subject": a, "object": b}})} for i, (a, b, _) in enumerate(entries)]
        def reviews_for(self, cid):
            i = int(cid)
            return [{"seq": i, "reviewer_kind": "model", "model_family": "family", "reviewer": "r", "verdict": entries[i][2]}]
    assert organization_aliases(Store()) == {"a": ("c", ["0", "1"]), "b": ("c", ["1"])}
