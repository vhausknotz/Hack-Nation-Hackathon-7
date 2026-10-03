"""HGNC: approved gene symbols, previous symbols, aliases and gene groups."""

import csv
from dataclasses import dataclass
from pathlib import Path

from . import RAW


@dataclass
class Gene:
    hgnc_id: str  # "HGNC:11444"
    symbol: str
    name: str
    aliases: list[str]
    previous: list[str]
    groups: list[str]
    entrez_id: str
    uniprot_ids: list[str]
    locus_group: str


def _split(value: str) -> list[str]:
    return [v for v in value.strip('"').split("|") if v]


def load(path: Path = RAW / "hgnc_complete_set.txt") -> dict[str, Gene]:
    genes: dict[str, Gene] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["status"] != "Approved":
                continue
            genes[row["hgnc_id"]] = Gene(
                hgnc_id=row["hgnc_id"],
                symbol=row["symbol"],
                name=row["name"],
                aliases=_split(row["alias_symbol"]),
                previous=_split(row["prev_symbol"]),
                groups=_split(row["gene_group"]),
                entrez_id=row["entrez_id"],
                uniprot_ids=_split(row["uniprot_ids"]),
                locus_group=row["locus_group"],
            )
    return genes


def symbol_index(genes: dict[str, Gene]) -> dict[str, str]:
    """Symbol, alias or previous symbol (upper-cased) -> HGNC ID. Approved symbols win over aliases."""
    index: dict[str, str] = {}
    for g in genes.values():
        for s in g.aliases + g.previous:
            index.setdefault(s.upper(), g.hgnc_id)
    for g in genes.values():
        index[g.symbol.upper()] = g.hgnc_id
    return index
