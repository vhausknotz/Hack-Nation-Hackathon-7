"""Community scout: find the patient organizations that serve a condition, proven by their own website.

    python -m agents.communities <campaign-name> MONDO:… [MONDO:… …] [--neighbors 5]

Per condition:
1. GPT-6 Luna with web search names candidate organizations and a page on each one's own site
   (falls back to GPT-6 Sol, then to Sol naming candidates from its own knowledge when search is declined;
   discovery is never evidence, so a wrong or invented candidate simply fails the next steps)
2. we fetch that page ourselves (robots.txt respected; the Internet Archive's latest snapshot when the site
   blocks automated visitors), archive it, and pick a verbatim sentence that
   names the condition or gene, deterministically, never from the model
3. the kernel checks the quote at its offsets and the signature
4. GPT-6 Sol reviews: is this a patient organization, and does the page show it serves these patients?

--neighbors N also scouts the N closest other-gene relatives of each condition, so a family whose own
condition has no organization can be pointed to the nearest community that does.
"""

import json
import re
import sys
import time
import urllib.robotparser
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import requests
from lxml.etree import ParserError

from . import ROOT
import llm  # noqa: E402
from ledger import identity, sources  # noqa: E402
from ledger.api import Ledger, now  # noqa: E402
from ledger.schema import make_claim  # noqa: E402
from ledger.canonical import find_quote as locate_quote  # noqa: E402

from .verify import MODEL_FAMILY, VERIFY_MODEL  # noqa: E402

SCOUT_MODEL, FALLBACK_MODEL = "gpt-6-luna", "gpt-6-sol"
SCOUT_PROMPT, RECALL_PROMPT, VERIFY_PROMPT = "find-communities@3", "recall-communities@2", "verify-community@3"
PROFILE_VERIFY_PROMPT = "verify-community-profile@2"
USER_AGENT = "Mozilla/5.0 (compatible; rare-disease-atlas/0.1; +https://github.com/vhausknotz/Hack-Nation-Hackathon-7)"
CAMPAIGNS = ROOT / "data" / "campaigns"
# directories, platforms and reference sites: useful, but not a community of their own
NOT_A_COMMUNITY = ("facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "tiktok.com",
                   "wikipedia.org", "nih.gov", "orpha.net", "omim.org", "medlineplus.gov", "clinicaltrials.gov",
                   "rarediseases.org", "globalgenes.org", "eurordis.org", "geneticalliance.org", "rareconnect.org",
                   "malacards.org", "genecards.org", "mayoclinic.org", "clevelandclinic.org", "healthline.com", "webmd.com")
ORG_TYPES = {  # what families see: only patient organizations count as "your people"
    "patient_organization": ("a group that gathers, represents or supports the families living with this condition, its gene, or a "
                             "named set of conditions that includes it (a foundation, family network or advocacy group for them)"),
    "research_program": "a research study, registry or data platform that families can join (e.g. a natural history registry)",
    "information_service": ("a site that explains many conditions without gathering a community around this one, even if a "
                            "nonprofit runs it (e.g. a disease information library or general rare-disease helpline)"),
    "professional_network": "a network of clinicians or scientists",
    "company": "a company, clinic, lab or for-profit service",
}
ORG_WORDS = re.compile(r"foundation|famil|mission|support|dedicated|cure|research|community|patients|children|advoca|connect",
                       re.IGNORECASE)

# Organization-wide descriptions complement condition leaf pages. They are evidence,
# not classification overrides: the kernel checks the quote and Sol still judges it.
ORG_PROFILES = {
    "org:simonssearchlight-org": {
        "source_id": "src:sha256:9ef48869aa136c64be4cbc7c1c1d00f473456876a742ab175c0d887995df6222",
        "quote": "Simons Searchlight is an online international research program, building an ever growing natural history database, biorepository, and resource network of over 175 rare genetic neurodevelopmental disorders.",
    },
}


def organization_profile(oid, ledger):
    profile = ORG_PROFILES.get(oid)
    if not profile:
        return None
    source = ledger.store.source(profile["source_id"])
    if source is None:
        raise ValueError("Pinned organization profile source is missing from the ledger archive")
    span = locate_quote(sources.read_text(source) or "", profile["quote"])
    if span is None:
        raise ValueError("Organization profile quote does not match its archived source")
    return {"type": "organization_page", **profile, "start": span[0], "end": span[1], "supports": "organization_kind",
            "url": source["url"], "page_read": "live", "page_date": source["retrieved"][:10]}


