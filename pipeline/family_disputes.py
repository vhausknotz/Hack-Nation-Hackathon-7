"""Stop family publication rather than silently flatten a reviewed dispute.

The contributor-facing MCP preserves both sides. Until family listings have an
explicit dispute view, do not export contested listings as ordinary leads.
"""
from ledger.policy import claim_review_status, visible


class ContestedFamilyEvidence(ValueError):
    pass


def check_family_disputes(store):
    assertions = set()
    for challenge in store.all_challenges():
        counter = store.claim(challenge["counter_claim"]) if challenge["counter_claim"] else None
        if not counter or not counter["kernel_ok"]:
            continue
        status = claim_review_status([dict(r) for r in store.reviews_for(counter["claim_id"])])
        if status not in {"independently_reviewed", "human_reviewed"}:
            continue
        target = challenge["target"]
        if target.startswith("assertion:"):
            assertions.add(target)
        else:
            claim = store.claim(target)
            if claim and claim["kernel_ok"]:
                assertions.add(claim["assertion_id"])
    for assertion in sorted(assertions):
        for row in store.claims_where("assertion_id=? AND kernel_ok=1 AND origin='contributed'", (assertion,)):
            if row["predicate"] not in {"has_asset", "represented_by", "same_organization_as"}:
                continue
            status = claim_review_status([dict(r) for r in store.reviews_for(row["claim_id"])])
            if visible("family", "contributed", status, {}, row["predicate"]):
                raise ContestedFamilyEvidence(
                    f"Family export stopped: contested listing {row['claim_id']} ({assertion}). "
                    "Inspect both sides through MCP and implement explicit family dispute handling before publication.")
