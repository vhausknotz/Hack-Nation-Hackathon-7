import pytest

from ledger.tests.test_ledger import ledger, archive_root, agent, make_source, seizure_claim
from pipeline.family_disputes import check_family_disputes, ContestedFamilyEvidence


@pytest.mark.parametrize("predicate,subject,obj", [
    ("has_asset", "MONDO:0014590", "NCT12345678"),
    ("represented_by", "MONDO:0014590", "org:example"),
    ("same_organization_as", "org:alias", "org:example"),
])
@pytest.mark.parametrize("target_kind", ["claim", "assertion"])
def test_reviewed_dispute_stops_family_export_but_bare_objection_does_not(
        ledger, archive_root, tmp_path, monkeypatch, predicate, subject, obj, target_kind):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    source = make_source(ledger, extractor, archive_root)
    claim = seizure_claim(source, extractor)
    # Deliberately synthetic semantics: this verifies publication policy, not biology.
    claim["assertion"] = {"subject": subject, "predicate": predicate, "object": obj, "qualifiers": {}}
    original = ledger.propose(claim, extractor)
    assert original.accepted
    human = agent(ledger, tmp_path, "human:test-reviewer", kind="human")
    ledger.review(original.claim_id, "supports", "Synthetic listing support", human)
    skeptic = agent(ledger, tmp_path, "agent:skeptic")
    counter = ledger.propose(seizure_claim(source, skeptic), skeptic)
    target = original.claim_id if target_kind == "claim" else original.assertion_id
    objection = ledger.challenge(target, "Synthetic objection", skeptic, counter_claim=counter.claim_id)
    check_family_disputes(ledger.store)
    for index, family in enumerate(["openai", "azure-openai", "test-independent"]):
        reviewer = agent(ledger, tmp_path, f"agent:review-{index}")
        ledger.review(counter.claim_id, "supports", "Synthetic counter-evidence support", reviewer, model_family=family)
        if index < 2:
            check_family_disputes(ledger.store)
    with pytest.raises(ContestedFamilyEvidence, match="Family export stopped"):
        check_family_disputes(ledger.store)

    # Exercise the actual action-export entry point before it can replace bundles.
    from ledger import store
    from pipeline import project_actions
    real_store = store.Store
    (tmp_path / "data/ledger").mkdir(parents=True)
    (tmp_path / "data/ledger/ledger.db").touch()
    monkeypatch.setattr(project_actions, "ROOT", tmp_path)
    monkeypatch.setattr(store, "Store", lambda **_: real_store(tmp_path / "ledger.db", readonly=True))
    with pytest.raises(ContestedFamilyEvidence):
        project_actions.load_actions({})

    # Rejected listings are already excluded from ordinary family views.
    ledger.review(original.claim_id, "does_not_support", "Synthetic rejection", human)
    check_family_disputes(ledger.store)
    ledger.review(original.claim_id, "supports", "Synthetic restored support", human)
    with pytest.raises(ContestedFamilyEvidence):
        check_family_disputes(ledger.store)
    ledger.redact(objection, "personal_data", human)
    check_family_disputes(ledger.store)
