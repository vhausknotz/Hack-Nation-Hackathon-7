"""Source archive: every quoted source is stored as fetched bytes plus a canonical text.

Quote offsets point into the canonical text, so a claim stays verifiable after the original
web page changes or disappears. Files are content-addressed under data/ledger/sources/.
Licensing: PubMed abstracts and open-access full text may be redistributed; other archived
copies are kept for verification only (see `redistributable`).
"""

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree, html

from . import LEDGER_DIR
from .canonical import TEXT_CANON_VERSION, canonical_text, sha256

ARCHIVE = LEDGER_DIR / "sources"
EXTRACTORS = {"pubmed_xml": "pubmed-abstract@1", "html": "html-text@1", "text": "plain@1", "json_fields": "json-fields@1"}


@dataclass
class Source:
    source_id: str  # "src:" + text hash
    url: str
    media_type: str  # pubmed_xml | html | text | json_fields
    raw_hash: str
    text_hash: str
    extractor: str  # e.g. "pubmed-abstract@1+text-canon@1"
    retrieved: str
    license: str  # e.g. "PubMed abstract", "CC BY 4.0", "verification-only"
    redistributable: bool
    title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _paths(raw_hash: str, text_hash: str, root: Path) -> tuple[Path, Path]:
    return root / "raw" / f"{raw_hash.split(':')[1]}.bin", root / "text" / f"{text_hash.split(':')[1]}.txt"


def extract_text(raw: bytes, media_type: str) -> tuple[str, str]:
    """(title, body text) before canonicalization."""
    if media_type == "pubmed_xml":
        root = etree.fromstring(raw)
        art = root.find(".//MedlineCitation/Article")
        title = "".join(art.find("ArticleTitle").itertext()) if art is not None and art.find("ArticleTitle") is not None else ""
        parts = []
        for node in art.iterfind("Abstract/AbstractText") if art is not None else []:
            label = node.get("Label")
            body = "".join(node.itertext())
            parts.append(f"{label}: {body}" if label else body)
        return title, title + "\n\n" + "\n\n".join(parts)
    if media_type == "html":
        doc = html.fromstring(raw)
        for bad in doc.xpath("//script|//style|//noscript|//nav|//footer|//header"):
            bad.drop_tree()
        title = (doc.findtext(".//title") or "").strip()
        for block in doc.xpath("//p|//div|//li|//h1|//h2|//h3|//h4|//tr|//br"):
            block.tail = "\n" + (block.tail or "")
        return title, doc.text_content()
    text = raw.decode("utf-8", errors="replace")
    return text.split("\n", 1)[0][:200], text


def archive(raw: bytes, url: str, media_type: str, license: str, redistributable: bool, root: Path = ARCHIVE) -> Source:
    title, body = extract_text(raw, media_type)
    text = canonical_text(body)
    raw_hash, text_hash = sha256(raw), sha256(text.encode("utf-8"))
    raw_path, text_path = _paths(raw_hash, text_hash, root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raw_path.write_bytes(raw)
    if not text_path.exists():
        text_path.write_text(text, encoding="utf-8")
    return Source(
        source_id="src:" + text_hash, url=url, media_type=media_type, raw_hash=raw_hash, text_hash=text_hash,
        extractor=f"{EXTRACTORS[media_type]}+{TEXT_CANON_VERSION}", retrieved=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        license=license, redistributable=redistributable, title=re.sub(r"\s+", " ", title).strip()[:300],
    )


def read_text(source: Source | dict, root: Path = ARCHIVE) -> str | None:
    s = source if isinstance(source, dict) else source.to_dict()
    _, text_path = _paths(s["raw_hash"], s["text_hash"], root)
    return text_path.read_text(encoding="utf-8") if text_path.exists() else None


def read_raw(source: Source | dict, root: Path = ARCHIVE) -> bytes | None:
    s = source if isinstance(source, dict) else source.to_dict()
    raw_path, _ = _paths(s["raw_hash"], s["text_hash"], root)
    return raw_path.read_bytes() if raw_path.exists() else None
