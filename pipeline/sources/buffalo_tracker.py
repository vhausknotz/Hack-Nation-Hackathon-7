"""Buffalo Initiative Patient-Powered Pipeline Tracker (https://buffaloinitiative.org/pipeline/).

Programs are self-reported by the submitting patient organizations and not verified by Buffalo,
so the atlas labels them as self-reported. robots.txt allows all crawlers, but the site's anti-spam
filter rejects non-browser user agents, so we send a plain browser UA, wait 2 s between pages and cache.
"""

from dataclasses import dataclass

from lxml import html as lxml_html

from http_cache import fetch_json

URL = "https://buffaloinitiative.org/pipeline/"


@dataclass
class Program:
    disease: str
    program: str
    updated: str  # MM/DD/YYYY as shown on the card
    tags: list[str]  # therapeutic area and modality, e.g. ["Neurology", "Nucleic Acid/RNA/ASO"]
    stage: str
    organization: str
    organization_url: str
    partners: list[str]
    source_url: str


def _has_class(name: str) -> str:
    return f'contains(concat(" ", normalize-space(@class), " "), " {name} ")'


def _text(node, xpath: str) -> str:
    found = node.xpath(xpath)
    return " ".join(found[0].text_content().split()) if found else ""


def _parse(page_html: str, page_url: str) -> list[Program]:
    doc = lxml_html.fromstring(page_html)
    programs = []
    for card in doc.xpath('//article[contains(@class,"wpgb-card")]'):
        org = card.xpath('.//a[contains(@class,"program-primary-sponsor")]')
        programs.append(Program(
            disease=_text(card, f".//*[{_has_class('wpgb-block-2')}]"),
            program=_text(card, f".//*[{_has_class('wpgb-block-1')}]"),
            updated=_text(card, ".//time"),
            tags=[" ".join(t.text_content().split()) for t in card.xpath(f".//span[{_has_class('wpgb-block-term')}]")],
            stage=_text(card, f".//*[{_has_class('wpgb-block-13')}]"),
            organization=" ".join(org[0].text_content().split()) if org else "",
            organization_url=org[0].get("href", "") if org else "",
            partners=[" ".join(li.text_content().split()) for li in card.xpath('.//ul[contains(@class,"program-partner-organizations")]/li')],
            source_url=page_url,
        ))
    return programs


def load(max_pages: int = 30) -> list[Program]:
    programs: list[Program] = []
    seen = set()
    for page in range(1, max_pages + 1):
        page_url = f"{URL}?_pagination={page}"
        page_html = fetch_json(URL, {"_pagination": page}, min_interval=2.0, as_text=True, headers={"User-Agent": "Mozilla/5.0"})
        batch = _parse(page_html, page_url)
        new = [p for p in batch if (p.disease, p.program, p.organization) not in seen]
        if not new:
            break
        seen |= {(p.disease, p.program, p.organization) for p in new}
        programs += new
    return programs
