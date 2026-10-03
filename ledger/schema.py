"""Claim schema: what a claim may say, about what, with which evidence.

A claim = assertion (subject, predicate, object, qualifiers) + evidence + provenance.
  assertion id = hash of the canonical assertion (many claims can support one assertion)
  claim id     = hash of the canonical claim (assertion + evidence + provenance)
See PLAN.md section 1.
"""

import re
from dataclasses import dataclass

from .canonical import content_id

# ---- entity kinds, recognized by ID shape ----------------------------------------------------------
KIND_PATTERNS: dict[str, re.Pattern] = {
    "condition": re.compile(r"^MONDO:\d{7}(-HGNC:\d+)?$"),
    "gene": re.compile(r"^HGNC:\d+$"),
    "phenotype": re.compile(r"^HP:\d{7}$"),
    "go_term": re.compile(r"^GO:\d{7}$"),
    "complex": re.compile(r"^CPX-\d+$"),
    "pathway": re.compile(r"^R-HSA-\d+$"),
    "effect": re.compile(r"^effect:(loss_of_function|gain_of_function|dominant_negative|non_loss_of_function)$"),
    "trial": re.compile(r"^NCT\d{8}$"),
    "publication": re.compile(r"^PMID:\d+$"),
    "organization": re.compile(r"^org:[a-z0-9][a-z0-9-]{1,80}$"),
    "person": re.compile(r"^(orcid:\d{4}-\d{4}-\d{4}-\d{3}[\dX]|person:[a-z0-9][a-z0-9-]{1,80})$"),
    "asset": re.compile(r"^asset:[a-z0-9][a-z0-9-]{1,120}$"),
    "intervention": re.compile(r"^intervention:[a-z0-9][a-z0-9-]{1,80}$"),
}


def kind_of(entity: str) -> str | None:
    for kind, pattern in KIND_PATTERNS.items():
        if pattern.match(entity):
            return kind
    return None


@dataclass(frozen=True)
class Predicate:
    subjects: tuple[str, ...]
    objects: tuple[str, ...]  # "text" = free text literal
    qualifiers: tuple[str, ...] = ()
    description: str = ""


PREDICATES: dict[str, Predicate] = {
    "causes": Predicate(("gene",), ("condition",), ("inheritance",), "Germline variants in the gene cause the condition"),
    "has_variant_effect": Predicate(("condition",), ("effect",), ("gene", "variant_class"), "How the causal gene change acts in this condition"),
    "has_symptom": Predicate(("condition",), ("phenotype",), ("frequency", "onset", "population", "evidence_level"), "Patients with the condition show this feature"),
    "has_name": Predicate(("condition",), ("text",), ("name_type", "naming_source"), "A name used for the condition"),
    "part_of_complex": Predicate(("gene",), ("complex",), (), "The gene's protein is part of the complex"),
    "in_pathway": Predicate(("gene",), ("pathway",), (), "The gene's protein acts in the pathway"),
    "involved_in": Predicate(("gene",), ("go_term",), (), "The gene's protein is involved in the process or located in the compartment"),
    "interacts_with": Predicate(("gene",), ("gene",), ("score", "species", "evidence_level"), "The two proteins physically interact"),
    "has_asset": Predicate(("condition",), ("trial", "asset"), ("asset_type", "status"), "A registry, study, model, biomarker, outcome measure, biorepository, program or trial relevant to the condition"),
    "represented_by": Predicate(("condition",), ("organization",), (), "A patient organization serves this community"),
    "studied_by": Predicate(("condition",), ("person",), ("role",), "A researcher or clinician works on the condition"),
    "tested_in": Predicate(("intervention",), ("condition",), ("species", "model_system", "evidence_level", "outcome"), "An intervention was tested for the condition"),
    "has_prevalence": Predicate(("condition",), ("text",), ("prevalence_kind", "geography"), "How common the condition is"),
}

QUALIFIER_VALUES: dict[str, set[str] | None] = {  # None = free text
    "inheritance": None,
    "gene": None,  # validated as a gene ID by the kernel
    "variant_class": {"missense", "truncating", "splice", "deletion", "duplication", "any"},
    "frequency": None,
    "onset": None,
    "population": None,
    "evidence_level": {"clinical", "case_report", "preclinical", "in_vitro", "computational", "curated"},
    "species": {"human", "mouse", "rat", "zebrafish", "fly", "worm", "yeast", "cell"},
    "model_system": None,
    "outcome": {"improved", "no_effect", "worsened", "mixed", "unknown"},
    "name_type": {"preferred", "curated_name", "synonym", "obsolete_label"},
    "naming_source": None,
    "score": None,
    "asset_type": {"registry", "natural_history_study", "model", "biomarker", "outcome_measure", "biorepository", "therapy_program", "trial", "guideline"},
    "status": None,
    "role": None,
    "prevalence_kind": None,
    "geography": None,
}

# ---- evidence -----------------------------------------------------------------------------------------
TEXT_EVIDENCE = {"publication_text", "trial_record", "organization_page", "community_report"}
EVIDENCE_FIELDS: dict[str, set[str]] = {
    # quoted from an archived source
    "publication_text": {"source_id", "quote", "start", "end"},
    "trial_record": {"source_id", "quote", "start", "end"},
    "organization_page": {"source_id", "quote", "start", "end"},
    "community_report": {"source_id", "quote", "start", "end"},
    # a record in a pinned reference dataset
    "curated_database": {"dataset", "dataset_hash", "record"},
    # derived by a declared recipe from pinned inputs
    "computed": {"recipe", "inputs"},
    # a signed statement by a human expert
    "expert_statement": {"statement"},
}

REVIEW_VERDICTS = {"supports", "supports_with_qualification", "does_not_support", "out_of_scope"}


def assertion_of(claim: dict) -> dict:
    a = claim["assertion"]
    return {"subject": a["subject"], "predicate": a["predicate"], "object": a["object"], "qualifiers": a.get("qualifiers", {})}


def assertion_id(claim_or_assertion: dict) -> str:
    a = claim_or_assertion.get("assertion", claim_or_assertion)
    return content_id("assertion", {"subject": a["subject"], "predicate": a["predicate"], "object": a["object"], "qualifiers": a.get("qualifiers", {})})


def claim_id(claim: dict) -> str:
    return content_id("claim", {k: claim[k] for k in ("assertion", "evidence", "provenance")})


def make_claim(subject: str, predicate: str, obj: str, evidence: list[dict], provenance: dict, **qualifiers) -> dict:
    return {
        "assertion": {"subject": subject, "predicate": predicate, "object": obj, "qualifiers": {k: v for k, v in qualifiers.items() if v not in (None, "")}},
        "evidence": evidence,
        "provenance": provenance,
    }
