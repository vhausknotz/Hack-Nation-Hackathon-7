from pipeline.frontier import frontier, score


def condition(cid, n=0, prevalence=None, strength="strong"):
    return {"id": cid, "name": cid, "gene": {"symbol": "G" + cid, "strength": strength},
            "phenotypes": [{"id": f"HP:{i:07d}"} for i in range(n)], "prevalence": {"class": prevalence} if prevalence else None}


def test_requests_outrank_missing_data_and_reasons_are_words():
    conditions = {"a": condition("a", n=0), "b": condition("b", n=12)}
    rows = frontier(conditions, {}, {}, {"b": 3})
    assert rows[0]["condition_id"] == "b"
    assert "3 people asked for this" in rows[0]["why"]
    assert rows[1]["why"][0] == "no symptoms recorded"


def test_focus_follows_the_biggest_gap():
    full = {"communities": [{"kind": "patient_organization"}], "assets": [{"id": "NCT1"}]}
    assert score(condition("a", n=2))[2] == "symptoms"
    assert score(condition("a", n=9))[2] == "community"
    assert score(condition("a", n=9), {"communities": [{"kind": "patient_organization"}]})[2] == "studies"
    assert score(condition("a", n=9), full)[2] == "review"


def test_prevalence_genetic_certainty_and_recent_work():
    common, rare = score(condition("a", prevalence="1-5 / 10 000")), score(condition("a", prevalence="<1 / 1 000 000"))
    assert common[0] > rare[0] and "affects about 1–5 in 10,000 people" in common[1]
    shared = condition("a", prevalence="1-5 / 10 000")
    shared["other_genes_for_this_disease"] = ["HGNC:1"]
    assert score(shared)[0] == score(condition("a"))[0]
    assert score(condition("a", strength="limited"))[0] < score(condition("a"))[0]
    assert score(condition("a"), recent=True)[0] == score(condition("a"))[0] - 3


def test_known_variants_with_little_clinical_description():
    s, why, _ = score(condition("a", n=1), variants={"plp": 40})
    assert s == score(condition("a", n=1))[0] + 1
    assert any("40 disease-causing variants" in w for w in why)


def test_campaigns_buy_attention_with_a_stated_reason():
    plain, boosted = score(condition("a", n=9)), score(condition("a", n=9), campaign="SNARE neighborhood")
    assert boosted[0] == plain[0] + 4 and boosted[1][0] == "part of the campaign “SNARE neighborhood”"
    rows = frontier({"a": condition("a", n=9), "b": condition("b", n=9)}, {}, {}, {}, campaigns={"b": "SNARE neighborhood"})
    assert rows[0]["condition_id"] == "b" and rows[0]["campaign"] == "SNARE neighborhood"
