"""Who works on each gene: investigators from PubMed patient research and NIH-funded projects (RePORTER).

    python pipeline/people.py [--limit N]     # resumable; writes data/build/people.json (gene symbol -> people)

Public, professional information only: author names and institutions as printed on publications, principal
investigators and organizations of funded projects. E-mail addresses inside affiliation strings are removed.
Researchers are gene-level (a paper about a gene may concern several of its conditions), keyed by surname +
first initial, so identically named people can merge; the display says "as listed on publications".
No language model is used.
"""
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "build" / "people.json"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
REPORTER = "https://api.reporter.nih.gov/v2/projects/search"
EMAIL = re.compile(r"\s*\S+@\S+")
AMBIGUOUS = re.compile(r"^[A-Z]{1,3}\d?$")  # very short symbols collide with ordinary words and abbreviations


INSTITUTION = re.compile(r"universit|hospital|institut|center|centre|college|school|clinic|foundation|laborator|academy|inserm|cnrs|nih", re.I)


def clean_affiliation(text: str) -> str:
    """The institution and its city/country, not the department: what a family can look up."""
    text = EMAIL.sub("", text or "").strip().rstrip(".;,")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    strong = re.compile(r"universit|hospital|college|school|clinic", re.I)
    inst = next((i for i, part in enumerate(parts) if strong.search(part) and not part.lower().startswith(("department", "division"))),
                next((i for i, part in enumerate(parts) if INSTITUTION.search(part)), 0))
    return ", ".join(parts[inst:inst + 1] + parts[-1:] if len(parts) > inst + 1 else parts[inst:inst + 1])[:140]


def pubmed(gene: str, session: requests.Session) -> list[dict]:
    term = (f'{gene}[tiab] AND (variant*[tiab] OR mutation*[tiab] OR pathogenic[tiab]) '
            f'AND (patient*[tiab] OR case[tiab] OR individuals[tiab] OR cohort[tiab]) AND ("2015"[dp]:"3000"[dp])')
    ids = session.get(EUTILS + "esearch.fcgi", params={"db": "pubmed", "term": term, "retmax": 25, "sort": "pub_date",
                                                       "retmode": "json", "tool": "rare-disease-atlas"}, timeout=30).json()["esearchresult"]["idlist"]
    time.sleep(0.35)
    if not ids:
        return []
    xml = session.get(EUTILS + "efetch.fcgi", params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": "rare-disease-atlas"}, timeout=60).content
    time.sleep(0.35)
    doc = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))
    people: dict[str, dict] = {}
    for art in doc.findall(".//PubmedArticle"):
        pmid = art.findtext(".//MedlineCitation/PMID")
        year = art.findtext(".//Article/Journal/JournalIssue/PubDate/Year") or (art.findtext(".//Article/Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
        authors = [a for a in art.findall(".//AuthorList/Author") if a.findtext("LastName")]
        # First and last authors usually lead the work; middle authors are counted but weigh less.
        for i, a in enumerate(authors):
            last, fore = a.findtext("LastName"), a.findtext("ForeName") or a.findtext("Initials") or ""
            key = f"{last.casefold()}|{fore[:1].casefold()}"
            role = 2 if i in (0, len(authors) - 1) else 1
            p = people.setdefault(key, {"name": f"{fore} {last}".strip(), "affiliations": Counter(), "papers": [], "weight": 0, "latest": ""})
            aff = clean_affiliation(a.findtext(".//AffiliationInfo/Affiliation") or "")
            if aff:
                p["affiliations"][aff] += 1
            p["papers"].append(pmid)
            p["weight"] += role
            p["latest"] = max(p["latest"], year or "")
    ranked = sorted(people.values(), key=lambda p: (-p["weight"], -len(p["papers"]), p["name"]))
    return [{"name": p["name"], "affiliation": p["affiliations"].most_common(1)[0][0] if p["affiliations"] else "",
             "papers": len(p["papers"]), "pmids": p["papers"][:5], "latest": p["latest"]}
            for p in ranked if len(p["papers"]) >= 2 or p["weight"] >= 2][:8]


def reporter(gene: str, session: requests.Session) -> list[dict]:
    year = datetime.now(timezone.utc).year
    body = {"criteria": {"advanced_text_search": {"operator": "and", "search_field": "projecttitle,terms",
                                                  "search_text": f'"{gene}"'},
                         "fiscal_years": [year - 2, year - 1, year]},
            "include_fields": ["ProjectTitle", "PrincipalInvestigators", "Organization", "FiscalYear", "ProjectNum", "ProjectDetailUrl"],
            "limit": 25, "offset": 0}
    r = session.post(REPORTER, json=body, timeout=60)
    time.sleep(1.0)
    if r.status_code != 200:
        return []
    projects = {}
    for p in r.json().get("results", []):
        core = (p.get("project_num") or "")[1:12]  # one entry per grant across years and supplements
        pis = [x.get("full_name", "").title() for x in p.get("principal_investigators") or [] if x.get("full_name")]
        entry = projects.setdefault(core, {"title": (p.get("project_title") or "").strip()[:200], "pis": pis[:3],
                                           "organization": ((p.get("organization") or {}).get("org_name") or "").title(),
                                           "years": set(), "url": p.get("project_detail_url") or ""})
        entry["years"].add(p.get("fiscal_year"))
    out = [{**v, "years": sorted(y for y in v["years"] if y)} for v in projects.values() if v["pis"]]
    out.sort(key=lambda v: (-max(v["years"] or [0]), v["title"]))
    return out[:6]


def main(args: list[str]) -> None:
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    genes = sorted({json.loads(l)["gene"]["symbol"] for l in (ROOT / "data/build/conditions.jsonl").read_text(encoding="utf-8").splitlines() if l})
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [g for g in genes if g not in data][:limit]
    session = requests.Session()
    session.headers["User-Agent"] = "rare-disease-atlas/1.0 (research coordination; https://salmon-island-04aa8f603.1.azurestaticapps.net)"
    for n, gene in enumerate(todo, 1):
        entry = {"retrieved": datetime.now(timezone.utc).date().isoformat(), "researchers": [], "projects": []}
        if not AMBIGUOUS.match(gene) or any(ch.isdigit() for ch in gene):
            try:
                entry["researchers"] = pubmed(gene, session)
            except (requests.RequestException, ValueError, KeyError, etree.XMLSyntaxError) as e:
                print(f"{gene} pubmed: {e}", file=sys.stderr)
                continue
            try:
                entry["projects"] = reporter(gene, session)
            except (requests.RequestException, ValueError) as e:
                print(f"{gene} reporter: {e}", file=sys.stderr)
        data[gene] = entry
        if n % 25 == 0 or n == len(todo):
            tmp = OUT.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(OUT)
            print(f"{n}/{len(todo)} genes", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
