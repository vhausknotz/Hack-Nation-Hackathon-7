"""Expose objections and reviewed counter-evidence without treating either as truth."""
from ledger.policy import claim_review_status


def challenge_view(store, claim_row):
    # A challenge to any accepted claim supporting the same assertion matters
    # when inspecting that assertion, not just the particular evidence instance.
    targets = {claim_row["claim_id"], claim_row["assertion_id"]}
    targets.update(r["claim_id"] for r in store.claims_where(
        "assertion_id=? AND kernel_ok=1", (claim_row["assertion_id"],)))
    challenges = []
    for target in sorted(targets):
        for row in store.challenges_for(target):
            counter_id = row["counter_claim"]
            counter = store.claim(counter_id) if counter_id else None
            status = claim_review_status([dict(r) for r in store.reviews_for(counter_id)]) if counter else "unavailable" if counter_id else "not_supplied"
            reviewed_counter = bool(counter and counter["kernel_ok"] and status in {"independently_reviewed", "human_reviewed"})
            event = store.event(row["event_id"])
            challenges.append({**dict(row), "at": event["ts"] if event else None,
                               "counter_claim_review_status": status,
                               "reviewed_counter_evidence": reviewed_counter})
    challenges.sort(key=lambda c: c["seq"])
    contested = any(c["reviewed_counter_evidence"] for c in challenges)
    return {"challenges": challenges,
            "challenge_status": "contested" if contested else "pending_review" if challenges else "none",
            "challenge_notice": "Objections are contributor statements. Contested means reviewed counter-evidence exists; inspect both claims. It does not establish which is correct."}
