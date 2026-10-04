"""Trust policies: from reviews and evidence to what each view may show. See PLAN.md sections 4-5.

Two separate questions:
  claim review status  - is this claim faithful to its cited source? (decided by reviews)
  evidence state       - how well supported is the assertion? (computed from its claims)
"""

from collections import Counter

POLICY_VERSION = "policy@1"

SUPPORTING = {"supports", "supports_with_qualification"}


def family_key(family: str | None) -> str:
    """Historical OpenAI labels must not masquerade as independent reviewers."""
    value = (family or "").strip().lower()
    if value == "openai" or value.startswith(("openai-", "azure-openai", "gpt-")):
        return "openai"
    return value


def claim_review_status(reviews: list[dict]) -> str:
    """unreviewed | reviewed | independently_reviewed | human_reviewed | review_disagreement | rejected

    Independence counts reviewer kinds and model families, never prompts: two reviews from the
    same model family count once, whatever the prompt.
    """
    if not reviews:
        return "unreviewed"
    human = [r for r in reviews if r["reviewer_kind"] == "human"]
    if human:
        latest = human[-1]["verdict"]
        return "human_reviewed" if latest in SUPPORTING else "rejected"
    by_family: dict[str, str] = {}
    for r in reviews:  # latest verdict per model family
        by_family[family_key(r["model_family"]) or r["reviewer"]] = r["verdict"]
    support = sum(v in SUPPORTING for v in by_family.values())
    against = sum(v == "does_not_support" for v in by_family.values())
    if support and against:
        return "review_disagreement"
    if against or all(v == "out_of_scope" for v in by_family.values()):
        return "rejected"
    return "independently_reviewed" if support >= 2 else "reviewed"


def source_key(claim: dict) -> str:
    """What counts as one independent source: a paper, a trial record, a page, or a dataset record family."""
    keys = []
    for e in claim["evidence"]:
        if "source_id" in e:
            keys.append(e.get("pmid") or e["source_id"])
        elif e["type"] == "curated_database":
            keys.append(e["dataset"])
        elif e["type"] == "expert_statement":
            keys.append("expert:" + claim["provenance"]["contributor"])
        else:
            keys.append(e["type"])
    return "|".join(sorted(set(keys)))


def evidence_state(claims: list[tuple[dict, str, str]], contested: bool) -> dict:
    """claims: (claim body, origin, review status). Returns the assertion's evidence state."""
    curated = [c for c, origin, _ in claims if origin == "reference"]
    reviewed = [c for c, origin, status in claims if origin == "contributed" and status in ("independently_reviewed", "human_reviewed")]
    sources = {source_key(c) for c in curated + reviewed}
    evidence_types = Counter(e["type"] for c in curated + reviewed for e in c["evidence"])
    if contested:
        state = "contested"
    elif curated:
        state = "curated"
    elif len(sources) >= 2:
        state = "multiple_independent_sources"
    elif sources:
        state = "single_source"
    else:
        state = "unsupported"
    return {"state": state, "independent_sources": len(sources), "evidence_types": dict(evidence_types),
            "human_reviewed": any(status == "human_reviewed" for _, _, status in claims)}


# Risk tiers: how much review a contributed claim needs before the family view may show it.
DESCRIPTIVE = {"has_symptom", "has_asset", "has_name", "represented_by", "studied_by", "has_prevalence"}  # what a source reports
MECHANISTIC = {"causes", "has_variant_effect", "interacts_with", "part_of_complex", "in_pathway", "involved_in"}  # how biology works
THERAPEUTIC = {"tested_in"}  # anything about treatment effects


def visible(policy: str, origin: str, review_status: str, state: dict, predicate: str = "") -> bool:
    """Whether a claim belongs in a view (the projection then labels it; see PLAN.md section 5)."""
    if review_status in ("rejected", "review_disagreement") and policy != "research":
        return False
    if review_status == "rejected":
        return False
    if policy == "research":
        return True
    if origin == "reference":
        return True
    if policy == "family":
        if predicate in THERAPEUTIC:
            return review_status == "human_reviewed"
        if predicate in MECHANISTIC:
            return review_status in ("independently_reviewed", "human_reviewed")
        return review_status in ("reviewed", "independently_reviewed", "human_reviewed")
    if policy == "strict":
        return review_status == "human_reviewed"
    raise ValueError(f"unknown policy {policy!r}")


def family_label(origin: str, review_status: str, state: dict) -> str:
    """Plain-language status for the family view."""
    if state.get("state") == "contested":
        return "Contested: see both sides"
    if origin == "reference":
        return "From a curated database"
    if review_status == "human_reviewed":
        return "Reviewed by an expert"
    if review_status == "independently_reviewed":
        return "Checked by two independent AI reviewers"
    if review_status == "reviewed":
        return "Checked by an AI reviewer against its source"
    return "Not yet checked"
