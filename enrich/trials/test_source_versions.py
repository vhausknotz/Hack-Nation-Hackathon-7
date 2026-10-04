import pytest
from ledger.canonical import canonical_text, sha256
from enrich.trials import full_run, run


STUDY = {"protocolSection": {"identificationModule": {"nctId": "NCT12345678", "briefTitle": "Test"},
                          "eligibilityModule": {"minimumAge": "18 Years", "sex": "ALL"},
                          "outcomesModule": {"primaryOutcomes": [{"measure": "A specific outcome"}]}}}


def original(study):
    return canonical_text("\n".join(f"{k}: {v}" for k, v in run.study_fields(study)
                                   if k not in {"Minimum age", "Maximum age", "Sex", "Healthy volunteers"}))


def decision(text, with_hash=False):
    quote = "A specific outcome"
    start = text.index(quote)
    d = {"decision": {"quotes": [{"text": quote}]}, "span": [[start, start+len(quote)]]}
    if with_hash:
        d["source_text_sha256"] = sha256(text.encode())
    return d


def test_legacy_offsets_are_preserved_without_silent_source_upgrade():
    old, new = original(STUDY), run.render(STUDY)
    assert old.index("A specific outcome") != new.index("A specific outcome")
    assert full_run.decision_text(decision(old), STUDY) == (old, "original-v1")
    assert "Minimum age" not in old


def test_new_decisions_preserve_their_hash_and_structured_fields():
    text = run.render(STUDY)
    assert full_run.decision_text(decision(text, True), STUDY) == (text, "structured-eligibility-v2")
    assert "Minimum age: 18 Years" in text


def test_unknown_source_or_mismatched_offsets_stop_export():
    text = run.render(STUDY)
    d = decision(text, True)
    d["source_text_sha256"] = "unknown"
    with pytest.raises(ValueError, match="hash"):
        full_run.decision_text(d, STUDY)
    with pytest.raises(ValueError, match="offsets"):
        full_run.decision_text(decision(text), STUDY)


def test_legacy_export_explicitly_marks_missing_structured_eligibility():
    d = {"condition_id": "MONDO:0012812", "nct_id": "NCT12345678", "source_id": "src:test", "created": "2026-10-04",
         "source_rendering": "original-v1", "span": [[0, 5]], "status": "RECRUITING",
         "decision": {"asset_type": "registry", "restriction": "Existing restriction",
                      "quotes": [{"text": "STXBP1", "role": "population"}]}}
    claim = run.candidate_for(d)
    assert claim["evidence"][0]["restriction"].startswith("Existing restriction; Eligibility excerpt incomplete")
    d["source_rendering"] = "structured-eligibility-v2"
    d["structured_eligibility_incomplete"] = True
    assert "Eligibility excerpt incomplete" in run.candidate_for(d)["evidence"][0]["restriction"]
