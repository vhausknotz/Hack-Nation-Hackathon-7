"""Phase 0 data check: does open data support a story around a gene neighborhood?

For each gene: its diseases (MONDO), Orphanet's variant-effect label, how many symptoms are
annotated, the diseases most similar by symptoms, and where the other neighborhood diseases rank.
Usage: python pipeline/recon_neighborhood.py [GENE ...]
"""

import sys
from collections import defaultdict

from phenotype_similarity import PhenotypeIndex
from sources import hgnc, hpo, mondo, orphanet

DEFAULT_GENES = [
    # SNARE / synaptic vesicle fusion machinery (brain)
    "STXBP1", "SNAP25", "STX1B", "STX1A", "VAMP2", "SYT1", "CPLX1", "UNC13A", "NSF",
    # same machinery, other tissues: neuromuscular junction and immune cells (expected counterexamples)
    "SYT2", "VAMP1", "SNAP29", "STXBP2", "STX11", "UNC13D",
    # other developmental and epileptic encephalopathies (4-PBA trial partner and comparators)
    "SLC6A1", "SCN2A", "SYNGAP1", "DNM1", "CACNA1A", "KCNQ2", "CDKL5",
]


def main(genes: list[str]) -> None:
    onto = hpo.load_ontology()
    annotations = hpo.load_annotations(onto)
    diseases = mondo.load()
    xref = mondo.xref_index(diseases)
    gene_table = hgnc.load()
    symbols = hgnc.symbol_index(gene_table)
    orpha = orphanet.load_gene_associations()

    # Join symptom annotations from OMIM and Orphanet records onto one MONDO disease.
    terms: dict[str, set[str]] = defaultdict(set)
    unmapped = 0
    for source_id, ann in annotations.items():
        key = xref.get(source_id)
        if key is None:
            unmapped += 1
            key = source_id
        terms[key] |= set(ann.phenotypes)
    index = PhenotypeIndex(onto, terms)

    monogenic = [d for d in diseases.values() if d.genes and d.is_rare]
    with_symptoms = [d for d in monogenic if d.id in index]
    typed = [a for a in orpha if a.is_germline_causal and a.variant_effect]
    print("== Coverage ==")
    print(f"MONDO rare diseases with a causal gene: {len(monogenic)}; with symptom annotations: {len(with_symptoms)}")
    print(f"HPO-annotated records not mapped to MONDO: {unmapped} of {len(annotations)}")
    print(f"Orphanet germline causal links with a loss/gain-of-function label: {len(typed)} of {sum(a.is_germline_causal for a in orpha)}")

    by_gene = defaultdict(list)
    for d in diseases.values():
        for g in d.genes:
            by_gene[g].append(d)
    orpha_by_gene = defaultdict(list)
    for a in orpha:
        if a.hgnc_id:
            orpha_by_gene[a.hgnc_id].append(a)

    def genes_of(disease_id: str) -> str:
        d = diseases.get(disease_id)
        return ",".join(gene_table[g].symbol for g in d.genes if g in gene_table) if d else "?"

    def name_of(disease_id: str) -> str:
        if disease_id in diseases:
            return diseases[disease_id].name
        return annotations[disease_id].name if disease_id in annotations else disease_id

    neighborhood: dict[str, str] = {}  # disease -> gene symbol
    print("\n== Genes ==")
    for symbol in genes:
        hid = symbols.get(symbol.upper())
        if hid is None:
            print(f"{symbol}: not found in HGNC")
            continue
        g = gene_table[hid]
        print(f"\n{g.symbol} ({g.name}) groups={g.groups}")
        for d in by_gene.get(hid, []):
            n = len(terms.get(d.id, ()))
            print(f"  {d.id} {d.name} | symptoms={n} | rare={d.is_rare}")
            if n >= 3 and d.is_rare:
                neighborhood.setdefault(d.id, g.symbol)
        for a in orpha_by_gene.get(hid, []):
            if a.is_germline_causal:
                print(f"  Orphanet {a.orpha_code} {a.disease_name} | {a.association_type} | effect={a.variant_effect}")

    print("\n== Nearest diseases by symptoms ==")
    for did, sym in neighborhood.items():
        print(f"\n{sym}: {name_of(did)} ({did})")
        for other, score in index.similar(did, top=8):
            print(f"  {score:.3f}  {name_of(other)} [{genes_of(other)}]")
        ranks = []
        for other, osym in neighborhood.items():
            if other != did:
                rank, score = index.rank_of(did, other)
                ranks.append((rank, osym, score))
        print("  neighborhood ranks: " + ", ".join(f"{s}#{r}({sc:.2f})" for r, s, sc in sorted(ranks)))

    print("\n== Shared symptoms, most informative first ==")
    ids = list(neighborhood)
    by_symbol = {s: d for d, s in neighborhood.items()}
    for a, b in [("SNAP25", "STXBP1"), ("STX1B", "STXBP1"), ("SLC6A1", "STXBP1"), ("STXBP2", "STXBP1"), ("SYT2", "SYT1")]:
        if a in by_symbol and b in by_symbol:
            print(f"\n{a} vs {b}:")
            for s in index.shared_symptoms(by_symbol[a], by_symbol[b], top=8):
                print(f"  {s.name} ({s.plain_name}) | IC={s.ic:.2f} | in {s.disease_count} diseases")
    print(f"\n(index: {len(index.ids)} diseases, {len(index.col)} symptom terms; neighborhood size {len(ids)})")


if __name__ == "__main__":
    main([g for g in sys.argv[1:]] or DEFAULT_GENES)