def ask(condition: dict, model: str, recall: bool = False) -> list[dict] | None:
    names = [condition["name"]] + [n for n in condition["also_known_as"] if n.lower() != condition["name"].lower()][:3]
    gene = condition["gene"]["symbol"]
    prompt = (
        f"Search the web: which nonprofit foundations, patient advocacy groups or family networks focus on {names[0]} "
        f"(caused by changes in the {gene} gene; also called {'; '.join(names[1:]) or names[0]})? "
        f"Include groups for all {gene}-related conditions, national and regional groups in any country, and groups for a "
        "broader set of conditions that explicitly include it. "
        "For each, give its name, its homepage, the address of a page on its own website that names this condition or the "
        f"{gene} gene, whether it focuses on this exact condition, on everything caused by {gene}, or on a broader group, "
        "and what kind of organization it is. "
        'Answer with JSON only: {"organizations": [{"name": "", "homepage": "", "page": "", '
        '"focus": "this condition | this gene | broader group", '
        '"kind": "patient organization | research program or registry | information service | professional network | company"}]}. '
        'If you find none, answer {"organizations": []}.'
    )
    if recall:  # web search declined (a filter sometimes trips on search results): ask from the model's own knowledge.
        # Safe because nothing is trusted from discovery: every candidate must still be found, read and quoted on its own site.
        text = llm.chat(model, [{"role": "user", "content": prompt.replace("Search the web: which", "From what you know, which")}],
                        task=RECALL_PROMPT)
    else:
        text = llm.search(model, prompt, task=SCOUT_PROMPT)["text"]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        orgs = json.loads(match.group(0))["organizations"] if match else None
    except (json.JSONDecodeError, KeyError, TypeError):
        orgs = None
    return orgs if isinstance(orgs, list) else None


def org_id(homepage: str) -> str | None:
    host = urlparse(homepage if "://" in homepage else "https://" + homepage).hostname or ""
    host = host.lower().removeprefix("www.")
    if not host or any(host == d or host.endswith("." + d) for d in NOT_A_COMMUNITY):
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    return f"org:{slug}"[:84] if slug else None


