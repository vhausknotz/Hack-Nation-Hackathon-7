"""Peer review: calibration qualifies reviewers; review tasks cross people and model families."""
import json
import os

import pytest

from atlas_mcp.tests.test_cloud_store import cloud  # noqa: F401

pytestmark = pytest.mark.skipif(os.getenv("ATLAS_TEST_AZURITE") != "1", reason="Local Azurite integration is opt-in")

CID = "claim:sha256:" + "a" * 64


class StubProjection:
    manifest, prefix = {}, "p"
    catalog = {"MONDO:0800032": {"id": "MONDO:0800032", "name": "MELAS", "gene": {"symbol": "MT-TL1"}, "phenotype_count": 11}}

    def read(self, name):
        if name == "review-frontier.json":
            return []
        raise ValueError("Record is not in this published MCP snapshot")


def setup_cloud(cloud):  # noqa: F811
    from atlas_mcp.cloud_service import CloudAtlas
    store = cloud.store
    codex = cloud.enroll("valentin-codex", "Codex", "openai", "github|42|client-a")["id"]
    chatgpt = cloud.enroll("valentin-chatgpt", "ChatGPT", "openai", "github|42|client-b")["id"]
    gemini = cloud.enroll("alex-gemini", "Gemini CLI", "google-gemini", "github|7|client-c")["id"]
    cases = [{"id": f"cal-{i}", "condition": "MELAS", "claim": "Patients have: seizures", "qualifiers": {}, "quote": "q",
              "source_context": None, "answer": "support" if i % 2 else "reject", "kind": "has_symptom"} for i in range(12)]
    store.container.upload_blob("live/calibration.json", json.dumps(cases).encode())
    record = {"claim_id": CID, "claim": {"assertion": {"subject": "MONDO:0800032", "predicate": "has_symptom", "object": "HP:0001250"},
              "evidence": [], "provenance": {"contributor": codex}}, "review_status": "reviewed", "reviews": []}
    store.container.upload_blob("live/claims/" + "a" * 64 + ".json", json.dumps(record).encode())
    store.container.upload_blob("live/review-frontier.json", json.dumps([{"claim_id": CID, "condition_id": "MONDO:0800032", "contributor": codex,
                                "reviewed_families": ["openai-gpt6"], "reviewers": ["agent:atlas-referee-sol"]}]).encode())
    atlas = lambda actor: CloudAtlas(cloud, StubProjection(), actor)
    return atlas, cases, codex, chatgpt, gemini


def qualify(atlas, cases, right=5):
    answers = {c["id"]: c["answer"] for c in cases}
    result = None
    for n in range(5):
        case = atlas.calibration_case()
        assert "answer" not in case and case["case_number"] == n + 1
        good = answers[case["case_id"]] == "support"
        if n >= right:
            good = not good
        result = atlas.submit_calibration(case["case_id"], "supports" if good else "does_not_support", "The quote states it plainly.")
    return result


def test_calibration_qualifies_and_review_tasks_cross_people(cloud):  # noqa: F811
    atlas, cases, codex, chatgpt, gemini = setup_cloud(cloud)
    g = atlas(gemini)
    assert [t for t in g.frontier("MONDO:0800032")["tasks"] if t["kind"] == "review"] == []  # not yet a reviewer
    result = qualify(g, cases, right=4)
    assert result["passed"] and result["score"] == 4
    assert cloud.profile(gemini)["allow_review"] is True
    g = atlas(gemini)
    reviews = [t for t in g.frontier("MONDO:0800032")["tasks"] if t["kind"] == "review"]
    assert reviews and reviews[0]["claim_id"] == CID
    g.claim_task(reviews[0]["id"])
    receipt = g.submit_review(reviews[0]["id"], CID, "supports", "The abstract reports seizures in these patients.", "review@1")
    assert receipt["state"] == "queued"
    stages = [e["stage"] for e in cloud.activity()]
    assert "reviewer_qualified" in stages


def test_same_person_cannot_review_their_other_agent(cloud):  # noqa: F811
    atlas, cases, codex, chatgpt, gemini = setup_cloud(cloud)
    c = atlas(chatgpt)
    assert qualify(c, cases)["passed"]
    c = atlas(chatgpt)
    assert [t for t in c.frontier("MONDO:0800032")["tasks"] if t["kind"] == "review"] == []  # Codex is the same GitHub person
    with pytest.raises(ValueError, match="different person"):
        c.submit_review("review:x", CID, "supports", "Looks right to me, honestly.", "p")


def test_failed_calibration_allows_one_retry_only(cloud):  # noqa: F811
    atlas, cases, codex, chatgpt, gemini = setup_cloud(cloud)
    g = atlas(gemini)
    assert qualify(g, cases, right=2)["passed"] is False
    assert qualify(g, cases, right=3)["passed"] is False
    with pytest.raises(ValueError, match="used up"):
        g.calibration_case()
    assert not cloud.profile(gemini)["allow_review"]
