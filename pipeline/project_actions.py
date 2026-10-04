"""Family projection of the action layer: patient organizations and reusable studies per condition.

Reads contributed represented_by and has_asset claims from the ledger and keeps those the family policy
accepts (kernel-checked and supported by a reviewer). Rules:
- one entry per organization or study per condition, from its best-reviewed claim
- an organization's kind is decided once; a reviewed organization-wide profile outranks a condition leaf page at equal trust
- an organization that serves everything caused by a gene is shown on all conditions of that gene
- every entry says how its page was read (live on a date, or a historical archive snapshot)
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_RANK = {"human_reviewed": 3, "independently_reviewed": 2, "reviewed": 1}


def asset_rank(status: str, review_seq: int, claim: dict) -> tuple:
    """Keep the latest reviewed evidence at a given trust tier, including narrower eligibility.

    A qualified newer claim must not lose to an older unrestricted claim. This selects
    a display entry only: it never retracts earlier claims or omitted v1 candidates.
    """
    return (STATUS_RANK.get(status, 0), review_seq, claim["provenance"]["created"])


def organization_aliases(store) -> dict[str, tuple[str, list[str]]]:
    """Resolve only reviewed, unambiguous identity claims. Cycles remain separate.

    A later rejection of the same assertion disables its older support. Original
    claims/IDs remain in the ledger; this changes only the display projection.
    """
    from ledger import policy
    latest = {}
    for row in store.claims_where("origin='contributed' AND kernel_ok=1 AND predicate='same_organization_as'"):
        if row["predicate"] != "same_organization_as":
            continue
        reviews = [dict(r) for r in store.reviews_for(row["claim_id"])]
        if not reviews:
            continue
        claim = json.loads(row["body"])
        a = claim["assertion"]
        key = (a["subject"], a["object"])
        rank = reviews[-1]["seq"]
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, policy.claim_review_status(reviews), row["claim_id"])
    links = defaultdict(list)
    for (alias, target), (_, status, cid) in latest.items():
        if status in STATUS_RANK and alias != target:
            links[alias].append((target, cid))
    result = {}
    for alias in links:
        target, seen, claims = alias, set(), []
        while target in links and len(links[target]) == 1 and target not in seen:
            seen.add(target)
            target, cid = links[target][0]
            claims.append(cid)
        if target not in links:
            result[alias] = (target, claims)
    return result


def load_actions(conditions: dict[str, dict]) -> dict[str, dict]:
    """condition id -> {"communities": [...], "assets": [...]} (only conditions that have any)."""
    if not (ROOT / "data" / "ledger" / "ledger.db").exists():
        return {}
    sys.path.insert(0, str(ROOT))
    from ledger import policy as pol
    from ledger import sources
    from ledger.store import Store

    store = Store(readonly=True)
    aliases = organization_aliases(store)
    rows = []
    asset_latest = {}
    for row in store.claims_where("origin = 'contributed' AND kernel_ok = 1 AND predicate IN ('represented_by', 'has_asset')"):
        reviews = [dict(r) for r in store.reviews_for(row["claim_id"])]
        status = pol.claim_review_status(reviews)
        if row["predicate"] == "has_asset" and reviews:
            claim = json.loads(row["body"])
            a = claim["assertion"]
            trust = 3 if any(r["reviewer_kind"] == "human" for r in reviews) else min(2, len({pol.family_key(r["model_family"]) or r["reviewer"] for r in reviews}))
            rank = (trust, reviews[-1]["seq"], claim["provenance"]["created"])
            key = (a["subject"], a["object"])
            if key not in asset_latest or asset_latest[key][0] < rank:
                asset_latest[key] = (rank, row["claim_id"])
        if pol.visible("family", "contributed", status, {}, row["predicate"]):
            last = reviews[-1]
            rows.append((json.loads(row["body"]), status, last["verdict"], last["reason"], last["seq"], row["claim_id"]))

    def source_text(source_id: str) -> str:
        s = store.source(source_id)
        return (sources.read_text(dict(s)) or "") if s else ""

    # ---- organizations ------------------------------------------------------------------------------------
    latest = {}  # stronger review, then explicit organization profile, then recency
    for claim, status, *_ in rows:
        q = claim["assertion"]["qualifiers"]
        if claim["assertion"]["predicate"] == "represented_by" and q.get("org_type"):
            created = claim["provenance"]["created"]
            profile = next((e for e in claim["evidence"] if e.get("supports") == "organization_kind"), None)
            rank = (STATUS_RANK.get(status, 0), profile is not None, created)
            if claim["assertion"]["object"] not in latest or latest[claim["assertion"]["object"]][0] < rank:
                latest[claim["assertion"]["object"]] = (rank, q["org_type"], profile)
    org_kind = {oid: kind for oid, (_, kind, _) in latest.items()}

    by_gene: dict[str, list[str]] = defaultdict(list)
    for cid, c in conditions.items():
        by_gene[c["gene"]["symbol"]].append(cid)

    best: dict[tuple[str, str, str], tuple] = {}
    for claim, status, verdict, reason, review_seq, claim_id in rows:
        a, ev = claim["assertion"], claim["evidence"]
        q = a["qualifiers"]
        if a["subject"] not in conditions:
            continue
        if a["predicate"] == "represented_by":
            if not q.get("org_type"):  # early claims without a reviewed kind are not shown
                continue
            entry = {
                "id": a["object"], "name": q.get("name", ""), "homepage": q.get("homepage", ""), "kind": org_kind[a["object"]],
                "scope": q.get("scope", "broader_group"), "quote": ev[0]["quote"], "page": ev[0].get("url", ""),
                "page_read": ev[0].get("page_read", "live"), "page_date": ev[0].get("page_date", claim["provenance"]["created"][:10]),
                "claim_id": claim_id,
                "kind_source": latest[a["object"]][2],
                "review": {"status": status, "verdict": verdict, "reason": reason},
            }
            targets = by_gene[conditions[a["subject"]]["gene"]["symbol"]] if entry["scope"] == "this_gene" else [a["subject"]]
            for t in targets:
                e = entry if t == a["subject"] else {**entry, "via": a["subject"]}
                canonical, alias_claims = aliases.get(a["object"], (a["object"], []))
                if alias_claims:
                    e = {**e, "id": canonical, "original_organization_id": a["object"], "identity_claim_ids": alias_claims}
                key = ("org", t, canonical)
                # Corrections must replace an older quote at equal trust, including
                # newer qualified evidence. A cached first claim must not win forever.
                rank = (STATUS_RANK.get(status, 0), a["object"] == canonical, review_seq, claim["provenance"]["created"], t == a["subject"])
                if key not in best or best[key][0] < rank:
                    best[key] = (rank, e)
        else:
            if asset_latest[(a["subject"], a["object"])][1] != claim_id:
                continue  # a newer rejection must not silently revive an older accepted display
            text = source_text(ev[0]["source_id"])
            title = re.search(r"^Title: (.+)$", text, re.MULTILINE)
            phase = re.search(r"^Phases?: (.+)$", text, re.MULTILINE)
            entry = {
                "id": a["object"], "title": title.group(1).strip() if title else a["object"], "type": q.get("asset_type", ""),
                "status": q.get("status", ""), "phase": phase.group(1).strip() if phase else "",
                "restriction": next((e.get("restriction") for e in ev if e.get("restriction")), None),
                "quotes": [e["quote"] for e in ev], "url": f"https://clinicaltrials.gov/study/{a['object']}",
                "claim_id": claim_id,
                "source_date": ((store.source(ev[0]["source_id"]) or {}).get("retrieved", ""))[:10],
                "review": {"status": status, "verdict": verdict, "reason": reason},
            }
            key = ("asset", a["subject"], a["object"])
            rank = asset_rank(status, review_seq, claim)
            if key not in best or best[key][0] < rank:
                best[key] = (rank, entry)
    store.close()

    out: dict[str, dict] = defaultdict(lambda: {"communities": [], "assets": []})
    for (kind, cid, _), (_, entry) in best.items():
        out[cid]["communities" if kind == "org" else "assets"].append(entry)
    kind_order = {"patient_organization": 0, "research_program": 1, "professional_network": 2, "information_service": 3, "company": 4}
    scope_order = {"this_condition": 0, "this_gene": 1, "broader_group": 2}
    open_status = {"RECRUITING": 0, "ENROLLING_BY_INVITATION": 1, "NOT_YET_RECRUITING": 2, "ACTIVE_NOT_RECRUITING": 3}
    for v in out.values():
        v["communities"].sort(key=lambda e: (kind_order.get(e["kind"], 9), scope_order.get(e["scope"], 9), "via" in e, e["name"]))
        v["assets"].sort(key=lambda e: (e["review"]["verdict"] != "supports", open_status.get(e["status"], 5), e["type"] == "trial", e["id"]))
    return dict(out)
