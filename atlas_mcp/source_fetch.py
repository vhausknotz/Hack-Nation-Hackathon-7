"""Bounded fetches from fixed official origins, shared by local and cloud intake."""
import json
import re
import requests
from lxml import etree
from ledger import sources


def official_url(provider, record_id):
    if provider == "pubmed" and re.fullmatch(r"[1-9][0-9]{0,8}", record_id):
        return f"https://pubmed.ncbi.nlm.nih.gov/{record_id}/"
    if provider == "clinicaltrials" and re.fullmatch(r"NCT[0-9]{8}", record_id):
        return f"https://clinicaltrials.gov/study/{record_id}"
    raise ValueError("Use provider pubmed with a PMID, or clinicaltrials with an NCT ID. Arbitrary URLs are not fetched.")


def fetch_official(provider, record_id, root):
    url = official_url(provider, record_id)
    endpoint = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={record_id}&retmode=xml"
                if provider == "pubmed" else f"https://clinicaltrials.gov/api/v2/studies/{record_id}")
    with requests.get(endpoint, timeout=(10, 25), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError(f"Source provider returned HTTP {response.status_code}; retry later")
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 2_000_000:
                raise ValueError("Source exceeds the 2 MB intake limit")
            chunks.append(chunk)
        raw = b"".join(chunks)
    if provider == "pubmed":
        doc = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        if b"<!ENTITY" in raw:
            raise ValueError("Source may not declare entities")
        if doc.findtext(".//MedlineCitation/PMID") != record_id or doc.find(".//Abstract") is None:
            raise ValueError("Provider response did not contain the requested abstract")
        media, license_ = "pubmed_xml", "PubMed abstract"
    else:
        from enrich.trials.run import render
        study = json.loads(raw)
        if study["protocolSection"]["identificationModule"]["nctId"] != record_id:
            raise ValueError("Provider returned a different trial")
        raw = render(study).encode()
        media, license_ = "text", "ClinicalTrials.gov (public domain)"
    return sources.archive(raw, url, media, license_, True, root=root)
