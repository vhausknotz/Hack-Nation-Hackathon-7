import json

from pipeline.project_actions import load_actions


def test_new_qualified_trial_replaces_older_unrestricted_display(monkeypatch, tmp_path):
    """Import order must not erase v2 eligibility; omitted v1 studies remain visible."""
    from ledger import sources, store
    from pipeline import project_actions

    (tmp_path / "data/ledger").mkdir(parents=True)
    (tmp_path / "data/ledger/ledger.db").touch()
    monkeypatch.setattr(project_actions, "ROOT", tmp_path)

    def claim(key, study, restriction, created):
        return {"claim_id": key, "predicate": "has_asset", "body": json.dumps({
            "assertion": {"subject": "C1", "predicate": "has_asset", "object": study,
                          "qualifiers": {"asset_type": "trial", "status": "RECRUITING"}},
            "provenance": {"created": created},
            "evidence": [{"source_id": "source1", "quote": "SCN2A participants", "restriction": restriction}],
        })}

    old = claim("old", "NCT1", None, "2026-10-01")
    new = claim("new", "NCT1", "One participant only", "2026-10-02")
    kept = claim("kept", "NCT2", None, "2026-10-01")

    class FakeStore:
        def __init__(self, **_):
            pass

        def claims_where(self, _):
            return [old, new, kept]

        def reviews_for(self, key):
            return [{"reviewer_kind": "model", "model_family": "openai", "reviewer": "sol",
                     "verdict": "supports_with_qualification" if key == "new" else "supports",
                     "reason": "Eligibility checked", "seq": 20 if key == "new" else 10}]

        def source(self, _):
            return {"retrieved": "2026-10-01T00:00:00Z"}

        def close(self):
            pass

    monkeypatch.setattr(store, "Store", FakeStore)
    monkeypatch.setattr(sources, "read_text", lambda _: "Title: Test study")
    result = load_actions({"C1": {"gene": {"symbol": "SCN2A"}}})
    assets = {a["id"]: a for a in result["C1"]["assets"]}
    assert set(assets) == {"NCT1", "NCT2"}
    assert assets["NCT1"]["restriction"] == "One participant only"
    assert assets["NCT1"]["claim_id"] == "new"
    assert assets["NCT1"]["review"]["verdict"] == "supports_with_qualification"
