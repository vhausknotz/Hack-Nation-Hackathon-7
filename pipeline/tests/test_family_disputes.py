import pytest

from ledger.tests.test_ledger import ledger, archive_root, agent, make_source, seizure_claim
from pipeline.family_disputes import dispute_index
from pipeline.project_collaboration import eligible


@pytest.mark.parametrize("predicate,subject,obj", [
    ("has_asset", "MONDO:0014590", "NCT12345678"),
    ("represented_by", "MONDO:0014590", "org:example"),
    ("same_organization_as", "org:alias", "org:example"),
])
@pytest.mark.parametrize("target_kind", ["claim", "assertion"])
def test_objections_are_shown_and_reviewed_counter_evidence_marks_contested(
        ledger, archive_root, tmp_path, predicate, subject, obj, target_kind):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    source = make_source(ledger, extractor, archive_root)
    claim = seizure_claim(source, extractor)
    # Deliberately synthetic semantics: this verifies publication policy, not biology.
    claim["assertion"] = {"subject": subject, "predicate": predicate, "object": obj, "qualifiers": {}}
    original = ledger.propose(claim, extractor)
    assert original.accepted
    human = agent(ledger, tmp_path, "human:test-reviewer", kind="human")
    ledger.review(original.claim_id, "supports", "Synthetic listing support", human)
    assert dispute_index(ledger.store) == {}

    skeptic = agent(ledger, tmp_path, "agent:skeptic")
    counter = ledger.propose(seizure_claim(source, skeptic), skeptic)
    target = original.claim_id if target_kind == "claim" else original.assertion_id
    objection = ledger.challenge(target, "Synthetic objection", skeptic, counter_claim=counter.claim_id)
    entry = dispute_index(ledger.store)[original.assertion_id]
    assert entry["status"] == "pending_review"
    assert entry["objections"][0]["reason"] == "Synthetic objection"
    assert entry["objections"][0]["counter"]["claim_id"] == counter.claim_id

    # Reviews from one model family do not make counter-evidence independent.
    for index, family in enumerate(["openai", "azure-openai"]):
        ledger.review(counter.claim_id, "supports", "Synthetic support", agent(ledger, tmp_path, f"agent:review-{index}"), model_family=family)
        assert dispute_index(ledger.store)[original.assertion_id]["status"] == "pending_review"
    ledger.review(counter.claim_id, "supports", "Synthetic support", agent(ledger, tmp_path, "agent:review-x"), model_family="test-independent")
    entry = dispute_index(ledger.store)[original.assertion_id]
    assert entry["status"] == "contested" and entry["objections"][0]["reviewed"]

    # Contested listings are not material for shared-research proposals.
    listing = {"type": "natural_history_study", "review": {"status": "human_reviewed", "verdict": "supports"}}
    assert eligible(listing) and not eligible({**listing, "dispute": entry})

    # A redacted objection disappears with its reason.
    ledger.redact(objection, "personal_data", human)
    assert dispute_index(ledger.store) == {}


def test_contested_identity_merge_is_not_applied(ledger, archive_root, tmp_path):
    from pipeline.project_actions import organization_aliases
    extractor = agent(ledger, tmp_path, "agent:extractor")
    source = make_source(ledger, extractor, archive_root)
    claim = seizure_claim(source, extractor)
    claim["assertion"] = {"subject": "org:alias", "predicate": "same_organization_as", "object": "org:example", "qualifiers": {}}
    merge = ledger.propose(claim, extractor)
    human = agent(ledger, tmp_path, "human:test-reviewer", kind="human")
    ledger.review(merge.claim_id, "supports", "Same organization", human)
    assert organization_aliases(ledger.store)["org:alias"][0] == "org:example"
    disputes = {merge.assertion_id: {"status": "contested", "objections": []}}
    assert "org:alias" not in organization_aliases(ledger.store, disputes)
