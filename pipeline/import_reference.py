"""Load the pinned reference datasets into the ledger as reference claims.

One `import.recorded` event per dataset commits (via a Merkle root) to every claim derived from it.
Claims are deterministic functions of the dataset bytes (provenance dates come from the source
manifest, not the clock), so re-running the importer on the same files reproduces the same claim IDs:
that is how reference data is verified. Claims are about MONDO diseases; the projection
(build_graph.py) derives the gene-defined conditions.
Usage: python pipeline/import_reference.py
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledger import identity  # noqa: E402
from ledger.api import Ledger  # noqa: E402
from ledger.schema import make_claim  # noqa: E402
from sources import hpo, mondo, orphanet, validity  # noqa: E402

IMPORTER = "reference-import@1"
G2P_EFFECTS = {"loss of function": "loss_of_function", "gain of function": "gain_of_function",
               "dominant negative": "dominant_negative", "undetermined non-loss-of-function": "non_loss_of_function"}
CAUSAL_GRADES = {"definitive", "strong", "moderate", "limited"}


def main() -> None:
    t0 = time.time()
    ledger = Ledger()
    importer = ledger.register(identity.load_or_create("importer:reference"), kind="importer",
                               manifest={"purpose": "Imports pinned reference datasets", "version": IMPORTER})
    manifest = json.loads((ROOT / "data" / "sources_manifest.json").read_text())
    reg = ledger.registry

    def provenance(dataset: str) -> dict:
        return {"contributor": importer.contributor, "agent": IMPORTER, "created": manifest[dataset]["retrieved"][:10]}

    def evidence(dataset: str, record: str, **fields) -> list[dict]:
        return [{"type": "curated_database", "dataset": dataset, "dataset_hash": reg.dataset_hash(dataset), "record": record,
                 **{k: v for k, v in fields.items() if v not in (None, "", [])}}]

    def record(dataset: str, claims: list[dict]) -> None:
        result = ledger.record_import(dataset, IMPORTER, claims, importer)
        print(f"[{time.time() - t0:6.1f}s] {dataset}: {result['claims']} claims, {result['rejected']} rejected {result['rejection_reasons'] or ''}")

    onto = hpo.load_ontology()
    diseases = mondo.load()
    xref = mondo.xref_index(diseases)

    # MONDO: causal genes and preferred names
    claims = []
    for d in diseases.values():
        for g in d.genes:
            claims.append(make_claim(g, "causes", d.id, evidence("mondo.obo", d.id, relation="has_material_basis_in_germline_mutation_in"), provenance("mondo.obo")))
        if d.genes:
            claims.append(make_claim(d.id, "has_name", d.name, evidence("mondo.obo", d.id), provenance("mondo.obo"), name_type="preferred", naming_source="MONDO"))
    record("mondo.obo", claims)

    # Gene2Phenotype: causal links, variant effect, curated names, phenotypes
    claims = []
    for r in validity.load_g2p():
        mid = r.mondo_id if r.mondo_id in diseases else xref.get(r.omim_id or "")
        if not mid or r.confidence not in CAUSAL_GRADES:
            continue
        ev = evidence("g2p_all.csv", r.g2p_id, grade=r.confidence, inheritance=r.allelic_requirement, url=r.url, reviewed=r.reviewed, pmids=r.pmids[:20])
        prov = provenance("g2p_all.csv")
        claims.append(make_claim(r.hgnc_id, "causes", mid, ev, prov))
        claims.append(make_claim(mid, "has_name", r.disease_name, ev, prov, name_type="curated_name", naming_source="Gene2Phenotype"))
        if r.mechanism in G2P_EFFECTS:
            claims.append(make_claim(mid, "has_variant_effect", f"effect:{G2P_EFFECTS[r.mechanism]}", evidence("g2p_all.csv", r.g2p_id, support=r.mechanism_support, url=r.url),
                                     prov, gene=r.hgnc_id))
        for h in r.phenotypes:
            h = onto.resolve(h)
            if h and onto.is_phenotypic_abnormality(h):
                claims.append(make_claim(mid, "has_symptom", h, evidence("g2p_all.csv", r.g2p_id, url=r.url), prov))
    record("g2p_all.csv", claims)

    # GenCC (Orphanet's own submissions are imported directly from Orphanet below)
    claims = []
    for s in validity.load_gencc():
        if s.submitter == "Orphanet" or s.classification.lower() not in CAUSAL_GRADES or s.mondo_id not in diseases:
            continue
        rec = f"{s.submitter}|{s.hgnc_id}|{s.mondo_id}|{s.classification}|{s.date}"
        claims.append(make_claim(s.hgnc_id, "causes", s.mondo_id,
                                 evidence("gencc_submissions.tsv", rec, grade=s.classification, submitter=s.submitter, inheritance=s.moi, url=s.report_url, pmids=s.pmids[:20]),
                                 provenance("gencc_submissions.tsv")))
    record("gencc_submissions.tsv", claims)

    # ClinGen gene-disease validity
    claims = []
    for c in validity.load_clingen_validity():
        if c.classification.lower() not in CAUSAL_GRADES or c.mondo_id not in diseases:
            continue
        claims.append(make_claim(c.hgnc_id, "causes", c.mondo_id,
                                 evidence("clingen_gene_validity.csv", c.report_url, grade=c.classification, inheritance=c.moi, panel=c.expert_panel, date=c.date),
                                 provenance("clingen_gene_validity.csv")))
    record("clingen_gene_validity.csv", claims)

    # Orphanet: germline causal genes and loss/gain-of-function labels
    claims = []
    for a in orphanet.load_gene_associations():
        mid = xref.get(a.orpha_code)
        if not mid or not a.hgnc_id or not a.is_germline_causal:
            continue
        rec = f"{a.orpha_code}|{a.hgnc_id}"
        ev = evidence("orphanet_genes.xml", rec, association=a.association_type, status=a.status, pmids=a.pmids)
        claims.append(make_claim(a.hgnc_id, "causes", mid, ev, provenance("orphanet_genes.xml")))
        if a.variant_effect:
            claims.append(make_claim(mid, "has_variant_effect", f"effect:{a.variant_effect}", ev, provenance("orphanet_genes.xml"), gene=a.hgnc_id))
    record("orphanet_genes.xml", claims)

    # HPO: disease -> symptom annotations (OMIM/Orphanet records mapped onto MONDO)
    claims = []
    for rid, ann in hpo.load_annotations(onto).items():
        mid = xref.get(rid)
        if not mid:
            continue
        for h, a in ann.phenotypes.items():
            claims.append(make_claim(mid, "has_symptom", h,
                                     evidence("phenotype.hpoa", f"{rid}|{h}", source_record=rid, frequency=a.frequency, evidence_code=a.evidence,
                                              refs=[r for r in a.references if r.startswith("PMID:")][:5]),
                                     provenance("phenotype.hpoa")))
    record("phenotype.hpoa", claims)

    head = ledger.publish_tree_head()
    print(f"[{time.time() - t0:6.1f}s] tree head: size {head['size']}, root {head['root'][:16]}…")
    counts = ledger.store.db.execute("SELECT predicate, COUNT(*) FROM claims WHERE origin='reference' GROUP BY predicate").fetchall()
    print("reference claims:", {p: n for p, n in counts})


if __name__ == "__main__":
    main()
