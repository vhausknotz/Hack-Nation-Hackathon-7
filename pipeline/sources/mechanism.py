"""Molecular machinery per gene: protein complexes, pathways, Gene Ontology terms and physical interactions.

All loaders return annotations keyed by HGNC ID, so callers never deal with UniProt or Ensembl IDs.
"""

import csv
import gzip
import re
from collections import defaultdict
from dataclasses import dataclass

from . import RAW, obo

# GO evidence codes we trust: experimental, phylogenetic, curated computational and author/curator statements.
# Electronic annotations (IEA) and "no data" (ND) are excluded.
GO_EVIDENCE = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP",
               "IBA", "IBD", "IKR", "IRD", "ISS", "ISO", "ISA", "ISM", "IGC", "RCA", "TAS", "NAS", "IC"}


@dataclass
class Annotation:
    id: str  # "CPX-1234", "R-HSA-112310", "GO:0016079"
    name: str
    source: str  # "Complex Portal", "Reactome", "Gene Ontology"
    url: str
    evidence: str = ""


def uniprot_to_hgnc(genes: dict) -> dict[str, str]:
    """UniProt accession -> HGNC ID, from the HGNC table (sources.hgnc.load())."""
    out = {}
    for g in genes.values():
        for acc in g.uniprot_ids:
            out.setdefault(acc, g.hgnc_id)
    return out


def load_complexes(uniprot_index: dict[str, str]) -> dict[str, list[Annotation]]:
    by_gene: dict[str, list[Annotation]] = defaultdict(list)
    with open(RAW / "complexportal_human.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            members = re.findall(r"([A-Z0-9]+)(?:-[A-Z0-9_]+)?\(\d+\)", row["Identifiers (and stoichiometry) of molecules in complex"])
            ann = Annotation(row["#Complex ac"], row["Recommended name"], "Complex Portal",
                             f"https://www.ebi.ac.uk/complexportal/complex/{row['#Complex ac']}", row["Evidence Code"])
            for hgnc_id in {uniprot_index[m] for m in members if m in uniprot_index}:
                by_gene[hgnc_id].append(ann)
    return by_gene


def load_reactome(uniprot_index: dict[str, str]) -> dict[str, list[Annotation]]:
    """Human pathways at every level of the Reactome hierarchy (broad ones get low weight later via IC)."""
    by_gene: dict[str, dict[str, Annotation]] = defaultdict(dict)
    with open(RAW / "reactome_uniprot_all_levels.txt", encoding="utf-8") as f:
        for line in f:
            acc, pid, url, name, evidence, species = line.rstrip("\n").split("\t")
            if species != "Homo sapiens" or acc not in uniprot_index:
                continue
            by_gene[uniprot_index[acc]].setdefault(pid, Annotation(pid, name, "Reactome", url, evidence))
    return {g: list(anns.values()) for g, anns in by_gene.items()}


def load_go(symbol_index: dict[str, str], aspects: tuple[str, ...] = ("P", "C")) -> tuple[dict[str, list[Annotation]], obo.Obo]:
    """Direct GO annotations (biological process and cellular component by default), plus the GO ontology for ancestors."""
    ontology = obo.load(RAW / "go-basic.obo")
    by_gene: dict[str, dict[str, Annotation]] = defaultdict(dict)
    with gzip.open(RAW / "goa_human.gaf.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("!"):
                continue
            col = line.rstrip("\n").split("\t")
            symbol, qualifier, go_id, evidence, aspect = col[2], col[3], col[4], col[6], col[8]
            if aspect not in aspects or evidence not in GO_EVIDENCE or qualifier.startswith("NOT"):
                continue
            hgnc_id = symbol_index.get(symbol.upper())
            go_id = ontology.resolve(go_id)
            if hgnc_id is None or go_id is None:
                continue
            by_gene[hgnc_id].setdefault(go_id, Annotation(go_id, ontology.terms[go_id].name, "Gene Ontology",
                                                          f"https://amigo.geneontology.org/amigo/term/{go_id}", evidence))
    return {g: list(anns.values()) for g, anns in by_gene.items()}, ontology


def load_physical_interactions(symbol_index: dict[str, str], min_score: int = 700) -> dict[str, dict[str, int]]:
    """STRING physical-interaction partners per gene with score >= min_score (0-1000; 700 = high confidence)."""
    names = {}
    with gzip.open(RAW / "string_protein_info.txt.gz", "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            protein, name = line.split("\t", 2)[:2]
            if name.upper() in symbol_index:
                names[protein] = symbol_index[name.upper()]
    partners: dict[str, dict[str, int]] = defaultdict(dict)
    with gzip.open(RAW / "string_physical_links.txt.gz", "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            a, b, score = line.split()
            score = int(score)
            if score >= min_score and a in names and b in names and names[a] != names[b]:
                partners[names[a]][names[b]] = max(score, partners[names[a]].get(names[b], 0))
    return partners
