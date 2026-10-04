"""Fetch an organization page politely and archive it with the ledger's source conventions, into a staging root.

Records what the kernel and a reviewer need to reproduce the read: the requested URL, every redirect hop, the final
URL, the UTC retrieval time, HTTP status and content type. robots.txt is honored for the user agent below; a page
that robots.txt disallows is recorded as a retrieval failure, never fetched.
"""

import time
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from ledger import sources

USER_AGENT = "Mozilla/5.0 (compatible; rare-disease-atlas/0.1; +https://github.com/vhausknotz/Hack-Nation-Hackathon-7)"
LICENSE = "organization website, quoted for citation"

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


@dataclass
class Retrieval:
    requested_url: str
    ok: bool
    retrieved: str
    final_url: str | None = None
    status: int | None = None
    content_type: str | None = None
    redirects: list[dict] = field(default_factory=list)  # [{"status": 301, "from": url, "to": url}, ...]
    failure: str | None = None
    source: dict | None = None  # ledger.sources.Source as a dict

    def to_dict(self) -> dict:
        return asdict(self)


def robots_allows(url: str, session: requests.Session | None = None) -> bool | None:
    """True/False from robots.txt; None if robots.txt could not be read (treated as allowed, and recorded)."""
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = (session or requests).get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            _robots[base] = rp
        except requests.RequestException:
            _robots[base] = None
    rp = _robots[base]
    return None if rp is None else rp.can_fetch(USER_AGENT, url)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_and_archive(url: str, root: Path, session: requests.Session | None = None) -> Retrieval:
    s = session or requests.Session()
    if robots_allows(url, s) is False:
        return Retrieval(url, False, utc_now(), failure="robots.txt disallows this page for our user agent")
    try:
        r = s.get(url, headers={"User-Agent": USER_AGENT}, timeout=45, allow_redirects=True)
    except requests.RequestException as error:
        return Retrieval(url, False, utc_now(), failure=f"{type(error).__name__}: {str(error)[:200]}")
    finally:
        time.sleep(1)
    retrieved = utc_now()
    hops = [{"status": h.status_code, "from": h.url, "to": h.headers.get("location", "")} for h in r.history]
    out = Retrieval(url, False, retrieved, final_url=r.url, status=r.status_code, content_type=r.headers.get("content-type"), redirects=hops)
    if r.url != url and robots_allows(r.url, s) is False:
        out.failure = "redirect target is disallowed by robots.txt; not archived"
        return out
    if r.status_code != 200:
        out.failure = f"HTTP {r.status_code}"
        return out
    if "html" not in (out.content_type or ""):
        out.failure = f"not an HTML page ({out.content_type})"
        return out
    try:
        src = sources.archive(r.content, r.url, "html", LICENSE, False, root=root)
    except Exception as error:  # lxml ParserError on empty documents, etc.
        out.failure = f"unreadable page: {type(error).__name__}"
        return out
    out.ok, out.source = True, {**src.to_dict(), "retrieved": retrieved}
    return out
