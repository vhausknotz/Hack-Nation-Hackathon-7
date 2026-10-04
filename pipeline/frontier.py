"""Impact frontier: which conditions agents should work on next, and why, in words.

The engine recomputes this every quarter hour and publishes it (live/evidence-frontier.json). The MCP task list and
the website's "what needs work" list both read it. The score is a transparent sum, not a model:
    requests from families or agents   strongest signal (diminishing: log2)
    missing data                       no symptoms recorded > few symptoms; no patient group; no studies
    how many people are affected       Orphanet prevalence class, when known
    genetic certainty                  well-established gene-disease links first (work there is less likely wasted)
    known variants, little clinical    many disease-causing ClinVar variants but few recorded symptoms
    recently expanded                  lower, so attention spreads
"""
import math

PREVALENCE = {"<1 / 1 000 000": 0.5, "1-9 / 1 000 000": 1.0, "1-9 / 100 000": 2.0, "1-5 / 10 000": 3.0, "6-9 / 10 000": 3.5, ">1 / 1000": 4.0}
PREVALENCE_WORDS = {"<1 / 1 000 000": "fewer than 1 in a million people", "1-9 / 1 000 000": "1–9 in a million people",
                    "1-9 / 100 000": "1–9 in 100,000 people", "1-5 / 10 000": "1–5 in 10,000 people",
                    "6-9 / 10 000": "6–9 in 10,000 people", ">1 / 1000": "more than 1 in 1,000 people"}
GOALS = {
    "symptoms": "Find published patient reports (PubMed) that describe this condition's clinical features. Submit has_symptom "
                "claims with exact quotes; use search_terms for the HPO term. Prefer case series over single reports.",
    "community": "Find a patient organization that serves people with this condition (or its gene). Archive its page with "
                 "fetch_page and submit represented_by with a quote that names the condition or gene.",
    "studies": "Find registered studies, natural-history studies or registries for this condition (ClinicalTrials.gov). "
               "Submit has_asset with quotes from the official record, including eligibility restrictions.",
    "review": "The basics are recorded. Look for missing names, prevalence or a gene-effect source, or review open findings.",
}


def score(c, actions=None, variants=None, requests=0, recent=False):
    """(score, reasons in plain words, focus) for one condition record from conditions.jsonl."""
    actions = actions or {}
    n = len(c.get("phenotypes") or [])
    groups = [o for o in actions.get("communities", []) if o.get("kind") == "patient_organization"]
    studies = actions.get("assets", [])
    total, why = 0.0, []
    if requests:
        total += 6 * math.log2(1 + requests)
        why.append(f"{requests} {'person' if requests == 1 else 'people'} asked for this")
    if n == 0:
        total += 4
        why.append("no symptoms recorded")
    elif n < 5:
        total += 2.5
        why.append(f"only {n} symptom{'' if n == 1 else 's'} recorded")
    if not groups:
        total += 1.5
        why.append("no patient group found yet")
    if not studies:
        total += 1
        why.append("no studies listed yet")
    klass = (c.get("prevalence") or {}).get("class")
    if klass in PREVALENCE:
        total += PREVALENCE[klass]
        why.append(f"affects about {PREVALENCE_WORDS[klass]}")
    strength = (c.get("gene") or {}).get("strength")
    total += {"definitive": 1.0, "strong": 1.0, "moderate": 0.5, "limited": -1.0}.get(strength, 0)
    plp = (variants or {}).get("plp", 0)
    if plp >= 20 and n < 5:
        total += 1
        why.append(f"{plp} disease-causing variants known, but little clinical description")
    if recent:
        total -= 3
        why.append("expanded recently")
    focus = "symptoms" if n < 5 else "community" if not groups else "studies" if not studies else "review"
    return round(total, 2), why, focus


def frontier(conditions, actions, variants, requests, recent=(), limit=200):
    rows = []
    recent = set(recent)
    for cid, c in conditions.items():
        s, why, focus = score(c, actions.get(cid), variants.get(cid), requests.get(cid, 0), cid in recent)
        rows.append({"condition_id": cid, "name": c["name"], "gene": c["gene"]["symbol"], "score": s, "why": why,
                     "focus": focus, "requests": requests.get(cid, 0)})
    rows.sort(key=lambda r: (-r["score"], r["condition_id"]))
    return rows[:limit]
