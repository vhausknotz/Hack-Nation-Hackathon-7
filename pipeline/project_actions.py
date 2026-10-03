"""Family projection of the action layer: patient organizations and reusable studies per condition.

Reads contributed represented_by and has_asset claims from the ledger and keeps those the family policy
accepts (kernel-checked and supported by a reviewer). Rules:
- one entry per organization or study per condition, from its best-reviewed claim
- an organization's kind is decided once, by its newest reviewed classification, so it reads the same everywhere
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


def load_actions(conditions: dict[str, dict]) -> dict[str, dict]:
    """condition id -> {"communities": [...], "assets": [...]} (only conditions that have any)."""
    if not (ROOT / "data" / "ledger" / "ledger.db").exists():
        return {}
    sys.path.insert(0, str(ROOT))
    from ledger import policy as pol
    from ledger import sources
    from ledger.store import Store

    store = Store()
    rows = []
    for row in store.claims_where("origin = 'contributed' AND kernel_ok = 1 AND predicate IN ('represented_by', 'has_asset')"):
        reviews = [dict(r) for r in store.reviews_for(row["claim_id"])]
        status = pol.claim_review_status(reviews)
        if pol.visible("family", "contributed", status, {}, row["predicate"]):
            last = reviews[-1]
            rows.append((json.loads(row["body"]), status, last["verdict"], last["reason"]))

    def source_text(source_id: str) -> str:
        s = store.source(source_id)
        return (sources.read_text(dict(s)) or "") if s else ""

    # ---- organizations ------------------------------------------------------------------------------------
    latest: dict[str, tuple[str, str]] = {}  # org -> (created, kind): the newest reviewed classification wins
    for claim, *_ in rows:
        q = claim["assertion"]["qualifiers"]
        if claim["assertion"]["predicate"] == "represented_by" and q.get("org_type"):
            created = claim["provenance"]["created"]
            if claim["assertion"]["object"] not in latest or latest[claim["assertion"]["object"]][0] < created:
                latest[claim["assertion"]["object"]] = (created, q["org_type"])
    org_kind = {oid: kind for oid, (_, kind) in latest.items()}

    by_gene: dict[str, list[str]] = defaultdict(list)
    for cid, c in conditions.items():
        by_gene[c["gene"]["symbol"]].append(cid)

    best: dict[tuple[str, str, str], tuple] = {}
    for claim, status, verdict, reason in rows:
        a, ev = claim["assertion"], claim["evidence"]
        q = a["qualifiers"]
        if a["subject"] not in conditions:
            continue
        if a["predicate"] == "represented_by":
            if not q.get("org_type"):  # early claims without a reviewed kind are not shown
                continue
            entry = {
                "id": a["object"], "name": q.get("name", ""), "homepage": q.get("homepage", ""), "kind": org_kind[a["object"]],
                "scope": q.get("scope", "broader_group"), "quote": ev[0]["quote"][:400], "page": ev[0].get("url", ""),
                "page_read": ev[0].get("page_read", "live"), "page_date": ev[0].get("page_date", claim["provenance"]["created"][:10]),
                "review": {"status": status, "verdict": verdict, "reason": reason},
            }
            targets = by_gene[conditions[a["subject"]]["gene"]["symbol"]] if entry["scope"] == "this_gene" else [a["subject"]]
            for t in targets:
                e = entry if t == a["subject"] else {**entry, "via": a["subject"]}
                key = ("org", t, a["object"])
                rank = (STATUS_RANK.get(status, 0), verdict == "supports", t == a["subject"])
                if key not in best or best[key][0] < rank:
                    best[key] = (rank, e)
        else:
            text = source_text(ev[0]["source_id"])
            title = re.search(r"^Title: (.+)$", text, re.MULTILINE)
            phase = re.search(r"^Phases?: (.+)$", text, re.MULTILINE)
            entry = {
                "id": a["object"], "title": title.group(1).strip() if title else a["object"], "type": q.get("asset_type", ""),
                "status": q.get("status", ""), "phase": phase.group(1).strip() if phase else "",
                "restriction": next((e.get("restriction") for e in ev if e.get("restriction")), None),
                "quotes": [e["quote"][:300] for e in ev], "url": f"https://clinicaltrials.gov/study/{a['object']}",
                "review": {"status": status, "verdict": verdict, "reason": reason},
            }
            key = ("asset", a["subject"], a["object"])
            rank = (STATUS_RANK.get(status, 0), verdict == "supports", True)
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
