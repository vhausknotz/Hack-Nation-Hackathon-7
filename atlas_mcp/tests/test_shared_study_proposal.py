import pytest
from tools.mcp_complete_shared_study import evidence_for


def source(criteria="Inclusion: a causative variant. Exclusion: pregnancy."):
    return {"source_id": "src:test", "text": "Title: Synthetic study\nOfficial title: Synthetic\nConditions: STXBP1; SYNGAP1\nKeywords: test\n"
            "Summary: A natural-history study.\nDetailed description: " + "long detail " * 300 +
            "\nStudy type: OBSERVATIONAL\nEligibility: " + criteria +
            "\nStudy population: Confirmed diagnoses\nMinimum age: 18 Years\nMaximum age: Not recorded\nSex: ALL\nHealthy volunteers: False"
            "\nInterventions: None\nPrimary outcomes: Development over time\nStatus: RECRUITING\nWhy stopped:\nRecord last updated: 2026-10-04"}


def test_long_description_does_not_overflow_quotes_and_eligibility_is_kept():
    record = source()
    evidence = evidence_for(record)
    for e in evidence:
        assert len(e["quote"]) <= 2000
        assert record["text"][e["start"]:e["end"]] == e["quote"]
    restriction = next(e["restriction"] for e in evidence if "restriction" in e)
    assert "Exclusion: pregnancy" in restriction and "Minimum age: 18 Years" in restriction
    assert "Study population: Confirmed diagnoses" in restriction


def test_excessive_eligibility_is_not_silently_truncated():
    with pytest.raises(ValueError, match="2000-character"):
        evidence_for(source("eligibility " * 250))
