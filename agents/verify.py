"""Verifier: does the cited passage support the claim as stated? (GPT-6 Sol, a different model from the extractor)

It judges fidelity to the source, not biological truth. Verdicts: supports, supports_with_qualification,
does_not_support, out_of_scope.
"""

import json

from . import ROOT  # noqa: F401
import llm  # noqa: E402

VERIFY_MODEL = "gpt-6-sol"
VERIFY_PROMPT = "verify-symptom@1"
MODEL_FAMILY = "openai-gpt6"


def verify_symptom(condition: dict, hpo_term, claim: dict, source_text: str) -> dict:
    ev = claim["evidence"][0]
    reply = llm.chat_json(VERIFY_MODEL, [
        {"role": "system", "content": (
            "You check claims for a rare-disease evidence ledger. Judge ONLY whether the cited passage, read in the context "
            "of its abstract, supports the claim exactly as stated. Do not use outside knowledge. Verdicts: "
            "'supports'; 'supports_with_qualification' (true only in a narrower sense, e.g. a single patient or a related "
            "feature); 'does_not_support' (the passage says something else, is about other people, or the feature term is wrong); "
            "'out_of_scope' (not about this condition's patients). "
            'Return JSON {"verdict": "...", "reason": "<one sentence>"}.')},
        {"role": "user", "content": json.dumps({
            "condition": f"{condition['name']} (caused by {condition['gene']['symbol']} variants)",
            "claim": f"Patients with this condition have: {hpo_term.name} — {hpo_term.definition[:200]}",
            "certainty": claim["assertion"]["qualifiers"].get("certainty", "asserted"),
            "frequency": ev.get("frequency", ""),
            "cited_passage": ev["quote"],
            "abstract": source_text,
        }, ensure_ascii=False)},
    ], task=VERIFY_PROMPT)
    verdict = reply.get("verdict")
    if verdict not in ("supports", "supports_with_qualification", "does_not_support", "out_of_scope"):
        verdict = "out_of_scope"
    return {"verdict": verdict, "reason": reply.get("reason", "")[:500]}
