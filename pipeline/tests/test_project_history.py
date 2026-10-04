import json

from pipeline.project_history import listing_history


def test_trail_uses_event_times_and_preserves_review_disagreement():
    class Store:
        def events_for(self, cid):
            assert cid == "selected"
            return [
                {"id": "p", "type": "claim.proposed", "ts": "2025-01-02", "payload": "{}"},
                {"id": "k", "type": "kernel.checked", "ts": "2025-01-03", "payload": '{"passed":true}'},
                *[{"id": key, "type": "review.attested", "ts": date, "payload": "{}"}
                  for key, date in [("r1", "2025-01-04"), ("r2", "2025-01-05")]],
            ]

        def reviews_for(self, _):
            return [{"event_id": key, "reviewer_kind": "model", "model": "model", "model_family": family,
                     "verdict": verdict, "reason": "Recorded reason", "private_extra": "must not export"}
                    for key, family, verdict in [("r1", "family1", "supports"), ("r2", "family2", "does_not_support")]]

        def source(self, _):
            return {"retrieved": "2024-12-31", "url": "https://example.org", "private_extra": "must not export"}

    trail = listing_history(Store(), "selected", {"provenance": {"created": "2099-01-01"},
                                                 "evidence": [{"source_id": "s"}, {"source_id": "s"}]})
    assert trail["submitted_at"] == "2025-01-02"
    assert trail["kernel_checked_at"] == "2025-01-03"
    assert trail["sources"] == [{"id": "s", "archived_at": "2024-12-31", "url": "https://example.org"}]
    assert [r["verdict"] for r in trail["reviews"]] == ["supports", "does_not_support"]
    assert [r["at"] for r in trail["reviews"]] == ["2025-01-04", "2025-01-05"]
    assert "private_extra" not in json.dumps(trail)


def test_missing_or_redacted_events_do_not_invent_checks():
    class Store:
        def events_for(self, _):
            return [{"id": "k", "type": "kernel.checked", "ts": "2025-01-03", "payload": '{"passed":false}'},
                    {"id": "r", "type": "review.attested", "ts": "2025-01-04", "payload": None}]
        def reviews_for(self, _):
            return [{"event_id": "r"}]
        def source(self, _):
            return None
    trail = listing_history(Store(), "selected", {"evidence": [{"source_id": "s"}]})
    assert trail == {"submitted_at": None, "kernel_checked_at": None, "sources": [], "reviews": []}
