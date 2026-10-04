"""Disputes in the family view: show both sides instead of silently flattening them.

A challenge is an objection to a claim (or to its assertion), optionally backed by a counter-claim.
- pending_review: an objection exists, but no counter-evidence has passed independent or human review.
  The listing stays visible with the objection shown.
- contested: kernel-accepted counter-evidence is independently or human reviewed. The listing is shown as
  "Contested: see both sides", and is excluded from shared-research proposals and suggested questions.
The atlas never decides which side is right. Redacted objections are excluded by the store.
"""
import json

from ledger.policy import claim_review_status

FAMILY_PREDICATES = {"has_asset", "represented_by", "same_organization_as"}
STRONG = {"independently_reviewed", "human_reviewed"}


def dispute_index(store) -> dict[str, dict]:
    """assertion_id -> {"status": "pending_review" | "contested", "objections": [...]} for family listings."""
    out: dict[str, dict] = {}
    if not hasattr(store, "all_challenges"):  # minimal stores (tests, old snapshots) have no challenges
        return out
    for challenge in store.all_challenges():
        target = challenge["target"]
        if target.startswith("assertion:"):
            assertion = target
            rows = store.claims_where("assertion_id=? AND kernel_ok=1", (assertion,))
            predicate = rows[0]["predicate"] if rows else None
        else:
            row = store.claim(target)
            if not row or not row["kernel_ok"]:
                continue
            assertion, predicate = row["assertion_id"], row["predicate"]
        if predicate not in FAMILY_PREDICATES:
            continue
        counter, reviewed = None, False
        if challenge["counter_claim"]:
            c = store.claim(challenge["counter_claim"])
            if c and c["kernel_ok"]:
                reviews = [dict(r) for r in store.reviews_for(c["claim_id"])]
                status = claim_review_status(reviews)
                body = json.loads(c["body"])
                ev = body["evidence"][0] if body.get("evidence") else {}
                src = store.source(ev.get("source_id", "")) if ev.get("source_id") else None
                reviewed = status in STRONG
                counter = {"claim_id": c["claim_id"], "quote": ev.get("quote", "")[:600], "source": (src or {}).get("url", ""),
                           "review_status": status, "review_reason": reviews[-1]["reason"] if reviews else None}
        event = store.event(challenge["event_id"])
        entry = out.setdefault(assertion, {"status": "pending_review", "objections": []})
        entry["objections"].append({"at": (event["ts"] if event else "")[:10], "reason": challenge["reason"][:600],
                                    "counter": counter, "reviewed": reviewed})
        if reviewed:
            entry["status"] = "contested"
    return out


def contested(disputes: dict, assertion_id: str) -> bool:
    return disputes.get(assertion_id, {}).get("status") == "contested"
