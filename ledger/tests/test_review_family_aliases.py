from ledger.policy import claim_review_status


def review(family, verdict="supports"):
    return {"reviewer_kind": "model", "model_family": family, "reviewer": family, "verdict": verdict}


def test_openai_labels_do_not_count_as_independent_reviews():
    assert claim_review_status([review("openai-gpt6"), review("openai")]) == "reviewed"
    assert claim_review_status([review("openai"), review("openai-gpt6", "does_not_support")]) == "rejected"
    assert claim_review_status([review("openai-gpt6"), review("anthropic-claude")]) == "independently_reviewed"
