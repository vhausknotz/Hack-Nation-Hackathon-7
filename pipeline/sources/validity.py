"""Gene-disease validity and mechanism curations: Gene2Phenotype, GenCC, ClinGen gene validity and dosage."""

import csv
from dataclasses import dataclass, field

from . import RAW


@dataclass
class G2PRecord:
    g2p_id: str
    hgnc_id: str  # "HGNC:11444"
    gene_symbol: str
    disease_name: str  # G2P's current name, e.g. "SNAP25-related epilepsy and intellectual disability"
    mondo_id: str | None
    omim_id: str | None
    allelic_requirement: str  # e.g. monoallelic_autosomal
    confidence: str  # definitive, strong, moderate, limited, disputed, refuted
    variant_consequence: str  # e.g. "absent gene product"
    mechanism: str  # loss of function, gain of function, dominant negative, undetermined, ...
    mechanism_support: str  # inferred | evidence
    phenotypes: list[str] = field(default_factory=list)  # HPO IDs
    pmids: list[str] = field(default_factory=list)  # curated publications
    mined_pmids: list[str] = field(default_factory=list)  # text-mined publications
    panels: list[str] = field(default_factory=list)
    reviewed: str = ""

    @property
    def url(self) -> str:
        return f"https://www.ebi.ac.uk/gene2phenotype/lgd/{self.g2p_id}"


def _split(value: str, sep: str = ";") -> list[str]:
    return [v.strip() for v in value.split(sep) if v.strip()]


def load_g2p() -> list[G2PRecord]:
    out = []
    with open(RAW / "g2p_all.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append(G2PRecord(
                g2p_id=r["g2p id"],
                hgnc_id=f"HGNC:{r['hgnc id']}",
                gene_symbol=r["gene symbol"],
                disease_name=r["disease name"],
                mondo_id=r["disease MONDO"] or None,
                omim_id=f"OMIM:{r['disease mim']}" if r["disease mim"] else None,
                allelic_requirement=r["allelic requirement"],
                confidence=r["confidence"],
                variant_consequence=r["variant consequence"],
                mechanism=r["molecular mechanism"],
                mechanism_support=r["molecular mechanism support"],
                phenotypes=_split(r["phenotypes"]),
                pmids=_split(r["publications"]),
                mined_pmids=_split(r["additional mined publications"]),
                panels=_split(r["panel"]),
                reviewed=r["date of last review"][:10],
            ))
    return out


@dataclass
class GenCCSubmission:
    hgnc_id: str
    gene_symbol: str
    mondo_id: str
    disease_title: str
    classification: str  # Definitive, Strong, Moderate, Limited, Disputed Evidence, Refuted Evidence, Supportive, ...
    moi: str  # mode of inheritance
    submitter: str
    date: str
    pmids: list[str]
    report_url: str


def load_gencc() -> list[GenCCSubmission]:
    out = []
    with open(RAW / "gencc_submissions.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if not r["disease_curie"].startswith("MONDO:"):
                continue
            out.append(GenCCSubmission(
                hgnc_id=r["gene_curie"], gene_symbol=r["gene_symbol"], mondo_id=r["disease_curie"],
                disease_title=r["disease_title"], classification=r["classification_title"], moi=r["moi_title"],
                submitter=r["submitter_title"], date=r["submitted_as_date"][:10],
                pmids=[p.strip().removeprefix("PMID:").strip() for p in r["submitted_as_pmids"].replace(",", ";").split(";") if p.strip()],
                report_url=r["submitted_as_public_report_url"],
            ))
    return out


@dataclass
class ClinGenValidity:
    hgnc_id: str
    gene_symbol: str
    mondo_id: str
    disease_label: str
    moi: str
    classification: str
    report_url: str
    date: str
    expert_panel: str


def load_clingen_validity() -> list[ClinGenValidity]:
    out = []
    with open(RAW / "clingen_gene_validity.csv", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header_at = next(i for i, r in enumerate(rows) if r and r[0] == "GENE SYMBOL")
    for r in rows[header_at + 1:]:
        if len(r) < 10 or r[0].startswith("+"):
            continue
        out.append(ClinGenValidity(r[1], r[0], r[3], r[2], r[4], r[6], r[7], r[8][:10], r[9]))
    return out


def load_clingen_dosage() -> dict[str, dict]:
    """Gene symbol -> haploinsufficiency score (3 = sufficient evidence, 30 = autosomal recessive, 40 = unlikely)."""
    out = {}
    with open(RAW / "clingen_dosage.tsv", encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#") or l.startswith("#Gene Symbol")]
    for r in csv.DictReader([l.lstrip("#") for l in lines], delimiter="\t"):
        out[r["Gene Symbol"]] = {
            "haploinsufficiency_score": r["Haploinsufficiency Score"],
            "haploinsufficiency": r["Haploinsufficiency Description"],
            "url": f"https://www.ncbi.nlm.nih.gov/projects/dbvar/clingen/clingen_gene.cgi?sym={r['Gene Symbol']}",
        }
    return out
