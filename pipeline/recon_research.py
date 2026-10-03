"""Phase 0 data check, part 2: how much research signal exists per gene (papers, trials, NIH grants)?

Usage: python pipeline/recon_research.py [GENE ...]
"""

import sys
from collections import Counter

from sources import clinicaltrials, pubmed, reporter

DEFAULT_GENES = ["STXBP1", "SNAP25", "STX1B", "VAMP2", "SYT1", "CPLX1", "UNC13A", "NSF", "SLC6A1", "SYNGAP1", "SCN2A", "CACNA1A", "STXBP2"]
DISEASE_CONTEXT = "(mutation*[tiab] OR variant*[tiab]) AND (patient*[tiab] OR disorder*[tiab] OR syndrome*[tiab] OR encephalopath*[tiab] OR epilep*[tiab])"
FISCAL_YEARS = [2022, 2023, 2024, 2025, 2026]

LITERATURE_CHECKS = {
    "SNAP25 epileptic encephalopathy": "SNAP25[tiab] AND (encephalopathy[tiab] OR epilep*[tiab]) AND (de novo[tiab] OR variant*[tiab])",
    "SNAREopathy concept": "SNAREopath*[tiab]",
    "STXBP1 + 4-phenylbutyrate": "STXBP1[tiab] AND (phenylbutyrate[tiab] OR 4-PBA[tiab])",
    "STXBP1 natural history": "STXBP1[tiab] AND (natural history[tiab] OR registry[tiab] OR cohort[tiab])",
    "STXBP1 haploinsufficiency / dominant negative": "STXBP1[tiab] AND (haploinsufficien*[tiab] OR dominant-negative[tiab] OR dominant negative[tiab])",
    "SNAP25 dominant negative": "SNAP25[tiab] AND (dominant-negative[tiab] OR dominant negative[tiab] OR haploinsufficien*[tiab])",
}


def main(genes: list[str]) -> None:
    print("== Papers, trials and NIH grants per gene ==")
    print(f"{'gene':8} {'papers':>7} {'disease-papers':>14} {'since2021':>9} {'trials':>6} {'NIH FY22-26':>11}  top PIs")
    for gene in genes:
        papers, _ = pubmed.search(f"{gene}[tiab]")
        disease_papers, _ = pubmed.search(f"{gene}[tiab] AND {DISEASE_CONTEXT}")
        recent, _ = pubmed.search(f"{gene}[tiab] AND {DISEASE_CONTEXT} AND 2021:2026[dp]")
        trials = clinicaltrials.search(gene, max_studies=100)
        total, projects = reporter.search(gene, FISCAL_YEARS, limit=200)
        pis = Counter(pi for p in projects for pi in p.investigators)
        top = ", ".join(f"{n} ({c})" for n, c in pis.most_common(3))
        print(f"{gene:8} {papers:>7} {disease_papers:>14} {recent:>9} {len(trials):>6} {total:>11}  {top}")

    print("\n== Trials (selected genes) ==")
    for gene in ["STXBP1", "SNAP25", "SLC6A1", "SYNGAP1", "STX1B", "SYT1"]:
        for s in clinicaltrials.search(gene, max_studies=100):
            print(f"{gene:7} {s.nct_id} | {s.status} | {','.join(s.phases) or s.study_type} | {s.title[:90]} | {', '.join(s.interventions)[:60]} | {s.sponsor[:40]}")

    print("\n== Literature checks ==")
    for label, term in LITERATURE_CHECKS.items():
        count, ids = pubmed.search(term, retmax=5, sort="relevance")
        print(f"\n{label}: {count} papers")
        for a in pubmed.fetch(ids):
            first = f"{a.authors[0].last} {a.authors[0].fore[:1]}" if a.authors else "?"
            print(f"  PMID {a.pmid} | {first} et al. {a.year} | {a.journal[:40]} | {a.title[:110]}")


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_GENES)
