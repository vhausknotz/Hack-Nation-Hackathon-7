"""Safe fetching of public organization pages for MCP contributors (patient groups, foundations, registries).

The gateway runs in Azure, so every address is checked before connecting: http(s) only, public IP
addresses only (re-checked on each redirect), HTML only, at most 2 MB, robots.txt respected. When a site
blocks automated visitors, the latest Internet Archive snapshot is used and labelled as historical.
Fetched text is untrusted data: it is archived and quoted, never followed as instructions.
"""
import ipaddress
import re
import socket
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "RareDiseaseAtlasBot/1.0 (+https://salmon-island-04aa8f603.1.azurestaticapps.net/agents)"
MAX_BYTES = 2_000_000
BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


def public_url(url):
    """Raise unless the URL is http(s) on a hostname that resolves only to public addresses."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use a public http(s) web address")
    host = parts.hostname.lower()
    if host in BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("That address is not a public website")
    if parts.port not in (None, 80, 443):
        raise ValueError("Only standard web ports are allowed")
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("That website's address could not be found") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError("That address is not a public website")
    return url


def get(url, max_redirects=4):
    """GET with manual redirects, each target re-validated. Returns (bytes, final_url) for HTML, else None."""
    for _ in range(max_redirects + 1):
        public_url(url)
        with requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=(10, 25),
                          allow_redirects=False, stream=True) as r:
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
                return None
            chunks, size = [], 0
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Page exceeds the 2 MB limit")
                chunks.append(chunk)
            return b"".join(chunks), url
    raise ValueError("Too many redirects")


def robots_allow(url):
    parts = urlparse(url)
    try:
        got = get(f"{parts.scheme}://{parts.netloc}/robots.txt")
    except (ValueError, requests.RequestException):
        return True
    if got is None:
        return True
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(got[0].decode("utf-8", "replace").splitlines())
    return rp.can_fetch(USER_AGENT, url)


def fetch_public_page(url):
    """(html, address read from, "live" | "archived_snapshot", content date)."""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    public_url(url)
    if robots_allow(url):
        try:
            got = get(url)
        except requests.RequestException:
            got = None
        if got:
            return got[0], got[1], "live", datetime.now(timezone.utc).date().isoformat()
    try:
        rows = requests.get("https://web.archive.org/cdx/search/cdx", params={"url": url, "output": "json", "limit": "-1",
                            "filter": "statuscode:200", "fl": "timestamp,original"}, headers={"User-Agent": USER_AGENT}, timeout=30).json()
    except (requests.RequestException, ValueError):
        rows = []
    if len(rows) < 2:
        raise ValueError("The page could not be read (blocked or unavailable) and has no Internet Archive copy")
    ts, original = rows[-1]
    got = get(f"https://web.archive.org/web/{ts}id_/{original}")
    if not got:
        raise ValueError("The archived copy could not be read")
    return got[0], f"https://web.archive.org/web/{ts}/{original}", "archived_snapshot", f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def org_id(homepage):
    host = (urlparse(homepage if "://" in homepage else "https://" + homepage).hostname or "").lower().removeprefix("www.")
    slug = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    return f"org:{slug}"[:84] if slug else None
