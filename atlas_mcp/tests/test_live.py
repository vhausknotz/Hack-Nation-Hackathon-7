"""Public live layer: presence, sanitized feed, overlay files and symptom-term search."""
import json
import os

import pytest

from atlas_mcp.terms import search
from atlas_mcp.tests.test_cloud_store import cloud  # noqa: F401  (Azurite fixture)

azurite = pytest.mark.skipif(os.getenv("ATLAS_TEST_AZURITE") != "1", reason="Local Azurite integration is opt-in")

TERMS = {"HP:0000365": ["Hearing impairment", "Hearing loss", "Deafness"],
         "HP:0002401": ["Stroke-like episode"],
         "HP:0003128": ["Lactic acidosis"],
         "HP:0004900": ["Severe lactic acidosis"]}


def test_term_search_prefers_exact_names_and_synonyms():
    assert search(TERMS, "hearing loss")[0]["id"] == "HP:0000365"
    assert search(TERMS, "stroke-like episodes") == [] or search(TERMS, "stroke-like episode")[0]["id"] == "HP:0002401"
    assert [t["id"] for t in search(TERMS, "lactic acidosis")][:2] == ["HP:0003128", "HP:0004900"]
    assert search(TERMS, "HP:0003128")[0]["name"] == "Lactic acidosis"
    with pytest.raises(ValueError):
        search(TERMS, "x")


class FakeAtlas:
    def condition(self, cid):
        return {"id": cid}

    def claim_task(self, tid):
        return {"id": tid}

    def get_activity_cursor(self):
        return 3


@azurite
def test_presence_and_feed_are_public_and_sanitized(cloud):  # noqa: F811
    from atlas_mcp.live import Feed, Presence
    store = cloud.store
    actor = cloud.enroll("gemini-scout", "gemini-2.5-pro", "google-gemini", "issuer|g")["id"]
    cloud.seed([{"id": "evidence:MONDO:0800037", "condition_id": "MONDO:0800037", "kind": "evidence"}])
    atlas = Presence(FakeAtlas(), store, actor)
    assert atlas.claim_task("evidence:MONDO:0800037") == {"id": "evidence:MONDO:0800037"}
    assert atlas.get_activity_cursor() == 3  # non-tool attributes pass through untouched
    cloud.claim("evidence:MONDO:0800037", actor)
    cloud.enqueue(actor, "evidence:MONDO:0800037", "claim", {"assertion": {"subject": "MONDO:0800037", "predicate": "has_symptom",
                  "object": "HP:0000365", "qualifiers": {}}, "evidence": [{"quote": "secret-ish payload"}], "prompt": "p@1"})
    cloud.post("agent:atlas-publisher", "MONDO:0800037", "published", {"new_connections": [{"id": "MONDO:1", "name": "x", "score": .5}]})
    feed = Feed(store, ttl=0)
    snap = feed.since(0)
    assert snap["presence"][0]["name"] == "gemini-scout"
    assert snap["presence"][0]["condition_id"] == "MONDO:0800037"
    assert snap["presence"][0]["doing"] == "taking on a task"
    stages = [e["stage"] for e in snap["events"]]
    assert stages == ["task_claimed", "queued", "published"]
    queued = snap["events"][1]
    assert queued["detail"] == {"kind": "claim", "predicate": "has_symptom", "object": "HP:0000365", "label": None}
    text = json.dumps(snap)
    assert "secret-ish" not in text and "issuer|g" not in text and "key_path" not in text
    # Incremental reads only return newer events, through the numeric seq column.
    last = snap["events"][-1]["seq"]
    cloud.post("agent:atlas-publisher", None, "rebuilding")
    assert [e["stage"] for e in feed.since(last)["events"]] == ["rebuilding"]


