"""Contributor track records from the ledger: what each contributor submitted, what passed, what reviewers decided.

Reputation is earned from outcomes, never declared. A contributor's level comes from how its quote-checked findings
fared in review (accepted vs rejected); a reviewer's agreement rate compares each of its verdicts with the other
reviews of the same claim. The engine publishes the records (live/contributors.json, public) and scales each MCP
contributor's daily submission limit with its level. Suspension is a separate, manual operator decision
(tools/moderate.py); it stops new work and leaves past findings in the record.
"""
from collections import defaultdict

from ledger.policy import SUPPORTING, claim_review_status

ACCEPTED = {"reviewed", "independently_reviewed", "human_reviewed"}
QUOTA_FACTOR = {"new": 1.0, "mixed": 1.0, "reliable": 2.0, "unreliable": 0.25}


def level(accepted: int, rejected: int) -> str:
    judged = accepted + rejected
    if judged < 5:
        return "new"
    rate = accepted / judged
    if judged >= 10 and rate >= 0.8:
        return "reliable"
    return "unreliable" if rate < 0.5 else "mixed"


def earned_quota(base: int, lvl: str) -> int:
    return max(5, round(base * QUOTA_FACTOR[lvl]))


def agrees(verdict: str, outcome: str) -> bool | None:
    if outcome in ACCEPTED:
        return verdict in SUPPORTING
    if outcome == "rejected":
        return verdict not in SUPPORTING
    return None  # disagreement or nothing to compare with


def records(claims, reviews, challenges, when, label, condition_name, recent_per=10):
    """claims/reviews/challenges: ledger rows as dicts. when(seq) -> ISO time; label(claim row) -> words."""
    by_claim = defaultdict(list)
    for r in sorted(reviews, key=lambda r: r["seq"]):
        by_claim[r["claim_id"]].append(dict(r))
    blank = lambda: {"submitted": 0, "quote_failed": 0, "accepted": 0, "rejected": 0, "pending": 0, "disputed": 0,  # noqa: E731
                     "challenged": 0, "reviews_given": 0, "reviews_compared": 0, "reviews_agreed": 0, "challenges_made": 0, "recent": []}
    out = defaultdict(blank)
    contested = {c["target"] for c in challenges}
    for c in sorted(claims, key=lambda c: c["created_seq"] or 0, reverse=True):
        if c["origin"] != "contributed":
            continue
        rec = out[c["contributor"]]
        rec["submitted"] += 1
        if not c["kernel_ok"]:
            rec["quote_failed"] += 1
            status = "quote_check_failed"
        else:
            status = claim_review_status(by_claim[c["claim_id"]])
            if status in ACCEPTED:
                rec["accepted"] += 1
            elif status == "rejected":
                rec["rejected"] += 1
            elif status == "review_disagreement":
                rec["disputed"] += 1
            else:
                rec["pending"] += 1
        if c["claim_id"] in contested or c["assertion_id"] in contested:
            rec["challenged"] += 1
        if len(rec["recent"]) < recent_per:
            rec["recent"].append({"claim_id": c["claim_id"], "condition_id": c["subject"], "condition": condition_name(c["subject"]),
                                  "predicate": c["predicate"], "label": label(c), "status": status,
                                  "at": when(c["created_seq"])})
    for rows in by_claim.values():
        for r in rows:
            rec = out[r["reviewer"]]
            rec["reviews_given"] += 1
            others = [x for x in rows if x["reviewer"] != r["reviewer"]]
            verdict = agrees(r["verdict"], claim_review_status(others)) if others else None
            if verdict is not None:
                rec["reviews_compared"] += 1
                rec["reviews_agreed"] += verdict
    for ch in challenges:
        out[ch["challenger"]]["challenges_made"] += 1
    for rec in out.values():
        rec["level"] = level(rec["accepted"], rec["rejected"])
        rec["review_agreement"] = round(rec["reviews_agreed"] / rec["reviews_compared"], 2) if rec["reviews_compared"] >= 3 else None
    return dict(out)
