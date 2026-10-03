"""Literature agents: scout (find papers), screener (is it about this condition?), extractor (symptoms with quotes).

Sources are PubMed abstracts, archived in the ledger's canonical form before anything is extracted,
so every quote can be checked mechanically against the exact text the model saw.
"""

import json
import re

from lxml import etree

from . import ROOT  # noqa: F401
import llm  # noqa: E402
from http_cache import fetch_json  # noqa: E402
from ledger import sources  # noqa: E402
from ledger.canonical import find_quote  # noqa: E402
from sources import pubmed  # noqa: E402

SCREEN_MODEL = "gpt-6-luna"
EXTRACT_MODEL = "gpt-6-luna"
SCREEN_PROMPT = "screen-paper@1"
EXTRACT_PROMPT = "extract-symptoms@1"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ---- scout ------------------------------------------------------------------------------------------------
def scout(gene: str, curated_pmids: list[str], max_search: int = 40) -> list[str]:
    """Candidate PubMed IDs: curated references first, then a disease-focused search on the gene."""
    term = f"{gene}[tiab] AND (variant*[tiab] OR mutation*[tiab]) AND (patient*[tiab] OR individual*[tiab] OR child*[tiab] OR case[tiab])"
    _, found = pubmed.search(term, retmax=max_search, sort="relevance")
    out, seen = [], set()
    for p in [x.replace("PMID:", "").strip() for x in curated_pmids] + found:
        if p.isdigit() and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def archive_abstracts(pmids: list[str], ledger, signer) -> dict[str, dict]:
    """Fetch PubMed records, archive each as a canonical source, return pmid -> {source, text, title}."""
    out = {}
    for i in range(0, len(pmids), 50):
        xml = fetch_json(f"{EUTILS}/efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids[i:i + 50]), "retmode": "xml"}, min_interval=0.4, as_text=True)
        root = etree.fromstring(xml.encode("utf-8"))
        for art in root.iterfind("PubmedArticle"):
            pmid = art.findtext("MedlineCitation/PMID")
            if art.find("MedlineCitation/Article/Abstract") is None:
                continue
            raw = b"<PubmedArticleSet>" + etree.tostring(art) + b"</PubmedArticleSet>"
            src = sources.archive(raw, f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "pubmed_xml", "PubMed abstract", True)
            ledger.add_source(src, signer)
            text = sources.read_text(src)
            if text and len(text) > 200:
                out[pmid] = {"source": src, "text": text, "title": src.title}
    return out


# ---- screener ----------------------------------------------------------------------------------------------
def screen(condition: dict, papers: dict[str, dict]) -> dict[str, dict]:
    """pmid -> {"relevance": direct|related|not_relevant, "reason"}."""
    gene = condition["gene"]["symbol"]
    names = [condition["name"], condition["disease_name"]] + condition["also_known_as"][:4]
    results = {}
    items = list(papers.items())
    for i in range(0, len(items), 8):
        batch = [{"pmid": p, "title": d["title"], "abstract": d["text"][:1800]} for p, d in items[i:i + 8]]
        reply = llm.chat_json(SCREEN_MODEL, [
            {"role": "system", "content": (
                f"You screen research abstracts for a rare-disease atlas. The condition is caused by germline variants in {gene} "
                f"and is also called: {'; '.join(dict.fromkeys(names))}. For each abstract decide: "
                "'direct' = it reports patients with this condition (clinical features, natural history, cohorts, case reports); "
                f"'related' = it studies {gene} disease mechanisms or models but reports no patients; "
                f"'not_relevant' = {gene} appears only incidentally (e.g. toxins, other diseases, biomarkers of something else). "
                'Return JSON {"results": [{"pmid": "...", "relevance": "...", "reason": "<short>"}]}.')},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
        ], task=SCREEN_PROMPT)
        for r in reply.get("results", []):
            results[str(r.get("pmid"))] = {"relevance": r.get("relevance", "not_relevant"), "reason": r.get("reason", "")}
    return results


# ---- extractor ---------------------------------------------------------------------------------------------
def extract_symptoms(condition: dict, paper: dict) -> list[dict]:
    """Candidate symptom statements with verbatim quotes and character offsets into the canonical text."""
    gene = condition["gene"]["symbol"]
    reply = llm.chat_json(EXTRACT_MODEL, [
        {"role": "system", "content": (
            f"Extract the clinical features reported in human patients with {gene}-related disease in this abstract. "
            "Only features of patients (not animals, cells or controls). For each feature give: "
            "'feature' = a short clinical term; "
            "'quote' = an EXACT contiguous span copied character-for-character from the text that states the feature (max 300 characters); "
            "'frequency' = how many patients, if stated (e.g. '21/23'), else ''; "
            "'certainty' = 'asserted' if stated as a finding, 'suggested' if hedged (may, might, possibly), 'speculative' if a hypothesis; "
            "'evidence_level' = 'case_report' for 1-3 patients, else 'clinical'. "
            'Return JSON {"features": [...]}. Return an empty list if no patient features are reported.')},
        {"role": "user", "content": paper["text"]},
    ], task=EXTRACT_PROMPT)
    out = []
    for f in reply.get("features", []):
        span = find_quote(paper["text"], f.get("quote", ""))
        out.append({**f, "span": span})
    return out


def frequency_text(value: str) -> str:
    m = re.match(r"^\s*(\d+)\s*(?:/|of|out of)\s*(\d+)\s*$", value or "")
    return f"{m.group(1)}/{m.group(2)}" if m else ""
