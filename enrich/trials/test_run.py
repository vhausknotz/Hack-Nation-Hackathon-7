"""Offline checks for rejection, reproducibility, budget, and resume boundaries."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import run as pilot


def study(nct="NCT01234567"):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": "STXBP1 natural history"},
        "descriptionModule": {"briefSummary": "This natural history study includes patients with pathogenic STXBP1 variants."},
        "designModule": {"studyType": "OBSERVATIONAL"},
        "statusModule": {"overallStatus": "TERMINATED", "whyStopped": "Stopping rule met."},
        "conditionsModule": {"conditions": ["STXBP1-related disorder"]},
    }}


def answer(quote="This natural history study includes patients with pathogenic STXBP1 variants."):
    return {"relevance": "direct", "asset_type": "natural_history_study", "modality": None,
            "quotes": [{"role": "both", "text": quote}], "restriction": None, "secondary_types": [],
            "reason": "The study explicitly includes pathogenic STXBP1 variants."}


def test_non_verbatim_and_empty_quotes_cannot_emit_candidates():
    text = pilot.render(study())
    assert pilot.validate_decision(answer(), text) is not None
    assert pilot.validate_decision(answer("Patients with pathogenic SNAP25 variants are eligible."), text) is None
    assert pilot.validate_decision(answer(""), text) is None
    assert pilot.validate_decision(answer("a" * 2001), "a" * 2001) is None


def test_invalid_model_output_is_rejected():
    bad = answer()
    bad["asset_type"] = "cure"
    with pytest.raises(ValueError, match="asset type"):
        pilot.validate_decision(bad, pilot.render(study()))
    bad = answer()
    bad["relevance"] = "not_relevant"
    with pytest.raises(ValueError, match="Negative"):
        pilot.validate_decision(bad, pilot.render(study()))


def test_renderer_preserves_termination_and_is_order_independent():
    original = study()
    reordered = {"protocolSection": dict(reversed(list(original["protocolSection"].items())))}
    assert pilot.render(original) == pilot.render(reordered)
    assert "Status: TERMINATED" in pilot.render(original)
    assert "Why stopped: Stopping rule met." in pilot.render(original)


def test_budget_reserves_output_before_spending():
    with pytest.raises(RuntimeError, match="budget stop"):
        pilot.budget_allowance([{"content": "x" * 5000}], 1200, 1.9999, 2)
    pilot.budget_allowance([{"content": "small"}], 1200, 0, 2)


def test_queries_omit_generic_names_and_keep_specific_phenotype():
    condition = {"gene": "NSF", "name": "Developmental and epileptic encephalopathy 96",
                 "disease_name": "developmental and epileptic encephalopathy 96",
                 "also_known_as": ["epilepsy", "DEE96", "neurodevelopmental disorder"]}
    assert list(pilot.queries_for(condition)) == [
        ("query.term", "NSF"), ("query.cond", '"Developmental and epileptic encephalopathy 96"')]


def test_balanced_sample_is_reproducible_and_unique():
    decisions = [{"id": i, "candidate": i < 20} for i in range(60)]
    sample = pilot.review_sample(decisions)
    assert sample == pilot.review_sample(decisions)
    assert sample == pilot.review_sample(list(reversed(decisions)))
    assert len(sample) == len({d["id"] for d in sample}) == 30
    assert sum(d["candidate"] for d in sample) == 15


@pytest.mark.parametrize("matches", [True, False])
def test_resume_avoids_second_model_call_and_detects_changed_prompt(tmp_path, monkeypatch, matches):
    output = tmp_path
    pilot.configure(output)
    condition = {"id": "MONDO:0014590", "gene": "STXBP1", "name": "STXBP1-related disorder"}
    if not matches:
        condition.update(gene="NOMATCH7", name="An unmentioned disease")
    pilot.write_json(output / "manifest.json", {"collection_complete": True})
    pilot.write_jsonl(output / "conditions.jsonl", [condition])
    pilot.write_jsonl(output / "pairs.jsonl", [{"condition_id": condition["id"], "nct_id": "NCT01234567", "queries": []}])
    record = study()
    source = pilot.archive(pilot.render(record).encode(), "https://clinicaltrials.gov/study/NCT01234567",
                           "text", "ClinicalTrials.gov (public domain)", True, root=output / "archive")
    pilot.write_jsonl(output / "sources.jsonl", [source.to_dict()])
    pilot.write_json(output / "source_index.json", {"NCT01234567": source.source_id})
    pilot.write_json(output / "studies/NCT01234567.json", record)
    calls = []
    monkeypatch.setattr(pilot.llm, "chat", lambda *a, **kw: (calls.append(1) or json.dumps(answer())))
    args = type("Args", (), {"output": output, "pilot_budget": 2})()
    pilot.screen(args)
    pilot.screen(args)
    assert len(calls) == int(matches)
    decisions = pilot.read_jsonl(output / "decisions.jsonl")
    assert len(decisions) == 1 and decisions[0]["candidate"] == matches
    if matches:
        claim = pilot.candidate_for(decisions[0])
        assert claim["assertion"]["qualifiers"]["status"] == "TERMINATED"
        assert pilot.Kernel(None, None).check_schema(claim).passed
    else:
        assert decisions[0]["stage"] == "prefilter"
    monkeypatch.setattr(pilot, "SYSTEM", pilot.SYSTEM + "New instruction")
    with pytest.raises(ValueError, match="Prompt or source changed"):
        pilot.screen(args)
    assert len(calls) == int(matches)


def test_gene_split_conditions_keep_distinct_model_inputs():
    a = {"id": "MONDO:0007163", "name": "Episodic ataxia type 2", "gene": "CACNA1A"}
    b = {"id": "MONDO:0020756", "name": "Familial hemiplegic migraine 1", "gene": "CACNA1A"}
    assert pilot.messages_for(a, "same study") != pilot.messages_for(b, "same study")


def test_empty_response_gets_one_bounded_audited_retry(tmp_path, monkeypatch):
    pilot.configure(tmp_path)
    replies = iter(["", json.dumps(answer())])
    caps = []
    def chat(*args, **kwargs):
        caps.append(kwargs["max_completion_tokens"])
        return next(replies)
    monkeypatch.setattr(pilot.llm, "chat", chat)
    result, span, error, attempts = pilot.screen_record([], pilot.render(study()), 2)
    assert result["relevance"] == "direct" and span is not None and error is None
    assert caps == [1200, 4096]
    assert attempts[0]["raw_output"] == "" and attempts[0]["validation_error"]


def test_unaccounted_usage_blocks_new_calls(tmp_path, monkeypatch):
    pilot.configure(tmp_path)
    pilot.write_jsonl(pilot.llm.USAGE, [{"input_tokens": None, "output_tokens": None}])
    monkeypatch.setattr(pilot.llm, "chat", lambda *a, **kw: pytest.fail("Must not call model"))
    with pytest.raises(RuntimeError, match="Missing token"):
        pilot.screen_record([], "text", 2)


@pytest.mark.parametrize("query_limit, expected_pairs, truncated, pages", [(1, 2, True, 1), (2, 4, False, 2)])
def test_paging_dedup_and_truncation_are_auditable(tmp_path, monkeypatch, query_limit, expected_pairs, truncated, pages):
    output = tmp_path / "output"
    pilot.configure(output)
    monkeypatch.setattr(pilot, "GENES", ["STXBP1"])
    monkeypatch.setattr(pilot, "queries_for", lambda c: [("query.term", "STXBP1")])
    conditions = tmp_path / "input.jsonl"
    pilot.write_jsonl(conditions, [
        {"id": "MONDO:0012812", "name": "One phenotype", "gene": {"symbol": "STXBP1"}},
        {"id": "MONDO:0014590", "name": "Another phenotype", "gene": {"symbol": "STXBP1"}},
    ])
    calls = []
    def fetch(url, params, **kwargs):
        calls.append(dict(params))
        payload = {"totalCount": 2, "studies": [study("NCT01234568")]} if "pageToken" in params else {
            "totalCount": 2, "studies": [study()], "nextPageToken": "second-page"}
        pilot.write_json(pilot.http_cache._key("GET", url, params, None), {"retrieved": 1700000000, "data": payload})
        return payload
    monkeypatch.setattr(pilot.http_cache, "fetch_json", fetch)
    args = type("Args", (), {"output": output, "conditions": conditions, "query_limit": query_limit})()
    pilot.collect(args)
    assert len(calls) == pages  # repeated gene query shared by both phenotype records
    assert len(pilot.read_jsonl(output / "pairs.jsonl")) == expected_pairs
    query = pilot.read_jsonl(output / "queries.jsonl")[0]
    assert query["truncated"] == truncated and query["total_count"] == 2
    pilot.collect(args)
    assert len(calls) == pages  # frozen complete collection makes no new API requests


def test_screening_context_cannot_leak_mechanism_annotations():
    condition = {"id": "MONDO:0013388", "gene": "SCN2A", "name": "SCN2A encephalopathy",
                 "variant_effect": "loss_of_function", "inheritance": ["dominant"], "mechanism": "gene dosage"}
    messages = pilot.messages_for(condition, "study")
    context = json.loads(messages[1]["content"])["condition"]
    assert "variant_effect" not in context and "inheritance" not in context and "mechanism" not in context
    assert "loss_of_function" not in messages[1]["content"]


def test_prefilter_requires_whole_words_and_accepts_name_synonyms():
    c = {"gene": "SCN2A", "name": "Rare syndrome", "also_known_as": ["DEE 11"]}
    assert pilot.has_mention(c, "SCN2A-related disorder")
    assert pilot.has_mention(c, "People with DEE\n11")
    assert not pilot.has_mention(c, "SCN2A1 and XSCN2A")
    assert pilot.has_mention({"gene": "SYT1", "name": "Baker-Gordon syndrome"}, "Baker Gordon Syndrome natural history")


def test_excerpt_keeps_late_gene_and_population_restriction():
    record = study()
    record["protocolSection"]["eligibilityModule"] = {
        "eligibilityCriteria": "Inclusion criteria: " + "OTHERGENE, " * 250 + "STXBP1 pathogenic variants",
        "studyPopulation": "Participants must have a movement disorder."}
    record["protocolSection"]["outcomesModule"] = {"primaryOutcomes": [{"measure": "CSF biomarkers"}]}
    excerpt, truncated = pilot.screening_excerpt({"gene": "STXBP1", "name": "STXBP1 disorder"}, record)
    assert "Eligibility" in truncated
    assert "STXBP1 pathogenic variants" in excerpt
    assert "Participants must have a movement disorder." in excerpt
    assert "CSF biomarkers" in excerpt
    assert len(excerpt) < len(pilot.render(record))


def test_two_evidence_quotes_keep_roles_restriction_and_full_archive_offsets():
    text = "Eligibility: STXBP1 variants and a movement disorder.\nTitle: Natural history study."
    result = answer()
    result.update(quotes=[{"role": "population", "text": "Eligibility: STXBP1 variants and a movement disorder."},
                          {"role": "asset_type", "text": "Title: Natural history study."}], restriction="Requires a movement disorder")
    spans = pilot.validate_decision(result, text)
    decision = {"decision": result, "span": spans, "condition_id": "MONDO:0012812", "nct_id": "NCT01234567",
                "source_id": "src:test", "created": "2026-10-03T00:00:00Z", "status": "RECRUITING", "truncated_fields": ["Eligibility"]}
    claim = pilot.candidate_for(decision)
    assert len(claim["evidence"]) == 2 and pilot.Kernel(None, None).check_schema(claim).passed
    for evidence in claim["evidence"]:
        assert "Requires a movement disorder" in evidence["restriction"]
        assert "incomplete" in evidence["restriction"]
        assert text[evidence["start"]:evidence["end"]] == evidence["quote"]
    result["quotes"][1]["text"] = "Invented study type"
    assert pilot.validate_decision(result, text) is None


def test_positive_quote_roles_must_cover_both_decisions():
    result = answer()
    result["quotes"][0]["role"] = "population"
    with pytest.raises(ValueError, match="population and asset"):
        pilot.validate_decision(result, pilot.render(study()))


def test_only_detail_mention_is_preserved_as_fallback_excerpt():
    record = study()
    record["protocolSection"]["descriptionModule"]["detailedDescription"] = "The study is supported by National Science Foundation (NSF)."
    excerpt, _ = pilot.screening_excerpt({"gene": "NSF", "name": "DEE96"}, record)
    assert "National Science Foundation (NSF)" in excerpt
    assert "Other archived excerpt:" in excerpt


def test_population_quote_cannot_omit_the_target_condition():
    result = answer("This natural history study includes participants with movement disorders.")
    with pytest.raises(ValueError, match="explicitly name"):
        pilot.validate_decision(result, result["quotes"][0]["text"], {"gene": "CACNA1A", "name": "Episodic ataxia type 2"})


def test_population_quote_accepts_explicit_numbered_alias_lists():
    c = {"gene": "CACNA1A", "name": "Spinocerebellar ataxia type 6", "also_known_as": ["SCA6"]}
    assert pilot.quote_has_target(c, "Clinical diagnosis of SCA 6")
    assert pilot.quote_has_target(c, "Genetic confirmation of SCA 1, 2, 3, 6, 7")
    assert not pilot.quote_has_target(c, "Genetic confirmation of SCA 1, 2, 3, 16, 27")


def test_broad_alias_does_not_prove_gene_defined_population():
    c = {"gene": "GABRB3", "name": "Developmental and epileptic encephalopathy 43", "also_known_as": ["Lennox-Gastaut syndrome"]}
    assert not pilot.quote_has_target(c, "Participants with Lennox-Gastaut syndrome or another DEE")
    assert pilot.quote_has_target(c, "Participants with GABRB3-related epilepsy")
    assert pilot.quote_has_target({**c, "name": "Lennox-Gastaut syndrome"}, "Participants with Lennox-Gastaut syndrome")


def test_compact_negative_omissions_need_no_formatting_retry(tmp_path, monkeypatch):
    pilot.configure(tmp_path)
    reply = {"relevance": "not_relevant", "reason": "Unrelated population."}
    calls = []
    monkeypatch.setattr(pilot.llm, "chat", lambda *a, **kw: (calls.append(1) or json.dumps(reply)))
    result, _, error, attempts = pilot.screen_record([], "Unrelated population.", 2)
    assert error is None and result['asset_type'] is None and result['secondary_types'] == []
    assert len(calls) == len(attempts) == 1
    assert pilot.normalize_decision({"relevance": "direct"}) == {"relevance": "direct"}
