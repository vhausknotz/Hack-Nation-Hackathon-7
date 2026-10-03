"""HTTP GET/POST with an on-disk JSON cache in data/cache/http/, so reruns are free and reproducible."""

import hashlib
import json
import time
from pathlib import Path

import requests

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "http"
_last_call: dict[str, float] = {}


def _key(method: str, url: str, params: dict | None, body: dict | None) -> Path:
    raw = json.dumps([method, url, params or {}, body or {}], sort_keys=True)
    return CACHE / f"{hashlib.sha256(raw.encode()).hexdigest()[:32]}.json"


DEFAULT_HEADERS = {"User-Agent": "rare-disease-atlas (hackathon research)"}


def fetch_json(url: str, params: dict | None = None, body: dict | None = None, min_interval: float = 0.0,
               as_text: bool = False, headers: dict | None = None):
    """GET (or POST when body is given) and return parsed JSON (or text). min_interval throttles per host."""
    method = "POST" if body is not None else "GET"
    path = _key(method, url, params, body)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["data"]
    host = url.split("/")[2]
    wait = _last_call.get(host, 0) + min_interval - time.time()
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        r = requests.request(method, url, params=params, json=body, timeout=60, headers=headers or DEFAULT_HEADERS)
        _last_call[host] = time.time()
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        break
    data = r.text if as_text else r.json()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"method": method, "url": url, "params": params, "body": body, "retrieved": time.time(), "data": data}), encoding="utf-8")
    return data
