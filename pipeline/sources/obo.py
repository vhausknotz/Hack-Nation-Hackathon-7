"""Minimal OBO parser for ontologies where we only need IDs, names, namespaces and the is_a / part_of hierarchy."""

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path


@dataclass
class OboTerm:
    id: str
    name: str = ""
    namespace: str = ""
    parents: list[str] = field(default_factory=list)  # is_a and part_of targets
    alt_ids: list[str] = field(default_factory=list)


class Obo:
    def __init__(self, terms: dict[str, OboTerm]):
        self.terms = terms
        self.alt = {a: t.id for t in terms.values() for a in t.alt_ids}

    def resolve(self, term_id: str) -> str | None:
        term_id = self.alt.get(term_id, term_id)
        return term_id if term_id in self.terms else None

    @cache
    def ancestors(self, term_id: str) -> frozenset[str]:
        out = {term_id}
        for parent in self.terms[term_id].parents:
            if parent in self.terms:
                out |= self.ancestors(parent)
        return frozenset(out)


def load(path: Path, follow: tuple[str, ...] = ("part_of",)) -> Obo:
    terms: dict[str, OboTerm] = {}
    current: OboTerm | None = None
    obsolete = False

    def flush():
        if current is not None and not obsolete:
            terms[current.id] = current

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("["):
                flush()
                current, obsolete = (OboTerm(id="") if line == "[Term]" else None), False
                continue
            if current is None or ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key == "id":
                current.id = value
            elif key == "name":
                current.name = value
            elif key == "namespace":
                current.namespace = value
            elif key == "alt_id":
                current.alt_ids.append(value)
            elif key == "is_obsolete" and value == "true":
                obsolete = True
            elif key == "is_a":
                current.parents.append(value.split(" ", 1)[0])
            elif key == "relationship":
                rel, target = value.split(" ")[:2]
                if rel in follow:
                    current.parents.append(target)
        flush()
    return Obo(terms)
