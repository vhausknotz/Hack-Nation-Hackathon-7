"""Pinned identifier registry: which IDs exist, in which dataset versions.

The kernel only accepts IDs that exist in the pinned ontology and database files in data/raw/.
Each file's SHA-256 is part of the registry version, so a check always says exactly what it was
checked against.
"""

import csv
import gzip
import hashlib
import json
import re
from functools import cached_property
from pathlib import Path

from . import ROOT

RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache" / "registry"


def file_hash(path: Path) -> str:
    """SHA-256 of a file, cached by (size, mtime) so large files are hashed once."""
    stat = path.stat()
    CACHE.mkdir(parents=True, exist_ok=True)
    marker = CACHE / f"{path.name}.{stat.st_size}.{int(stat.st_mtime)}.sha256"
    if marker.exists():
        return marker.read_text()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    value = "sha256:" + h.hexdigest()
    marker.write_text(value)
    return value


class Registry:
    FILES = {
        "mondo": "mondo.obo",
        "hgnc": "hgnc_complete_set.txt",
        "hpo": "hp.json",
        "go": "go-basic.obo",
        "complexes": "complexportal_human.tsv",
        "reactome": "reactome_pathways.txt",
    }

    def __init__(self, raw: Path = RAW):
        self.raw = raw

    @cached_property
    def versions(self) -> dict[str, str]:
        return {name: file_hash(self.raw / file) for name, file in self.FILES.items()}

    @cached_property
    def version(self) -> str:
        return "registry:" + hashlib.sha256(json.dumps(self.versions, sort_keys=True).encode()).hexdigest()[:16]

    def dataset_hash(self, file: str) -> str:
        return file_hash(self.raw / file)

    def _ids(self, file: str, pattern: str) -> frozenset[str]:
        text = (self.raw / file).read_text(encoding="utf-8")
        return frozenset(re.findall(pattern, text))

    @cached_property
    def mondo(self) -> frozenset[str]:
        return self._ids("mondo.obo", r"(?m)^id: (MONDO:\d{7})$")

    @cached_property
    def hpo(self) -> frozenset[str]:
        return frozenset(i.replace("_", ":") for i in self._ids("hp.json", r'"http://purl.obolibrary.org/obo/(HP_\d{7})"'))

    @cached_property
    def go(self) -> frozenset[str]:
        return self._ids("go-basic.obo", r"(?m)^(?:id|alt_id): (GO:\d{7})$")

    @cached_property
    def hgnc(self) -> frozenset[str]:
        with open(self.raw / "hgnc_complete_set.txt", encoding="utf-8") as f:
            return frozenset(r["hgnc_id"] for r in csv.DictReader(f, delimiter="\t") if r["status"] == "Approved")

    @cached_property
    def complexes(self) -> frozenset[str]:
        return self._ids("complexportal_human.tsv", r"(?m)^(CPX-\d+)\t")

    @cached_property
    def pathways(self) -> frozenset[str]:
        return self._ids("reactome_pathways.txt", r"(?m)^(R-HSA-\d+)\t")

    def exists(self, kind: str, entity: str) -> bool | None:
        """True/False for kinds with a pinned registry; None when the kind has no registry (e.g. NCT IDs)."""
        if kind == "condition":
            mondo, _, gene = entity.partition("-")
            return mondo in self.mondo and (not gene or gene in self.hgnc)
        table = {"gene": "hgnc", "phenotype": "hpo", "go_term": "go", "complex": "complexes", "pathway": "pathways"}.get(kind)
        if table is None:
            return None
        return entity in getattr(self, table)


_default: Registry | None = None


def default() -> Registry:
    global _default
    if _default is None:
        _default = Registry()
    return _default


def gz_lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        yield from f
