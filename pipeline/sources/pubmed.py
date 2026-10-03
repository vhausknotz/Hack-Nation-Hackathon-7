"""PubMed via NCBI E-utilities: search counts, IDs and article metadata (title, journal, year, authors, abstract)."""

from dataclasses import dataclass, field

from lxml import etree

from http_cache import fetch_json

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE = 0.4  # NCBI allows 3 requests/second without an API key


@dataclass
class Author:
    last: str
    fore: str
    affiliations: list[str] = field(default_factory=list)
    orcid: str | None = None


@dataclass
class Article:
    pmid: str
    title: str
    journal: str
    year: str
    abstract: str
    authors: list[Author]
    pmcid: str | None
    publication_types: list[str]


def search(term: str, retmax: int = 0, sort: str = "relevance") -> tuple[int, list[str]]:
    data = fetch_json(f"{EUTILS}/esearch.fcgi", {"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax, "sort": sort}, min_interval=RATE)
    result = data["esearchresult"]
    return int(result["count"]), result.get("idlist", [])


def fetch(pmids: list[str]) -> list[Article]:
    articles: list[Article] = []
    for i in range(0, len(pmids), 100):
        xml = fetch_json(f"{EUTILS}/efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids[i:i + 100]), "retmode": "xml"}, min_interval=RATE, as_text=True)
        root = etree.fromstring(xml.encode("utf-8"))
        for node in root.iterfind("PubmedArticle"):
            art = node.find("MedlineCitation/Article")
            authors = []
            for a in art.iterfind("AuthorList/Author"):
                orcid = a.findtext("Identifier[@Source='ORCID']")
                authors.append(Author(a.findtext("LastName") or a.findtext("CollectiveName") or "", a.findtext("ForeName") or "",
                                      [x.text for x in a.iterfind("AffiliationInfo/Affiliation") if x.text], orcid))
            abstract = " ".join("".join(t.itertext()) for t in art.iterfind("Abstract/AbstractText"))
            year = art.findtext("Journal/JournalIssue/PubDate/Year") or (art.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
            articles.append(Article(
                pmid=node.findtext("MedlineCitation/PMID"),
                title="".join(art.find("ArticleTitle").itertext()) if art.find("ArticleTitle") is not None else "",
                journal=art.findtext("Journal/Title") or "",
                year=year,
                abstract=abstract,
                authors=authors,
                pmcid=node.findtext("PubmedData/ArticleIdList/ArticleId[@IdType='pmc']"),
                publication_types=[p.text for p in art.iterfind("PublicationTypeList/PublicationType")],
            ))
    return articles
