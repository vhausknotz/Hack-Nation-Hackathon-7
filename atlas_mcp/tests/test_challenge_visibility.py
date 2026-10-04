import json

import pytest

from atlas_mcp.cloud_publish import publish
from atlas_mcp.service import Atlas
from ledger.tests.test_ledger import (ledger, archive_root, agent, make_source,
                                      seizure_claim, FakeRegistry)


class Cloud:
    def __init__(self):
        self.objects = {}
        self.container = self

    def immutable(self, name, body):
        self.objects[name] = body

    def upload_blob(self, name, body, **_):
        self.objects[name] = body


@pytest.mark.parametrize("target_kind", ["claim", "assertion", "sibling_claim"])
def test_local_and_cloud_read_counter_evidence_without_promoting_unreviewed_objections(
        ledger, archive_root, tmp_path, target_kind):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    source = make_source(ledger, extractor, archive_root)
    original = ledger.propose(seizure_claim(source, extractor), extractor)
    skeptic = agent(ledger, tmp_path, "agent:skeptic")
    sibling = ledger.propose(seizure_claim(source, skeptic), skeptic)
    counter = ledger.propose(seizure_claim(source, skeptic, quote="All individuals had developmental delay"), skeptic)
    target = {"claim": original.claim_id, "assertion": original.assertion_id,
              "sibling_claim": sibling.claim_id}[target_kind]
    reason = "Synthetic objection: inspect this counter-claim"
    event = ledger.challenge(target, reason, skeptic, counter_claim=counter.claim_id)
    data = tmp_path / "data"
    data.mkdir()
    (data / "conditions.jsonl").write_text(json.dumps({"id": "MONDO:0014590", "name": "Test", "gene": {"symbol": "SNAP25"}})+"\n")
    atlas = Atlas(tmp_path / "intake", tmp_path / "ledger.db", data, registry_=FakeRegistry())

    def views():
        local = atlas.claim(original.claim_id)
        cloud = Cloud()
        manifest = publish(cloud, tmp_path / "ledger.db", data)
        hosted = json.loads(cloud.objects[manifest["prefix"]+"/claims/"+original.claim_id.split(":")[-1]+".json"])
        assert local == hosted
        return local

    view = views()
    assert view["review_status"] == "unreviewed"
    assert view["challenge_status"] == "pending_review"
    item = view["challenges"][0]
    assert item["reason"] == reason and item["counter_claim"] == counter.claim_id
    assert item["target"] == target and item["at"]
    assert not item["reviewed_counter_evidence"]
    for index, family in enumerate(["openai", "azure-openai", "test-independent"]):
        reviewer = agent(ledger, tmp_path, f"agent:reviewer-{index}")
        ledger.review(counter.claim_id, "supports", "Synthetic source review", reviewer, model_family=family)
        assert views()["challenge_status"] == ("contested" if index == 2 else "pending_review")
    assert views()["review_status"] == "unreviewed"  # counter-review never changes the original review
    moderator = agent(ledger, tmp_path, "human:moderator", kind="human")
    ledger.redact(event, "personal_data", moderator)
    assert views()["challenges"] == [] and views()["challenge_status"] == "none"
    assert reason not in json.dumps(views())


def test_missing_or_redacted_counter_cannot_make_a_claim_contested(ledger, archive_root, tmp_path):
    from atlas_mcp.challenge_view import challenge_view
    extractor = agent(ledger, tmp_path, "agent:extractor")
    source = make_source(ledger, extractor, archive_root)
    original = ledger.propose(seizure_claim(source, extractor), extractor)
    skeptic = agent(ledger, tmp_path, "agent:skeptic")
    counter = ledger.propose(seizure_claim(source, skeptic), skeptic)
    moderator = agent(ledger, tmp_path, "human:moderator", kind="human")
    ledger.review(counter.claim_id, "supports", "Synthetic review", moderator)
    ledger.challenge(original.claim_id, "Inspect the counter", skeptic, counter_claim=counter.claim_id)
    row = ledger.store.claim(original.claim_id)
    assert challenge_view(ledger.store, row)["challenge_status"] == "contested"
    proposed = next(e for e in ledger.store.events_for(counter.claim_id) if e["type"] == "claim.proposed")
    ledger.redact(proposed["id"], "personal_data", moderator)
    view = challenge_view(ledger.store, row)
    assert view["challenge_status"] == "pending_review"
    assert view["challenges"][0]["counter_claim_review_status"] == "unavailable"
