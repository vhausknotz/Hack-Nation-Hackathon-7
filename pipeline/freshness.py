"""Evidence freshness: recheck the sources behind accepted findings and record each result in the signed ledger.

    retraction         PubMed marks a cited paper as retracted -> "retracted": the finding is superseded and leaves
                       the map on the next rebuild (build_graph, project_actions skip it).
    organization page  the quoted text is still on the live page -> "reaffirmed"; gone -> "quote_missing";
                       live page unreadable -> "unreachable". Listings show the latest result with its date.

Each recheck is a ledger event: type "evidence.rechecked", target = claim id, payload
{"check": "retraction" | "page", "result": ..., "checked": ISO date, "detail": ...}, signed by agent:atlas-freshness.
The engine runs this in its 6-hourly freshness pass (it is the single ledger writer); pages are rechecked about
monthly, a bounded number per pass. No language model is used.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timezone

import requests

RECHECK_PAGE_DAYS = 30
PAGES_PER_PASS = 15
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PMID = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")


def latest_rechecks(store) -> dict[str, dict]:
    """claim id -> {"retraction": payload, "page": payload} (latest of each check)."""
    out: dict[str, dict] = defaultdict(dict)
    if not hasattr(store, "db"):  # read models without an event log (test doubles) have no rechecks
        return {}
    for target, payload in store.db.execute("SELECT target, payload FROM events WHERE type = 'evidence.rechecked' ORDER BY seq"):
        if payload:
            p = json.loads(payload)
            out[target][p["check"]] = p
    return dict(out)


def superseded(store) -> set[str]:
    """Claims whose cited paper has been retracted."""
    return {cid for cid, checks in latest_rechecks(store).items() if checks.get("retraction", {}).get("result") == "retracted"}


def page_state(checks: dict | None) -> dict | None:
    """What a listing shows about its latest page recheck."""
    page = (checks or {}).get("page")
    return {"result": page["result"], "checked": page["checked"]} if page else None


def pubmed_retracted(pmids: list[str]) -> set[str]:
    out = set()
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i + 200]
        r = requests.post(EUTILS, data={"db": "pubmed", "id": ",".join(batch), "retmode": "json", "tool": "rare-disease-atlas"}, timeout=60)
        r.raise_for_status()
        result = r.json().get("result", {})
        for pmid in batch:
            if "Retracted Publication" in (result.get(pmid) or {}).get("pubtype", []):
                out.add(pmid)
    return out


def recheck(ledger, fetch_page=None, retracted=pubmed_retracted, now=None, pages_per_pass=PAGES_PER_PASS):
    """One bounded freshness pass. Returns counts by result."""
    from ledger import identity
    from ledger.canonical import canonical_text, find_quote
    from ledger.sources import extract_text
    if fetch_page is None:
        from atlas_mcp.page_fetch import fetch_public_page as fetch_page
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    store = ledger.store
    signer = identity.load_or_create("agent:atlas-freshness", ledger.keys_dir)
    ledger.register(signer, kind="agent", manifest={"role": "freshness-checker", "checks": ["pubmed retraction", "organization page quote"],
                                                    "model": None, "version": "freshness@1"})
    latest = latest_rechecks(store)
    counts: dict[str, int] = defaultdict(int)
    by_pmid, pages = defaultdict(list), []
    for row in store.claims_where("origin = 'contributed' AND kernel_ok = 1"):
        body = json.loads(row["body"])
        for e in body.get("evidence", []):
            src = store.source(e.get("source_id", "")) if e.get("source_id") else None
            url = (src or {}).get("url", "")
            if m := PMID.search(url):
                by_pmid[m.group(1)].append(row["claim_id"])
            elif row["predicate"] == "represented_by" and url and "clinicaltrials.gov" not in url and e.get("quote") and e.get("supports") != "organization_kind":
                pages.append((row["claim_id"], url.split("web.archive.org/web/", 1)[-1].split("/", 1)[-1] if "web.archive.org/web/" in url else url, e["quote"]))
    for pmid in retracted(sorted(by_pmid)) if by_pmid else set():
        for cid in by_pmid[pmid]:
            if latest.get(cid, {}).get("retraction", {}).get("result") != "retracted":
                ledger._append(signer, "evidence.rechecked", cid, {"check": "retraction", "result": "retracted", "checked": today,
                                                                   "detail": f"PubMed lists PMID {pmid} as a retracted publication"})
                counts["retracted"] += 1

    def age(cid):
        last = latest.get(cid, {}).get("page", {}).get("checked")
        return (now.date() - datetime.fromisoformat(last).date()).days if last else 10_000
    due = sorted({cid: (cid, url, quote) for cid, url, quote in pages if age(cid) >= RECHECK_PAGE_DAYS}.values(), key=lambda p: -age(p[0]))
    for cid, url, quote in due[:pages_per_pass]:
        try:
            raw, read_from, mode, date = fetch_page(url)
            if mode != "live":
                result, detail = "unreachable", f"live page could not be read; latest archived copy is from {date}"
            else:
                _, text = extract_text(raw, "html")
                found = find_quote(canonical_text(text), quote)
                result, detail = ("reaffirmed", "quoted text is still on the page") if found else ("quote_missing", "quoted text is no longer on the page")
        except (ValueError, requests.RequestException) as error:
            result, detail = "unreachable", str(error)[:200]
        ledger._append(signer, "evidence.rechecked", cid, {"check": "page", "result": result, "checked": today, "detail": detail, "url": url})
        counts[result] += 1
    ledger.store.commit()
    return dict(counts)
