"""Human Phenotype Ontology: symptom terms, their hierarchy, and disease annotations."""

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from . import RAW

PURL = "http://purl.obolibrary.org/obo/"
PHENOTYPIC_ABNORMALITY = "HP:0000118"


@dataclass
class Term:
    id: str
    name: str
    definition: str = ""
    layperson: list[str] = field(default_factory=list)  # plain-language names, e.g. "Epilepsy"
    synonyms: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)


@dataclass
class Annotation:
    hpo_id: str
    frequency: str  # HP frequency term, "n/m" or "x%"; "" when unknown
    references: list[str]
    evidence: str  # IEA (inferred from electronic annotation), PCS (published clinical study), TAS (traceable author statement)


@dataclass
class DiseaseAnnotations:
    id: str  # OMIM:..., ORPHA:... or DECIPHER:...
    name: str
    phenotypes: dict[str, Annotation] = field(default_factory=dict)
    inheritance: set[str] = field(default_factory=set)
    course: set[str] = field(default_factory=set)  # clinical course incl. onset, e.g. HP:0003593 Infantile onset


def _curie(uri: str) -> str:
    return uri.removeprefix(PURL).replace("_", ":", 1)


class Ontology:
    def __init__(self, terms: dict[str, Term], alt_ids: dict[str, str]):
        self.terms = terms
        self.alt_ids = alt_ids

    def resolve(self, hpo_id: str) -> str | None:
        hpo_id = self.alt_ids.get(hpo_id, hpo_id)
        return hpo_id if hpo_id in self.terms else None

    @cache
    def ancestors(self, hpo_id: str) -> frozenset[str]:
        """The term itself plus every term above it."""
        out = {hpo_id}
        for parent in self.terms[hpo_id].parents:
            out |= self.ancestors(parent)
        return frozenset(out)

    def is_phenotypic_abnormality(self, hpo_id: str) -> bool:
        return PHENOTYPIC_ABNORMALITY in self.ancestors(hpo_id)

    def most_specific(self, hpo_ids: set[str]) -> set[str]:
        """Drop every term that is an ancestor of another term in the set."""
        redundant = set()
        for t in hpo_ids:
            redundant |= self.ancestors(t) - {t}
        return hpo_ids - redundant

    def label(self, hpo_id: str, plain: bool = False) -> str:
        term = self.terms[hpo_id]
        return term.layperson[0] if plain and term.layperson else term.name


def load_ontology(path: Path = RAW / "hp.json") -> Ontology:
    graph = json.loads(path.read_text(encoding="utf-8"))["graphs"][0]
    terms: dict[str, Term] = {}
    alt_ids: dict[str, str] = {}
    for node in graph["nodes"]:
        if node.get("type") != "CLASS" or "/HP_" not in node["id"]:
            continue
        meta = node.get("meta", {})
        if meta.get("deprecated"):
            continue
        term = Term(id=_curie(node["id"]), name=node.get("lbl", ""), definition=meta.get("definition", {}).get("val", ""))
        for syn in meta.get("synonyms", []):
            if syn.get("synonymType", "").endswith("#layperson"):
                term.layperson.append(syn["val"])
            else:
                term.synonyms.append(syn["val"])
        for prop in meta.get("basicPropertyValues", []):
            if prop["pred"].endswith("#hasAlternativeId"):
                alt_ids[prop["val"]] = term.id
        terms[term.id] = term
    for edge in graph["edges"]:
        child, parent = _curie(edge["sub"]), _curie(edge["obj"])
        if edge["pred"] == "is_a" and child in terms and parent in terms:
            terms[child].parents.append(parent)
    return Ontology(terms, alt_ids)


def load_annotations(ontology: Ontology, path: Path = RAW / "phenotype.hpoa") -> dict[str, DiseaseAnnotations]:
    """Disease -> annotated symptoms (aspect P), inheritance modes (I) and clinical course (C). Negated annotations are skipped."""
    diseases: dict[str, DiseaseAnnotations] = {}
    with open(path, encoding="utf-8") as f:
        header = None
        for line in f:
            if line.startswith("#"):
                continue
            row = line.rstrip("\n").split("\t")
            if header is None:
                header = row
                continue
            rec = dict(zip(header, row))
            if rec["qualifier"] == "NOT":
                continue
            hpo_id = ontology.resolve(rec["hpo_id"])
            if hpo_id is None:
                continue
            disease = diseases.setdefault(rec["database_id"], DiseaseAnnotations(rec["database_id"], rec["disease_name"]))
            if rec["aspect"] == "I":
                disease.inheritance.add(hpo_id)
            elif rec["aspect"] == "C":
                disease.course.add(hpo_id)
            elif rec["aspect"] == "P":
                refs = [r for r in rec["reference"].split(";") if r]
                existing = disease.phenotypes.get(hpo_id)
                if existing:
                    existing.references = sorted(set(existing.references) | set(refs))
                else:
                    disease.phenotypes[hpo_id] = Annotation(hpo_id, rec["frequency"], refs, rec["evidence"])
    return diseases