@azurite
def test_overlay_files_are_restricted_to_shard_paths(cloud):  # noqa: F811
    from atlas_mcp.live import Feed
    store = cloud.store
    store.container.upload_blob("live/v/0123456789abcdef/c/12.json", b'{"x":1}')
    feed = Feed(store)
    assert feed.overlay_file("0123456789abcdef/c/12.json") == b'{"x":1}'
    for bad in ("../private/keys/x.pem", "0123456789abcdef/../../x", "0123456789abcdef/c/12.json/../x", "zz/c/1.json"):
        assert feed.overlay_file(bad) is None


@azurite
def test_requests_count_each_visitor_once_and_show_on_the_feed(cloud):  # noqa: F811
    from atlas_mcp.live import Feed
    assert cloud.request_condition("MONDO:0800032", "v1") == {"count": 1, "new": True}
    assert cloud.request_condition("MONDO:0800032", "v1") == {"count": 1, "new": False}
    assert cloud.request_condition("MONDO:0800032", "v2")["count"] == 2
    assert cloud.requests() == {"MONDO:0800032": 2}
    for n in range(10):
        cloud.request_condition(f"MONDO:000001{n}", "v3")
    with pytest.raises(ValueError, match="limit"):
        cloud.request_condition("MONDO:0000099", "v3")
    events = Feed(cloud.store, ttl=0).since(0)["events"]
    requested = [e for e in events if e["stage"] == "requested"]
    assert requested[0]["condition_id"] == "MONDO:0800032" and requested[0]["agent"] == "visitor"
    assert "v1" not in json.dumps(events)


@azurite
def test_public_request_route_hashes_visitors(cloud):  # noqa: F811
    from atlas_mcp.live import Feed
    feed = Feed(cloud.store, ttl=0)
    assert feed.request("MONDO:0800032", "203.0.113.5")["count"] == 1
    assert feed.request("MONDO:0800032", "203.0.113.5")["new"] is False
    assert feed.request_count("MONDO:0800032") == 1
    row = cloud.store.get("request", "MONDO:0800032")
    assert "203.0.113.5" not in json.dumps(row) and len(row["visitors"][0]) == 16
    assert feed.frontier() == {"at": None, "conditions": []}


@azurite
def test_suspension_stops_new_work_with_its_reason(cloud):  # noqa: F811
    actor = cloud.enroll("noisy-agent", "m", "google-gemini", "issuer|n")["id"]
    cloud.seed([{"id": "evidence:MONDO:0800037", "condition_id": "MONDO:0800037", "kind": "evidence"}])
    profile = cloud.store.get("profile", actor)
    cloud.store.table.upsert_entity(cloud.store.entity("profile", actor, {**profile, "suspended": True, "suspended_reason": "quotes from unrelated papers"}))
    with pytest.raises(ValueError, match="unrelated papers"):
        cloud.claim("evidence:MONDO:0800037", actor)
    assert cloud.profile(actor)["id"] == actor  # the worker can still read it for already-submitted findings


@azurite
def test_expert_desk_needs_an_owner_grant_and_records_a_human_review(cloud):  # noqa: F811
    import time
    from atlas_mcp.expert import ExpertDesk
    desk = ExpertDesk(cloud)
    session = {"github_id": 42, "login": "Dr-Example", "expires": time.time() + 60}
    assert desk.actor(session) is None  # signing in alone grants nothing
    cloud.store.table.upsert_entity(cloud.store.entity("expertgrant", "dr-example", {"login": "dr-example", "credential": "Clinical geneticist, ORCID 0000-0000-0000-0001"}))
    actor = desk.actor(session)
    assert actor == "human:expert-dr-example" and desk.actor(session) == actor
    profile = cloud.profile(actor)
    assert profile["kind"] == "human" and profile["allow_review"] and profile["manifest"]["role"] == "human-expert"
    with pytest.raises(ValueError, match="reason"):
        desk.review(actor, "claim:sha256:" + "a" * 64, "MONDO:0800032", "supports", "ok")
    queued = desk.review(actor, "claim:sha256:" + "a" * 64, "MONDO:0800032", "does_not_support", "The quote is about a different variant class.")
    assert queued["state"] == "queued"
