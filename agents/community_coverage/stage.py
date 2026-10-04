"""Turn a hand-researched spec into an importable candidate package, without touching the production ledger.

    python -m agents.community_coverage.stage                     # fetch, archive, locate quotes, write the package
    python -m agents.community_coverage.stage --verify            # recheck hashes and offsets from the local archive

Input: data/community_candidates/coverage-v1/spec.json (conditions investigated, organizations, URLs, chosen quotes,
why each was chosen, and negative findings). Output, next to it:
- candidates.jsonl   one represented_by claim body per candidate (assertion + evidence with offsets), plus metadata
- retrievals.jsonl   every page read or attempted: requested URL, redirects, final URL, UTC time, status, failure
- manifest.json      candidate -> source files, source -> archive paths and hashes, conditions -> outcome
- archive/           raw bytes and canonical text (ledger.sources layout); local only, not committed

A quote is chosen by a person/agent reading the page, but its offsets are located mechanically in the canonical
text (ledger.canonical.find_quote) and re-checked exactly as the kernel does. A quote that is not found verbatim
stops the candidate; it is recorded as a failure, never repaired by hand.
"""

import json
import sys
from pathlib import Path

from ledger import sources
from ledger.canonical import canonical_quote, find_quote, sha256
from ledger.kernel import MAX_QUOTE

from .fetch import fetch_and_archive

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "data" / "community_candidates" / "coverage-v1"
ARCHIVE = PACKAGE / "archive"
KINDS = {"patient_organization", "research_program", "information_service", "professional_network", "company"}
SCOPES = {"this_condition", "this_gene", "broader_group"}
CONTRIBUTOR = "agent:coverage-research-claude"  # proposed signer; the lead decides the enrolled identity at import


def check_offsets(text: str, start: int, end: int, quote: str) -> str | None:
    """The kernel's own quote rule, returning a reason when it fails."""
    if not (0 <= start < end <= len(text)):
        return "offsets out of range"
    if len(quote) > MAX_QUOTE:
        return f"quote longer than {MAX_QUOTE} characters"
    if canonical_quote(text[start:end]) != canonical_quote(quote):
        return "quote does not appear verbatim at the stated offsets"
    return None


def source_files(source: dict) -> dict:
    raw = ARCHIVE / "raw" / f"{source['raw_hash'].split(':')[1]}.bin"
    text = ARCHIVE / "text" / f"{source['text_hash'].split(':')[1]}.txt"
    return {"raw": raw.relative_to(PACKAGE).as_posix(), "text": text.relative_to(PACKAGE).as_posix()}


