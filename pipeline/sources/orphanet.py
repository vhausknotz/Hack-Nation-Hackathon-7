"""Orphanet (Orphadata) gene-disease associations, including loss/gain-of-function labels where curated."""

import re
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from . import RAW


@dataclass
class GeneAssociation:
    orpha_code: str  # "ORPHA:599373"
    disease_name: str
    gene_symbol: str
    gene_name: str
    hgnc_id: str | None  # "HGNC:11444"
    association_type: str  # e.g. "Disease-causing germline mutation(s) (loss of function) in"
    status: str  # "Assessed" or "Not yet assessed"
    pmids: list[str]

    @property
    def variant_effect(self) -> str | None:
        """'loss_of_function', 'gain_of_function', or None when Orphanet doesn't say."""
        if "(loss of function)" in self.association_type:
            return "loss_of_function"
        if "(gain of function)" in self.association_type:
            return "gain_of_function"
        return None

    @property
    def is_germline_causal(self) -> bool:
        return self.association_type.startswith("Disease-causing germline")


def load_gene_associations(path: Path = RAW / "orphanet_genes.xml") -> list[GeneAssociation]:
    out: list[GeneAssociation] = []
    for _, disorder in etree.iterparse(str(path), tag="Disorder"):
        code = disorder.findtext("OrphaCode")
        name = disorder.findtext("Name")
        for assoc in disorder.iterfind("DisorderGeneAssociationList/DisorderGeneAssociation"):
            gene = assoc.find("Gene")
            hgnc = None
            for ref in gene.iterfind("ExternalReferenceList/ExternalReference"):
                if ref.findtext("Source") == "HGNC":
                    hgnc = "HGNC:" + ref.findtext("Reference")
            out.append(GeneAssociation(
                orpha_code=f"ORPHA:{code}",
                disease_name=name,
                gene_symbol=gene.findtext("Symbol"),
                gene_name=gene.findtext("Name"),
                hgnc_id=hgnc,
                association_type=assoc.findtext("DisorderGeneAssociationType/Name"),
                status=assoc.findtext("DisorderGeneAssociationStatus/Name"),
                pmids=re.findall(r"(\d+)\[PMID\]", assoc.findtext("SourceOfValidation") or ""),
            ))
        disorder.clear()
    return out