_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def allowed(url: str) -> bool:
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            _robots[base] = rp
        except requests.RequestException:
            _robots[base] = None
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def _get(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    except requests.RequestException:
        return None
    time.sleep(1)
    return r.content if r.status_code == 200 and "html" in r.headers.get("content-type", "") else None


def fetch_page(url: str) -> tuple[bytes, str, str, str] | None:
    """(html, address it was read from, "live" | "archived_snapshot", date of the content).

    The live page if robots.txt allows us and the site answers; otherwise the latest Internet Archive snapshot,
    a public timestamped copy (many small sites block all automated visitors). A snapshot is historical: it shows
    what the site said on that date, not that the organization is active today."""
    if not url.startswith("http"):
        return None
    if allowed(url) and (raw := _get(url)) is not None:
        return raw, url, "live", now()[:10]
    rows = []
    for attempt in range(3):  # the archive's index is sometimes briefly unavailable
        try:
            rows = requests.get("https://web.archive.org/cdx/search/cdx", params={
                "url": url, "output": "json", "limit": "-1", "filter": "statuscode:200", "fl": "timestamp,original"},
                headers={"User-Agent": USER_AGENT}, timeout=45).json()
            break
        except (requests.RequestException, ValueError):
            time.sleep(3 * (attempt + 1))
    if len(rows) < 2:
        return None
    ts, original = rows[-1]
    snapshot = f"https://web.archive.org/web/{ts}id_/{original}"
    raw = _get(snapshot)
    return (raw, f"https://web.archive.org/web/{ts}/{original}", "archived_snapshot", f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}") if raw is not None else None


def term_patterns(condition: dict) -> list[re.Pattern]:
    gene = condition["gene"]["symbol"]
    gene_re = re.sub(r"(?<=[A-Za-z])(?=\d)", "-?", re.escape(gene))  # SNAP25 also matches SNAP-25
    names = {n for n in [condition["name"], condition["disease_name"]] + condition["also_known_as"] if len(n) >= 6}
    return [re.compile(rf"(?<![A-Za-z0-9]){gene_re}(?![A-Za-z0-9])")] + [
        re.compile(rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])", re.IGNORECASE) for n in sorted(names, key=len, reverse=True)]


def find_quote(text: str, patterns: list[re.Pattern]) -> tuple[int, int] | None:
    """Offsets of a verbatim sentence that names the condition or gene; prefers sentences about the organization."""
    # Negative scores are still candidates. Semantic review, not this ranking
    # threshold, decides whether a passage establishes whom a group serves.
    best, best_score = None, float("-inf")
    pos = 0
    for line in text.split("\n"):
        start, end = pos, pos + len(line)
        pos = end + 1
        hit = next((m for p in patterns if (m := p.search(line))), None)
        if hit is None or len(line.strip()) < 25:
            continue
        s, e = 0, len(line)
        if len(line) > 400:  # narrow to the sentence around the match
            s = max(line.rfind(". ", 0, hit.start()) + 2, 0) if line.rfind(". ", 0, hit.start()) >= 0 else 0
            nxt = line.find(". ", hit.end())
            e = nxt + 1 if nxt >= 0 else len(line)
            if e - s > 400:
                s, e = max(0, hit.start() - 150), min(len(line), hit.end() + 200)
        while s < e and line[s].isspace():
            s += 1
        while e > s and line[e - 1].isspace():
            e -= 1
        score = len(ORG_WORDS.findall(line[s:e])) * 10 - abs(len(line[s:e]) - 160) / 40
        if score > best_score:
            best, best_score = (start + s, start + e), score
    return best


def verify_community(condition: dict, org: dict, page_title: str, quote: str, page_text: str, profile: dict | None = None, chat_json=None) -> dict:
    reply = (chat_json or llm.chat_json)(VERIFY_MODEL, [
        {"role": "system", "content": (
            "You check claims for a rare-disease evidence ledger. A claim says an organization of a given kind serves people "
            "with one genetic condition, at a given scope. Judge ONLY from the organization's page, without outside knowledge. "
            "Do not judge whether the organization is active today.\n"
            "The supplied quote must carry the decision about THIS organization and condition/gene. A quote describing a different "
            "foundation, even on this organization's own page, does not support the claim. Return does_not_support for that "
            "attribution error. Page context can resolve references, but cannot substitute for missing quoted support. "
            "An organization-wide profile establishes kind, not diagnosis-specific membership or eligibility.\n"
            "Kinds: " + "; ".join(f"{k} = {v}" for k, v in ORG_TYPES.items()) + ".\n"
            "Scopes: this_condition; this_gene (everything caused by the gene); broader_group (many conditions, explicitly including this one).\n"
            "Answer: serves_these_patients (does the page show the organization works for or with people who have this "
            "condition or its gene?), the correct kind and scope, and a verdict on the claim exactly as stated: 'supports'; "
            "'supports_with_qualification' (true, but the page only mentions the condition in passing); 'does_not_support' "
            "(wrong kind, wrong scope, or it does not serve these patients); 'out_of_scope' (the page is about something else). "
            'Return JSON {"serves_these_patients": true|false, "kind": "...", "scope": "...", "verdict": "...", '
            '"reason": "<one plain sentence>"}.' +
            (" The organization_profile is a separate verbatim passage from this organization's own site. Use it to assess the organization's kind, while using the condition page to assess whom it serves. A registry's information page does not make the registry an information-only service." if profile else ""))},
        {"role": "user", "content": json.dumps({
            "condition": f"{condition['name']} (caused by {condition['gene']['symbol']} variants)",
            "organization": org["name"], "homepage": org["homepage"], "claimed_kind": org["org_type"], "claimed_scope": org["scope"],
            "page_title": page_title, "quote": quote, "page_text": page_text[:6000],
            **({"organization_profile": profile} if profile else {}),
        }, ensure_ascii=False)},
    ], task=PROFILE_VERIFY_PROMPT if profile else VERIFY_PROMPT)
    verdict = reply.get("verdict")
    if verdict not in ("supports", "supports_with_qualification", "does_not_support", "out_of_scope"):
        verdict = "out_of_scope"
    return {"verdict": verdict, "reason": reply.get("reason", "")[:500], "serves": reply.get("serves_these_patients") is True,
            "org_type": reply.get("kind") if reply.get("kind") in ORG_TYPES else None,
            "scope": reply.get("scope") if reply.get("scope") in ("this_condition", "this_gene", "broader_group") else None}


def type_of(kind: str) -> str:
    k = (kind or "").lower()
    for word, t in (("patient", "patient_organization"), ("research", "research_program"), ("registry", "research_program"),
                    ("information", "information_service"), ("professional", "professional_network"), ("company", "company")):
        if word in k:
            return t
    return "patient_organization"


def scope_of(focus: str) -> str:
    f = (focus or "").lower()
    return "this_condition" if "condition" in f else "this_gene" if "gene" in f else "broader_group"


def load_conditions() -> dict[str, dict]:
    out = {}
    with open(ROOT / "data" / "build" / "conditions.jsonl", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            out[c["id"]] = c
    return out


def nearest_relatives(ids: list[str], n: int) -> list[str]:
    if n <= 0:
        return []
    want, out = set(ids), []
    with open(ROOT / "data" / "build" / "neighbors.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["id"] in want:
                out += [x["id"] for x in row["neighbors"] if not x["same_gene"]][:n]
    return out


def reuse_claim(ledger, claim):
    """Timestamp changes alone must not create duplicate claims on a cached rerun."""
    a = claim["assertion"]
    for row in ledger.store.claims_where("subject = ? AND predicate = ? AND object = ?", (a["subject"], a["predicate"], a["object"])):
        old = json.loads(row["body"])
        if old["assertion"] == a and old["evidence"] == claim["evidence"] and old["provenance"].get("prompt") == claim["provenance"].get("prompt"):
            return old
    return claim


def save_receipt(path, receipt):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=1, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def scout_condition(c, name, ledger, scout, verifier, pages):
    cid = c["id"]
    r = Counter()
    orgs, discovery = ask(c, SCOUT_MODEL), "web_search"
    if not orgs:
        r["scout_fallback"] += 1
        orgs = ask(c, FALLBACK_MODEL)
    if not orgs:
        r["scout_recall"] += 1
        orgs, discovery = ask(c, FALLBACK_MODEL, recall=True) or [], "model_recall"
    patterns = term_patterns(c)
    found = []
    for o in orgs[:8]:
        if not isinstance(o, dict) or not o.get("homepage"):
            continue
        r["organizations_named"] += 1
        oid = org_id(o["homepage"])
        if oid is None:
            r["skipped_directory_or_platform"] += 1
            continue
        org = {"name": str(o.get("name", ""))[:200], "homepage": o["homepage"], "scope": scope_of(o.get("focus", "")),
               "org_type": type_of(o.get("kind", ""))}
        quote_at = None
        for url in dict.fromkeys(u for u in (o.get("page"), o["homepage"]) if u):
            if url not in pages:
                got = fetch_page(url)
                if got is None:
                    pages[url] = None
                else:
                    try:
                        src = sources.archive(got[0], got[1], "html", "organization website, quoted for citation", False)
                    except ParserError:
                        # Empty/broken pages are missing evidence, not a failure of all remaining organizations.
                        pages[url] = None
                        r["dropped_unreadable_page"] += 1
                        continue
                    ledger.add_source(src, scout)
                    pages[url] = (src, sources.read_text(src) or "", got[2], got[3])
            if pages[url] is None:
                continue
            src, text, read_as, page_date = pages[url]
            if (quote_at := find_quote(text, patterns)) is not None:
                break
        if quote_at is None:
            r["dropped_page_does_not_name_condition"] += 1
            continue
        r[f"page_{read_as}"] += 1
        start, end = quote_at
        evidence = [{"type": "organization_page", "source_id": src.source_id, "quote": text[start:end], "start": start, "end": end,
                     "url": src.url, "page_read": read_as, "page_date": page_date}]
        profile = organization_profile(oid, ledger)
        if profile:
            evidence.append(profile)
        for attempt in range(2):  # a second attempt only to apply the reviewer's correction of kind or scope
            claim = make_claim(cid, "represented_by", oid, evidence,
                               {"contributor": "agent:community-scout", "agent": "community-scout", "model": SCOUT_MODEL,
                                "prompt": SCOUT_PROMPT if discovery == "web_search" else RECALL_PROMPT, "discovery": discovery,
                                "campaign": name, "created": now(),
                                **({"corrected_after_review": True} if attempt else {})},
                               scope=org["scope"], name=org["name"], homepage=org["homepage"], org_type=org["org_type"])
            claim = reuse_claim(ledger, claim)
            result = ledger.propose(claim, scout)
            r["claims_proposed"] += 1
            if not result.accepted:
                r["claims_kernel_rejected"] += 1
                break
            r["claims_kernel_accepted"] += 1
            v = verify_community(c, org, src.title, text[start:end], text, profile)
            if not ledger.store.reviews_for(result.claim_id):
                ledger.review(result.claim_id, v["verdict"], v["reason"], verifier, model_family=MODEL_FAMILY, model=VERIFY_MODEL, prompt=PROFILE_VERIFY_PROMPT if profile else VERIFY_PROMPT)
            r[f"review_{v['verdict']}"] += 1
            correction = (v["serves"] and v["verdict"] == "does_not_support" and v["org_type"] and v["scope"]
                          and (v["org_type"], v["scope"]) != (org["org_type"], org["scope"]))
            if attempt == 0 and correction:
                r["corrected_kind_or_scope"] += 1
                org = {**org, "org_type": v["org_type"], "scope": v["scope"]}
                continue
            found.append(f"{org['name']} ({org['org_type']}, {org['scope']}, {read_as}) [{v['verdict']}]")
            break
    return {"name": c["name"], "status": "complete", **r, "found": found}


def main(args: list[str]) -> None:
    n_rel = int(args[args.index("--neighbors") + 1]) if "--neighbors" in args else 0
    positional = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--neighbors")]
    name, ids = positional[0], positional[1:]
    conditions = load_conditions()
    ids = list(dict.fromkeys(ids + nearest_relatives(ids, n_rel)))
    t0, usage0 = time.time(), llm.usage_summary()

    ledger = Ledger()
    scout = ledger.register(identity.load_or_create("agent:community-scout"), kind="agent", manifest={
        "role": "scout", "model": SCOUT_MODEL, "fallback_model": FALLBACK_MODEL, "model_family": MODEL_FAMILY,
        "prompt": SCOUT_PROMPT, "tools": ["web_search", "HTTP fetch (robots.txt respected)", "Internet Archive snapshots"],
        "quote_selection": "deterministic: the sentence on the organization's own page that names the condition or gene",
    })
    verifier = ledger.register(identity.load_or_create("agent:community-verifier-sol"), kind="agent", manifest={
        "role": "verifier", "model": VERIFY_MODEL, "model_family": MODEL_FAMILY, "prompt": VERIFY_PROMPT,
    })
    receipt_path = CAMPAIGNS / f"{name}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {
        "campaign": name, "kind": "communities", "started": now(), "conditions": {}, "runs": [],
        "cost_note": "Run deltas below exclude spending before checkpointing was introduced; token totals exclude Sol pricing and web-search fees.",
    }
    receipt["complete"] = False
    receipt["requested_conditions"] = ids
    pages = {}
    save_receipt(receipt_path, receipt)
    from openai import RateLimitError
    for cid in ids:
        c = conditions.get(cid)
        if c is None or receipt["conditions"].get(cid, {}).get("status") == "complete":
            continue
        for attempt in range(3):
            try:
                receipt["conditions"][cid] = scout_condition(c, name, ledger, scout, verifier, pages)
                print(f"{c['name'][:60]}: complete", flush=True)
                break
            except RateLimitError as error:
                receipt["conditions"][cid] = {"name": c["name"], "status": "error", "error_type": type(error).__name__, "error": "Azure rate limit; safe to resume"}
                save_receipt(receipt_path, receipt)
                if attempt < 2:
                    time.sleep(45)
            except Exception as error:
                receipt["conditions"][cid] = {"name": c["name"], "status": "error", "error_type": type(error).__name__, "error": str(error)[:300]}
                print(f"{cid}: {type(error).__name__}; recorded for retry", flush=True)
                break
        save_receipt(receipt_path, receipt)

    usage1 = llm.usage_summary()
    searches = sum(v.get("web_searches", 0) for v in usage1.values()) - sum(v.get("web_searches", 0) for v in usage0.values())
    tokens_usd = sum(v["usd"] for v in usage1.values()) - sum(v["usd"] for v in usage0.values())
    head = ledger.publish_tree_head()
    receipt.setdefault("runs", []).append({"finished": now(), "seconds": round(time.time() - t0), "web_searches": searches,
                                            "usd_tokens_known_prices": round(tokens_usd, 4)})
    receipt.update({"finished": now(), "complete": all(receipt["conditions"].get(cid, {}).get("status") == "complete" for cid in ids),
                    "web_searches": sum(r["web_searches"] for r in receipt["runs"]),
                    "usd_tokens_known_prices": round(sum(r["usd_tokens_known_prices"] for r in receipt["runs"]), 4),
                    "ledger_tree_head": {"size": head["size"], "root": head["root"]}, "log_verified": ledger.verify_log()["ok"]})
    save_receipt(receipt_path, receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("conditions", "requested_conditions")}, indent=1))
    ledger.store.close()
    if not receipt["complete"]:
        raise RuntimeError("Community campaign incomplete; failed conditions are saved for a resumable rerun")



if __name__ == "__main__":
    main(sys.argv[1:])
