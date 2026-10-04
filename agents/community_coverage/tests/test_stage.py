"""Offline tests for staging: saved HTML fixtures and a fake HTTP session. No network, models or production ledger."""

import json
from types import SimpleNamespace

import pytest

from agents.community_coverage import fetch, stage
from ledger import sources

PAGE = b"""<html><head><title>Example Foundation</title></head><body>
<nav>Menu</nav>
<p>The Example Foundation supports families living with Example syndrome.</p>
<p>Example syndrome is caused by changes in the EXA1 gene.</p>
</body></html>"""
QUOTE = "The Example Foundation supports families living with Example syndrome."


def spec(quote=QUOTE):
    return {"researcher_model": "test", "conditions": [{
        "id": "MONDO:0000001", "name": "EXA1-related Example syndrome", "gene": "EXA1", "why": "test",
        "candidates": [{"org_id": "org:example-org", "name": "Example Foundation", "homepage": "https://example.org/",
                        "org_type": "patient_organization", "scope": "this_condition", "rationale": "test",
                        "evidence": [{"url": "https://example.org/", "supports": "serves_condition", "quote": quote}]}]}]}


@pytest.fixture
def package(monkeypatch, tmp_path):
    monkeypatch.setattr(stage, "PACKAGE", tmp_path)
    monkeypatch.setattr(stage, "ARCHIVE", tmp_path / "archive")

    def fake_fetch(url, root, session=None):
        src = sources.archive(PAGE, url, "html", fetch.LICENSE, False, root=root)
        return fetch.Retrieval(url, True, "2026-10-04T00:00:00+00:00", final_url=url, status=200, source={**src.to_dict(), "retrieved": "2026-10-04T00:00:00+00:00"})

    monkeypatch.setattr(stage, "fetch_and_archive", fake_fetch)
    return tmp_path


def test_stage_locates_quote_offsets_and_verifies(package):
    manifest = stage.stage(spec())
    assert manifest["failures"] == [] and manifest["conditions"]["MONDO:0000001"]["outcome"] == "candidates"
    candidate = json.loads((package / "candidates.jsonl").read_text(encoding="utf-8"))
    ev = candidate["claim"]["evidence"][0]
    entry = manifest["sources"][ev["source_id"]]
    text = (package / entry["files"]["text"]).read_text(encoding="utf-8")
    assert text[ev["start"]:ev["end"]] == QUOTE
    assert stage.verify() == []


def test_quote_not_in_page_is_a_recorded_failure_not_a_repair(package):
    manifest = stage.stage(spec("The Example Foundation serves everyone."))
    assert manifest["candidates"] == {} and "not found verbatim" in manifest["failures"][0]["failure"]
    assert manifest["conditions"]["MONDO:0000001"]["outcome"] == "unresolved_gap"


def test_verify_catches_a_tampered_archive_and_offsets(package):
    manifest = stage.stage(spec())
    entry = next(iter(manifest["sources"].values()))
    text_file = package / entry["files"]["text"]
    text_file.write_text(text_file.read_text(encoding="utf-8") + "\nextra", encoding="utf-8")
    assert any("do not match their hashes" in p for p in stage.verify())
    text_file.write_text(text_file.read_text(encoding="utf-8").removesuffix("\nextra"), encoding="utf-8")
    assert stage.verify() == []
    rows = [json.loads(line) for line in (package / "candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0]["claim"]["evidence"][0]["start"] += 4
    (package / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert any("verbatim" in p for p in stage.verify())


def test_check_offsets_rules():
    text = "alpha beta   gamma"
    assert stage.check_offsets(text, 0, 5, "alpha") is None
    assert stage.check_offsets(text, 6, 18, "beta gamma") is None  # whitespace runs collapse, as in the kernel
    assert stage.check_offsets(text, 0, 5, "alpha!") is not None
    assert stage.check_offsets(text, 5, 5, "") is not None and stage.check_offsets(text, 0, 99, "alpha") is not None


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, **_):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return SimpleNamespace(status_code=404, text="", url=url, headers={}, history=[])
        return self.routes[url]


def reply(url, status=200, body=PAGE, ctype="text/html; charset=utf-8", history=()):
    return SimpleNamespace(status_code=status, url=url, content=body, headers={"content-type": ctype}, history=list(history))


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda *_: None)
    monkeypatch.setattr(fetch, "_robots", {})


def test_fetch_records_redirect_history_and_final_url(tmp_path):
    hop = SimpleNamespace(status_code=301, url="http://www.example.org/", headers={"location": "https://example.org/"})
    session = FakeSession({"http://www.example.org/": reply("https://example.org/", history=[hop])})
    got = fetch.fetch_and_archive("http://www.example.org/", tmp_path, session)
    assert got.ok and got.final_url == "https://example.org/"
    assert got.redirects == [{"status": 301, "from": "http://www.example.org/", "to": "https://example.org/"}]
    assert got.source["url"] == "https://example.org/" and got.source["redistributable"] is False


@pytest.mark.parametrize("response, failure", [
    (reply("https://example.org/", status=403, body=b""), "HTTP 403"),
    (reply("https://example.org/", ctype="application/pdf", body=b"%PDF"), "not an HTML page"),
])
def test_fetch_failures_are_recorded_not_archived(tmp_path, response, failure):
    got = fetch.fetch_and_archive("https://example.org/", tmp_path, FakeSession({"https://example.org/": response}))
    assert not got.ok and failure in got.failure and got.source is None
    assert not (tmp_path / "raw").exists()


def test_robots_disallow_is_never_fetched(tmp_path):
    class Blocking(FakeSession):
        def get(self, url, **kw):
            if url.endswith("/robots.txt"):
                return SimpleNamespace(status_code=200, text="User-agent: *\nDisallow: /", url=url, headers={}, history=[])
            return super().get(url, **kw)

    session = Blocking({})
    got = fetch.fetch_and_archive("https://example.org/private", tmp_path, session)
    assert not got.ok and "robots.txt" in got.failure and session.calls == []  # only robots.txt was requested; the page itself never was
