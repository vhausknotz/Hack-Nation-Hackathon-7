"""MONDO disease ontology: stable disease IDs, names, synonyms, cross-references and causal genes."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import RAW

_SYNONYM = re.compile(r'^"(.*)" (EXACT|RELATED|BROAD|NARROW)')
_XREF = re.compile(r"^(\S+)(?: \{(.*)\})?")
_HGNC = re.compile(r"identifiers\.org/hgnc/(\d+)")


@dataclass
class Disease:
    id: str
    name: str
    definition: str = ""
    synonyms: list[tuple[str, str]] = field(default_factory=list)  # (text, scope)
    xrefs: dict[str, list[str]] = field(default_factory=dict)  # "OMIM:612164" -> sources, e.g. ["MONDO:equivalentTo"]
    subsets: set[str] = field(default_factory=set)  # e.g. rare, gard_rare, nord_rare, orphanet_rare
    parents: list[str] = field(default_factory=list)
    genes: list[str] = field(default_factory=list)  # HGNC IDs ("HGNC:11444") with germline causal mutations

    def equivalent(self, prefix: str) -> list[str]:
        """Cross-references MONDO asserts as exact equivalents, e.g. equivalent("OMIM")."""
        return [x for x, src in self.xrefs.items() if x.startswith(prefix + ":") and "MONDO:equivalentTo" in src]

    @property
    def is_rare(self) -> bool:
        return "rare" in self.subsets


def load(path: Path = RAW / "mondo.obo") -> dict[str, Disease]:
    diseases: dict[str, Disease] = {}
    current: Disease | None = None
    obsolete = False
    in_term = False

    def flush():
        if current is not None and not obsolete and current.id.startswith("MONDO:"):
            diseases[current.id] = current

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("["):
                flush()
                in_term = line == "[Term]"
                current, obsolete = None, False
                continue
            if not in_term or not line or ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key == "id":
                current = Disease(id=value, name="")
            elif current is None:
                continue
            elif key == "name":
                current.name = value
            elif key == "def":
                current.definition = value.split('" [', 1)[0].strip('"')
            elif key == "is_obsolete" and value == "true":
                obsolete = True
            elif key == "synonym":
                m = _SYNONYM.match(value)
                if m:
                    current.synonyms.append((m.group(1), m.group(2)))
            elif key == "xref":
                m = _XREF.match(value)
                if m:
                    sources = re.findall(r'source="([^"]+)"', m.group(2) or "")
                    current.xrefs[m.group(1)] = sources
            elif key == "subset":
                current.subsets.add(value.split(" ", 1)[0])
            elif key == "is_a":
                current.parents.append(value.split(" ", 1)[0])
            elif key == "relationship" and value.startswith("has_material_basis_in_germline_mutation_in"):
                m = _HGNC.search(value)
                if m and f"HGNC:{m.group(1)}" not in current.genes:
                    current.genes.append(f"HGNC:{m.group(1)}")
        flush()
    return diseases


def xref_index(diseases: dict[str, Disease], prefixes: tuple[str, ...] = ("OMIM", "Orphanet")) -> dict[str, str]:
    """Map exact-equivalent external IDs to MONDO IDs. Orphanet IDs are also indexed as ORPHA:<n> (HPO's prefix)."""
    index: dict[str, str] = {}
    for d in diseases.values():
        for prefix in prefixes:
            for x in d.equivalent(prefix):
                index[x] = d.id
                if prefix == "Orphanet":
                    index["ORPHA:" + x.split(":", 1)[1]] = d.id
    return index
