from ledger import sources
from ledger.canonical import find_quote
from ledger.tests.test_ledger import _roots, agent, archive_root, ledger, make_source, seizure_claim  # noqa: F401
from pipeline.freshness import latest_rechecks, page_state, recheck, superseded
from pipeline.project_history import listing_history

PAGE = b"<html><head><title>SNAP25 families</title></head><body><p>We support families affected by SNAP25 disorders.</p></body></html>"


def test_retracted_paper_supersedes_its_findings_once(ledger, archive_root, tmp_path):  # noqa: F811
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    proposed = ledger.propose(seizure_claim(src, extractor), extractor)
    assert proposed.accepted
    assert recheck(ledger, retracted=lambda pmids: set()) == {}
    assert superseded(ledger.store) == set()
    seen = []
    assert recheck(ledger, retracted=lambda pmids: seen.append(pmids) or {"33299146"}) == {"retracted": 1}
    assert seen == [["33299146"]]
    assert superseded(ledger.store) == {proposed.claim_id}
    assert recheck(ledger, retracted=lambda pmids: {"33299146"}) == {}  # recorded once
    history = listing_history(ledger.store, proposed.claim_id, seizure_claim(src, extractor))
    assert history["rechecks"][0]["result"] == "retracted" and ledger.verify_log()["ok"]


def test_organization_page_quote_is_rechecked_monthly(ledger, archive_root, tmp_path):  # noqa: F811
    from datetime import datetime, timedelta, timezone
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = sources.archive(PAGE, "https://example.org/about", "html", "organization page", True, root=archive_root)
    _roots[src.source_id] = archive_root
    ledger.add_source(src, extractor)
    quote = "We support families affected by SNAP25 disorders."
    text = sources.read_text(src, root=archive_root)
    start, end = find_quote(text, quote)
    claim = seizure_claim(make_source(ledger, extractor, archive_root), extractor)
    claim["assertion"] = {"subject": "MONDO:0014590", "predicate": "represented_by", "object": "org:example-org", "qualifiers": {}}
    claim["evidence"] = [{"type": "organization_page", "source_id": src.source_id, "quote": quote, "start": start, "end": end}]
    proposed = ledger.propose(claim, extractor)
    assert proposed.accepted, proposed.checks
    live = lambda url: (PAGE, url, "live", "2026-10-04")  # noqa: E731
    assert recheck(ledger, fetch_page=live, retracted=lambda p: set()) == {"reaffirmed": 1}
    assert recheck(ledger, fetch_page=live, retracted=lambda p: set()) == {}  # not due again for a month
    later = datetime.now(timezone.utc) + timedelta(days=31)
    changed = lambda url: (b"<html><body><p>New website.</p></body></html>", url, "live", "2026-11-04")  # noqa: E731
    assert recheck(ledger, fetch_page=changed, retracted=lambda p: set(), now=later) == {"quote_missing": 1}
    state = page_state(latest_rechecks(ledger.store)[proposed.claim_id])
    assert state == {"result": "quote_missing", "checked": later.date().isoformat()}
    assert proposed.claim_id not in superseded(ledger.store)  # a reworded page is shown with a note, not removed
