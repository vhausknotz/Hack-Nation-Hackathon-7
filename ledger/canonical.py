"""Canonical encodings, so that the same content always has the same hash.

- JSON: sorted keys, no insignificant whitespace, UTF-8, Unicode NFC strings.
- Text (archived sources): NFC, newlines normalized, runs of spaces collapsed, blank-line runs collapsed.
- Quotes: the same rules on a single line, so a quote matches the canonical text it came from.
"""

import hashlib
import json
import re
import unicodedata

TEXT_CANON_VERSION = "text-canon@1"


def _nfc(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {_nfc(k): _nfc(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_nfc(v) for v in value]
    return value


def canonical_json(obj) -> bytes:
    return json.dumps(_nfc(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_id(prefix: str, obj) -> str:
    """Content-derived identity, e.g. content_id("claim", {...}) -> "claim:sha256:…"."""
    return f"{prefix}:{sha256(canonical_json(obj))}"


def canonical_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t   ]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def canonical_quote(quote: str) -> str:
    """A quote as it must appear in canonical text: NFC, whitespace (incl. newlines) collapsed to single spaces."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", quote)).strip()


def find_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Locate a quote in canonical text, treating any whitespace run in the text as one space.

    Returns (start, end) offsets into `text`, or None. The kernel later verifies that
    canonical_quote(text[start:end]) == canonical_quote(quote).
    """
    q = canonical_quote(quote)
    if not q:
        return None
    pattern = r"\s+".join(re.escape(part) for part in q.split(" "))
    m = re.search(pattern, text)
    return (m.start(), m.end()) if m else None