def stage(spec: dict) -> dict:
    retrievals: dict[str, dict] = {}

    def read(url: str) -> dict:
        if url not in retrievals:
            retrievals[url] = fetch_and_archive(url, ARCHIVE).to_dict()
        return retrievals[url]

    candidates, failures, outcomes = [], [], {}
    for cond in spec["conditions"]:
        staged = 0
        for org in cond.get("candidates", []):
            assert org["org_type"] in KINDS and org["scope"] in SCOPES, org
            evidence, problem = [], None
            for ev in org["evidence"]:
                got = read(ev["url"])
                if not got["ok"]:
                    problem = f"{ev['url']}: {got['failure']}"
                    break
                src = got["source"]
                text = sources.read_text(src, root=ARCHIVE) or ""
                span = find_quote(text, ev["quote"])
                if span is None:
                    problem = f"{ev['url']}: chosen quote not found verbatim in canonical text"
                    break
                start, end = span
                quote = text[start:end]
                if (why := check_offsets(text, start, end, quote)) is not None:
                    problem = f"{ev['url']}: {why}"
                    break
                evidence.append({"type": "organization_page", "source_id": src["source_id"], "quote": quote, "start": start, "end": end,
                                 "url": src["url"], "page_read": "live", "page_date": got["retrieved"][:10],
                                 "supports": ev.get("supports", "serves_condition")})
            if problem:
                failures.append({"condition": cond["id"], "organization": org["name"], "failure": problem})
                continue
            staged += 1
            candidates.append({
                "candidate_id": f"{cond['id']}|{org['org_id']}",
                "claim": {
                    "assertion": {"subject": cond["id"], "predicate": "represented_by", "object": org["org_id"],
                                  "qualifiers": {"org_type": org["org_type"], "scope": org["scope"], "name": org["name"], "homepage": org["homepage"]}},
                    "evidence": evidence,
                    "provenance_proposal": {"contributor": CONTRIBUTOR, "agent": "coverage-research", "model": spec["researcher_model"],
                                            "discovery": "web_search_and_manual_reading", "quote_selection": "manual; offsets located mechanically",
                                            "campaign": "community-coverage-v1"},
                },
                "condition_name": cond["name"],
                "rationale": org["rationale"],
                "caveats": org.get("caveats", []),
                "status": "proposal: not kernel-checked in the production ledger, not reviewed",
            })
        outcomes[cond["id"]] = {"name": cond["name"], "gene": cond["gene"], "why_chosen": cond["why"], "candidates_staged": staged,
                                "outcome": "candidates" if staged else "unresolved_gap", "notes": cond.get("notes", ""),
                                "searched": cond.get("searched", []), "rejected": cond.get("rejected", [])}

    used = {e["source_id"] for c in candidates for e in c["claim"]["evidence"]}
    manifest = {
        "package": "community-coverage-v1",
        "archive_root": ARCHIVE.relative_to(PACKAGE).as_posix() + "/",
        "redistribution": "Archived pages are organization websites kept for verification only (redistributable=false). "
                          "Only metadata and short quotes are committed; raw/ and text/ stay local.",
        "conditions": outcomes,
        "candidates": {c["candidate_id"]: [e["source_id"] for e in c["claim"]["evidence"]] for c in candidates},
        "sources": {r["source"]["source_id"]: {"source": r["source"], "files": source_files(r["source"]), "requested_url": url}
                    for url, r in retrievals.items() if r["ok"] and r["source"]["source_id"] in used},
        "failures": failures,
    }
    write_jsonl(PACKAGE / "candidates.jsonl", candidates)
    write_jsonl(PACKAGE / "retrievals.jsonl", [{k: v for k, v in r.items() if k != "source"} | {"source_id": (r["source"] or {}).get("source_id")} for r in retrievals.values()])
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest


def verify() -> list[str]:
    """Recompute every hash and re-check every quote from the local archive. Returns problems (empty when sound)."""
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for sid, entry in manifest["sources"].items():
        raw, text = (PACKAGE / entry["files"]["raw"]).read_bytes(), (PACKAGE / entry["files"]["text"]).read_text(encoding="utf-8")
        s = entry["source"]
        if sha256(raw) != s["raw_hash"] or sha256(text.encode("utf-8")) != s["text_hash"] or "src:" + s["text_hash"] != sid:
            problems.append(f"{sid}: archived files do not match their hashes")
    for line in (PACKAGE / "candidates.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        for ev in c["claim"]["evidence"]:
            entry = manifest["sources"].get(ev["source_id"])
            if entry is None:
                problems.append(f"{c['candidate_id']}: source {ev['source_id']} missing from manifest")
                continue
            text = (PACKAGE / entry["files"]["text"]).read_text(encoding="utf-8")
            if (why := check_offsets(text, ev["start"], ev["end"], ev["quote"])) is not None:
                problems.append(f"{c['candidate_id']}: {why}")
    return problems


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        found = verify()
        print("\n".join(found) or "package verified: every hash and quote offset reproduces")
        sys.exit(1 if found else 0)
    m = stage(json.loads((PACKAGE / "spec.json").read_text(encoding="utf-8")))
    print(json.dumps({"candidates": len(m["candidates"]), "sources": len(m["sources"]), "failures": m["failures"],
                      "gaps": [k for k, v in m["conditions"].items() if v["outcome"] == "unresolved_gap"]}, indent=1))
