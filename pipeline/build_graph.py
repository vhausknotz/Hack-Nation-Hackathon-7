"""Phase 1: build the breadth graph for every monogenic condition from open structured data.

A condition is gene-defined: one gene plus the disease it causes, keyed by MONDO ID. When a MONDO
disease covers several genes without gene-specific subtypes, a gene that has no other condition gets
its own "<GENE>-related <disease>" condition (ID "<MONDO>-<HGNC>"). Umbrella terms (a disease whose
gene-specific subtypes exist) become search aliases; multi-gene diseases and MONDO classes become groups.

Output in data/build/:
  conditions.jsonl  conditions with names, genes (+ evidence), symptoms, inheritance, onset, prevalence
  genes.jsonl       genes with molecular machinery (complexes, pathways, GO, partners, dosage)
  neighbors.jsonl   per condition: most similar conditions (by symptoms, by mechanism, combined) with reasons
  phenotypes.jsonl  dictionary of every symptom term referenced
  mechanisms.jsonl  dictionary of every complex / pathway / GO term referenced, with gene counts
  groups.jsonl      disease groups (e.g. "lysosomal storage disease") and their conditions
  search.jsonl      every searchable name -> entity
  report.json       counts and coverage
Usage: python pipeline/build_graph.py
"""

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from similarity import IcIndex
from sources import hgnc, hpo, mechanism, mondo, orphanet, validity

OUT = Path(__file__).resolve().parent.parent / "data" / "build"
K_COMBINED, K_SYMPTOM, K_MECHANISM = 20, 10, 10
MECH_WEIGHTS = {"complex": 0.2, "pathway": 0.2, "go": 0.35, "partners": 0.25}
PPI_WEIGHT = 0.6  # how much a direct, high-confidence physical interaction adds to mechanism similarity
PPI_HUB_DEGREE = 40  # partners beyond this (90th percentile) dampen the interaction bonus for hub proteins
GO_ROOTS = {"GO:0008150", "GO:0005575", "GO:0003674"}
CATEGORY_NAMES = [  # first match wins; used for map colors and filters (missing names are logged)
    "nervous system disorder", "inborn errors of metabolism", "cardiovascular disorder", "immune system disorder",
    "hematologic disorder", "musculoskeletal system disorder", "integumentary system disorder", "disorder of visual system",
    "auditory system disorder", "kidney disorder", "urinary system disorder", "endocrine system disorder",
    "respiratory system disorder", "digestive system disorder", "reproductive system disorder", "cancer or benign tumor",
]
STRENGTH = {"strong": 3, "moderate": 2, "limited": 1}
G2P_EFFECTS = {"loss of function": "loss_of_function", "gain of function": "gain_of_function",
               "dominant negative": "dominant_negative", "undetermined non-loss-of-function": "non_loss_of_function"}
ONSET_ROOT = "HP:0003674"


def log(msg: str, t0: list[float] = [time.time()]) -> None:
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


def link_strength(source: str, confidence: str) -> str:
    c = confidence.lower()
    if source in ("MONDO", "Orphanet") or c in ("definitive", "strong"):
        return "strong"
    if c == "moderate":
        return "moderate"
    if c in ("limited", "supportive"):  # "supportive" carries no causality grade
        return "limited"
    return "none"  # disputed, refuted, no known disease relationship, animal model only, ...


@dataclass
class Condition:
    id: str
    disease: str  # the MONDO disease this condition is defined on
    gene: str  # HGNC ID
    synthetic: bool  # split out of a multi-gene disease


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    onto = hpo.load_ontology()
    annotations = hpo.load_annotations(onto)
    diseases = mondo.load()
    xref = mondo.xref_index(diseases)
    gene_table = hgnc.load()
    log("loaded HPO, MONDO, HGNC")

    # ---- gene-disease links with provenance ----------------------------------------------------
    links: dict[tuple[str, str], list[dict]] = defaultdict(list)  # (mondo, hgnc) -> evidence

    def add_link(mondo_id: str | None, hgnc_id: str | None, ev: dict) -> None:
        if mondo_id in diseases and hgnc_id in gene_table and ev["strength"] != "none":
            links[(mondo_id, hgnc_id)].append(ev)

    for d in diseases.values():
        for g in d.genes:
            add_link(d.id, g, {"source": "MONDO", "strength": "strong", "url": f"https://monarchinitiative.org/{d.id}"})
    g2p_by_pair: dict[tuple[str, str], list] = defaultdict(list)
    for r in validity.load_g2p():
        mid = r.mondo_id if r.mondo_id in diseases else xref.get(r.omim_id or "")
        if mid:
            g2p_by_pair[(mid, r.hgnc_id)].append(r)
        add_link(mid, r.hgnc_id, {"source": "Gene2Phenotype", "strength": link_strength("G2P", r.confidence),
                                  "confidence": r.confidence, "mechanism": r.mechanism, "inheritance": r.allelic_requirement,
                                  "url": r.url, "date": r.reviewed, "pmids": r.pmids[:20]})
    for s in validity.load_gencc():
        if s.submitter == "Orphanet":  # imported directly below, with Orphanet's own association types
            continue
        add_link(s.mondo_id, s.hgnc_id, {"source": f"GenCC ({s.submitter})", "strength": link_strength("GenCC", s.classification),
                                         "confidence": s.classification, "inheritance": s.moi, "date": s.date,
                                         "url": s.report_url or f"https://search.thegencc.org/genes/{s.hgnc_id}", "pmids": s.pmids[:20]})
    for c in validity.load_clingen_validity():
        add_link(c.mondo_id, c.hgnc_id, {"source": "ClinGen", "strength": link_strength("ClinGen", c.classification),
                                         "confidence": c.classification, "inheritance": c.moi, "url": c.report_url, "date": c.date})
    orpha_effect: dict[tuple[str, str], str] = {}
    for a in orphanet.load_gene_associations():
        mid = xref.get(a.orpha_code)
        if a.is_germline_causal and a.hgnc_id:
            add_link(mid, a.hgnc_id, {"source": "Orphanet", "strength": "strong", "confidence": a.status,
                                      "mechanism": a.variant_effect, "url": f"https://www.orpha.net/en/disease/detail/{a.orpha_code.split(':')[1]}",
                                      "pmids": a.pmids})
            if mid and a.variant_effect:
                orpha_effect[(mid, a.hgnc_id)] = a.variant_effect
    genes_of: dict[str, dict[str, str]] = defaultdict(dict)  # mondo -> hgnc -> best strength
    for (mid, gid), evs in links.items():
        genes_of[mid][gid] = max((e["strength"] for e in evs), key=lambda s: STRENGTH.get(s, 0))
    log(f"gene-disease links: {len(links)}")

    # ---- symptoms, inheritance, onset per disease ---------------------------------------------------
    pheno: dict[str, dict[str, dict]] = defaultdict(dict)
    inheritance: dict[str, set[str]] = defaultdict(set)
    course: dict[str, set[str]] = defaultdict(set)
    records_of: dict[str, list[str]] = defaultdict(list)
    for rid, ann in annotations.items():
        mid = xref.get(rid, rid)
        records_of[mid].append(rid)
        for hid, a in ann.phenotypes.items():
            entry = pheno[mid].setdefault(hid, {"frequency": a.frequency, "sources": [], "refs": []})
            entry["sources"].append(rid)
            entry["refs"] = sorted(set(entry["refs"]) | {r for r in a.references if r.startswith("PMID:")})[:5]
        inheritance[mid] |= {onto.label(t) for t in ann.inheritance}
        course[mid] |= ann.course

    # ---- conditions ----------------------------------------------------------------------------------
    children: dict[str, list[str]] = defaultdict(list)
    for d in diseases.values():
        for p in d.parents:
            children[p].append(d.id)
    desc_cache: dict[str, frozenset[str]] = {}

    def descendants(mid: str) -> frozenset[str]:
        if mid not in desc_cache:
            out = set()
            for ch in children.get(mid, []):
                out |= {ch} | descendants(ch)
            desc_cache[mid] = frozenset(out)
        return desc_cache[mid]

    candidates = {mid: {g for g, s in gs.items() if STRENGTH.get(s, 0) >= 2} for mid, gs in genes_of.items()}
    candidates = {mid: gs for mid, gs in candidates.items() if gs}
    umbrella_of: dict[str, list[str]] = defaultdict(list)  # disease -> umbrella terms above it
    single: dict[str, str] = {}  # disease -> its one core gene
    multi: dict[str, set[str]] = {}  # disease -> genes, when it is not gene-specific
    for mid, gs in candidates.items():
        below = [d for d in descendants(mid) if d in candidates and candidates[d] & gs]
        if below:
            for d in below:
                umbrella_of[d].append(mid)
            continue
        core = (set(diseases[mid].genes) & gs) or gs
        if len(core) == 1:
            single[mid] = next(iter(core))
        multi_genes = (gs - core) if len(core) == 1 else gs
        if multi_genes:
            multi[mid] = multi_genes
    conditions: dict[str, Condition] = {mid: Condition(mid, mid, g, False) for mid, g in single.items()}
    has_condition = set(single.values())
    options: dict[str, list[tuple]] = defaultdict(list)
    for mid, gs in multi.items():
        for g in gs:
            if g not in has_condition and genes_of[mid][g] == "strong":
                options[g].append((len(candidates[mid]), -len(pheno.get(mid, {})), mid))
    for g, opts in options.items():
        mid = min(opts)[2]  # the most specific multi-gene disease this gene belongs to
        cid = f"{mid}-{g}"
        conditions[cid] = Condition(cid, mid, g, True)
    gene_conditions: dict[str, list[str]] = defaultdict(list)
    for c in conditions.values():
        gene_conditions[c.gene].append(c.id)
    log(f"conditions: {len(conditions)} ({sum(c.synthetic for c in conditions.values())} split out of multi-gene diseases) | "
        f"umbrella terms: {len({u for us in umbrella_of.values() for u in us})} | multi-gene diseases: {len(multi)}")

    def condition_pheno(c: Condition) -> dict[str, dict]:
        out = {h: dict(e) for h, e in pheno.get(c.disease, {}).items()}
        for r in g2p_by_pair.get((c.disease, c.gene), []):
            for hid in r.phenotypes:
                hid = onto.resolve(hid)
                if hid and onto.is_phenotypic_abnormality(hid):
                    out.setdefault(hid, {"frequency": "", "sources": [], "refs": []})
                    out[hid] = {**out[hid], "sources": out[hid]["sources"] + [f"G2P:{r.g2p_id}"]}
        # an umbrella's symptoms flow down when it has exactly one condition below it
        for u in umbrella_of.get(c.disease, []):
            below = [d for d in descendants(u) if d in conditions]
            if len(below) == 1 and pheno.get(u):
                for hid, e in pheno[u].items():
                    out.setdefault(hid, {**e, "sources": [f"{s} (via {u})" for s in e["sources"]]})
        return {h: e for h, e in out.items() if onto.is_phenotypic_abnormality(h)}

    cond_pheno = {cid: condition_pheno(c) for cid, c in conditions.items()}

    def closure(terms) -> set[str]:
        out = set()
        for t in terms:
            out |= onto.ancestors(t)
        return {t for t in out if onto.is_phenotypic_abnormality(t)}

    sets = {cid: closure(p) for cid, p in cond_pheno.items()}
    condition_diseases = {c.disease for c in conditions.values()}
    for mid, p in pheno.items():  # other annotated diseases still inform how rare each symptom is
        if mid not in condition_diseases:
            sets[f"other:{mid}"] = closure(p)
    symptom_index = IcIndex(sets)
    cond_ids = sorted(conditions)
    with_symptoms = [c for c in cond_ids if c in symptom_index]
    totals = np.array([symptom_index.total[symptom_index.row[c]] for c in with_symptoms])
    info_floor = float(np.percentile(totals, 25))

    def symptom_similarity(a: str, b: str) -> float:
        """simGIC, shrunk when either profile carries little information (e.g. only "seizure" + "intellectual disability")."""
        if a not in symptom_index or b not in symptom_index:
            return 0.0
        smaller = float(min(symptom_index.total[symptom_index.row[a]], symptom_index.total[symptom_index.row[b]]))
        return float(symptom_index.similarity(a, b) * min(1.0, (smaller / info_floor) ** 0.5))

    log(f"symptom index: {len(symptom_index.ids)} profiles, {len(symptom_index.vocab)} terms (information floor {info_floor:.1f})")

    # ---- genes: molecular machinery ---------------------------------------------------------------------
    symbols = hgnc.symbol_index(gene_table)
    uniprot = mechanism.uniprot_to_hgnc(gene_table)
    complexes = mechanism.load_complexes(uniprot)
    pathways = mechanism.load_reactome(uniprot)
    go_direct, go = mechanism.load_go(symbols)
    partners = mechanism.load_physical_interactions(symbols)
    dosage = validity.load_clingen_dosage()

    def go_closure(anns) -> set[str]:
        out = set()
        for a in anns:
            out |= go.ancestors(a.id)
        return out - GO_ROOTS

    all_genes = set(gene_table)
    mech_sets = {
        "complex": {g: {a.id for a in complexes.get(g, [])} for g in all_genes},
        "pathway": {g: {a.id for a in pathways.get(g, [])} for g in all_genes},
        "go": {g: go_closure(go_direct.get(g, [])) for g in all_genes},
        "partners": {g: ({f"PPI:{p}" for p in partners[g]} | {f"PPI:{g}"}) if partners.get(g) else set() for g in all_genes},
    }
    mech_index = {name: IcIndex(s) for name, s in mech_sets.items()}
    mech_names: dict[str, tuple[str, str, str]] = {}  # term -> (name, source, url)
    for anns in list(complexes.values()) + list(pathways.values()):
        for a in anns:
            mech_names[a.id] = (a.name, a.source, a.url)
    for t in go.terms.values():
        mech_names[t.id] = (t.name, "Gene Ontology", f"https://amigo.geneontology.org/amigo/term/{t.id}")
    log("mechanism indexes: " + ", ".join(f"{n}={len(ix.ids)} genes" for n, ix in mech_index.items()))

    def interaction_bonus(g1: str, g2: str) -> float:
        score = partners.get(g1, {}).get(g2, 0) / 1000
        if not score:
            return 0.0
        hub = max(len(partners.get(g1, {})), len(partners.get(g2, {})))
        return PPI_WEIGHT * score * min(1.0, (PPI_HUB_DEGREE / hub) ** 0.5)

    condition_genes = sorted(gene_conditions)
    col = {g: j for j, g in enumerate(condition_genes)}
    gene_neighbors: dict[str, list[tuple[str, float]]] = {}
    for start in range(0, len(condition_genes), 512):
        block = condition_genes[start:start + 512]
        sims = sum(w * mech_index[n].dense(block, condition_genes) for n, w in MECH_WEIGHTS.items())
        for i, g in enumerate(block):
            row = sims[i]
            for p in partners.get(g, {}):
                if p in col:
                    row[col[p]] = 1 - (1 - row[col[p]]) * (1 - interaction_bonus(g, p))
            best = np.argsort(-row)[:80]
            gene_neighbors[g] = [(condition_genes[j], float(row[j])) for j in best if condition_genes[j] != g and row[j] > 0]
    log(f"gene mechanism neighbors for {len(gene_neighbors)} genes")

    pair_cache: dict[tuple[str, str], float] = {}

    def mech_similarity(g1: str, g2: str) -> float:
        if g1 == g2:
            return 1.0
        key = (g1, g2) if g1 < g2 else (g2, g1)
        if key not in pair_cache:
            weighted = sum(w * mech_index[n].similarity(g1, g2) for n, w in MECH_WEIGHTS.items())
            pair_cache[key] = 1 - (1 - weighted) * (1 - interaction_bonus(g1, g2))
        return pair_cache[key]

    # ---- body-system categories (MONDO ancestry) ----------------------------------------------------------
    by_name = {d.name: d.id for d in diseases.values()}
    categories = [(n, by_name[n]) for n in CATEGORY_NAMES if n in by_name]
    if missing := [n for n in CATEGORY_NAMES if n not in by_name]:
        log(f"category names not found in MONDO: {missing}")
    anc_cache: dict[str, frozenset[str]] = {}

    def ancestors(mid: str) -> frozenset[str]:
        if mid not in anc_cache:
            out = {mid}
            for p in diseases[mid].parents if mid in diseases else []:
                out |= ancestors(p)
            anc_cache[mid] = frozenset(out)
        return anc_cache[mid]

    def category_of(c: Condition) -> str:
        anc = ancestors(c.disease)
        return next((name for name, mid in categories if mid in anc), "other")

    # ---- variant effect per condition -----------------------------------------------------------------
    def effect_of(c: Condition) -> dict:
        votes, sources = Counter(), []
        for r in g2p_by_pair.get((c.disease, c.gene), []):
            if r.mechanism in G2P_EFFECTS:
                votes[G2P_EFFECTS[r.mechanism]] += 2
                sources.append({"source": "Gene2Phenotype", "value": r.mechanism, "support": r.mechanism_support, "url": r.url})
        eff = orpha_effect.get((c.disease, c.gene))
        if eff:
            votes[eff] += 1
            sources.append({"source": "Orphanet", "value": eff.replace("_", " ")})
        d = dosage.get(gene_table[c.gene].symbol, {})
        if d.get("haploinsufficiency_score") == "3":
            votes["loss_of_function"] += 1
            sources.append({"source": "ClinGen dosage", "value": "haploinsufficiency (sufficient evidence)", "url": d["url"]})
        return {"value": votes.most_common(1)[0][0] if votes else "unknown", "sources": sources}

    effects = {cid: effect_of(c) for cid, c in conditions.items()}

    def effect_relation(a: str, b: str) -> str:
        ea, eb = effects[a]["value"], effects[b]["value"]
        if "unknown" in (ea, eb):
            return "unknown"
        return "same" if ea == eb else "different"

    # ---- neighbors ----------------------------------------------------------------------------------------
    sym_top = symptom_index.top_k(with_symptoms, with_symptoms, k=60)
    log("symptom candidates computed")
    scored: dict[str, list[tuple]] = {}
    for cid in cond_ids:
        c = conditions[cid]
        cand = {o for o, _ in sym_top.get(cid, [])}
        for og, _ in gene_neighbors.get(c.gene, [])[:40]:
            cand |= set(gene_conditions[og])
        cand |= set(gene_conditions[c.gene])
        cand.discard(cid)
        scored[cid] = [(o, symptom_similarity(cid, o), mech_similarity(c.gene, conditions[o].gene)) for o in cand]
    sym_scale = float(np.percentile([s for v in scored.values() for s in sorted((x[1] for x in v), reverse=True)[:10]], 99))
    mech_scale = float(np.percentile([m for v in scored.values() for m in sorted((x[2] for x in v if x[2] < 1), reverse=True)[:10]], 99))
    log(f"scored candidates (scales: symptom {sym_scale:.3f}, mechanism {mech_scale:.3f})")

    def shared_symptoms(a: str, b: str, n: int = 5) -> list[str]:
        if a not in symptom_index or b not in symptom_index:
            return []
        shared = onto.most_specific(set(symptom_index.sets[a] & symptom_index.sets[b]))
        return sorted(shared, key=lambda t: -symptom_index.term_ic(t))[:n]

    def shared_mechanisms(g1: str, g2: str, n: int = 5) -> list[dict]:
        out = []
        if g2 in partners.get(g1, {}):
            out.append({"k": "interaction", "score": partners[g1][g2] / 1000})
        terms = []
        for name in ("complex", "pathway", "go"):
            for s in mech_index[name].shared_terms(g1, g2):
                terms.append((s.ic, name, s.term))
        for s in mech_index["partners"].shared_terms(g1, g2):
            p = s.term.removeprefix("PPI:")
            if p not in (g1, g2):
                terms.append((s.ic, "partner", p))
        go_terms = {t for _, k, t in terms if k == "go"}
        specific_go = go_terms - {a for t in go_terms for a in go.ancestors(t) if a != t}
        for ic, kind, term in sorted((x for x in terms if x[1] != "go" or x[2] in specific_go), key=lambda x: -x[0]):
            if len(out) >= n:
                break
            out.append({"k": kind, "id": term, "symbol": gene_table[term].symbol} if kind == "partner" else {"k": kind, "id": term})
        return out

    def combine(s_sym: float, s_mech: float) -> float:
        """Half plain average, half geometric mean: strong one-sided matches count, matches on both count most."""
        a, b = min(s_sym / sym_scale, 1.0), min(s_mech / mech_scale, 1.0)
        return 0.5 * (a + b) / 2 + 0.5 * (a * b) ** 0.5

    # Look-alikes: sister proteins (same HGNC gene family) whose conditions share almost no symptoms.
    family_members: dict[str, set[str]] = defaultdict(set)
    for g in condition_genes:
        for fam in gene_table[g].groups:
            family_members[fam].add(g)

    def lookalikes(cid: str, n: int = 4) -> list[dict]:
        c = conditions[cid]
        out = []
        for fam in gene_table[c.gene].groups:
            members = family_members[fam]
            if len(members) > 60:
                continue
            for g in members - {c.gene}:
                for o in gene_conditions[g]:
                    s_sym = symptom_similarity(cid, o)
                    if s_sym < 0.08:
                        out.append({"id": o, "family": fam, "sym": round(s_sym, 4), "mech": round(mech_similarity(c.gene, g), 4),
                                    "same_category": category_of(c) == category_of(conditions[o])})
        out.sort(key=lambda x: (x["same_category"], -x["mech"]))
        return out[:n]

    referenced_hpo: set[str] = set()
    referenced_mech: set[str] = set()
    with open(OUT / "neighbors.jsonl", "w", encoding="utf-8") as f:
        for cid in cond_ids:
            rows = [(combine(s_sym, min(s_mech, 0.999)), o, s_sym, s_mech) for o, s_sym, s_mech in scored[cid]]
            keep = {o for _, o, _, _ in sorted(rows, key=lambda x: -x[0])[:K_COMBINED]}
            keep |= {o for _, o, _, _ in sorted(rows, key=lambda x: -x[2])[:K_SYMPTOM]}
            keep |= {o for _, o, _, _ in sorted((r for r in rows if r[3] < 1), key=lambda x: -x[3])[:K_MECHANISM]}
            keep |= {o for _, o, _, m in rows if m == 1}  # same gene, other condition
            out = []
            for combined, o, s_sym, s_mech in sorted((r for r in rows if r[1] in keep), key=lambda x: -x[0]):
                g1, g2 = conditions[cid].gene, conditions[o].gene
                syms = shared_symptoms(cid, o)
                mechs = [] if g1 == g2 else shared_mechanisms(g1, g2)
                referenced_hpo.update(syms)
                referenced_mech.update(m["id"] for m in mechs if m["k"] in ("complex", "pathway", "go"))
                out.append({"id": o, "score": round(combined, 4), "sym": round(s_sym, 4), "mech": round(s_mech, 4),
                            "same_gene": g1 == g2, "effect": effect_relation(cid, o),
                            "same_category": category_of(conditions[cid]) == category_of(conditions[o]),
                            "symptoms": syms, "mechanisms": mechs})
            looks = lookalikes(cid)
            referenced_hpo.update(s for x in looks for s in shared_symptoms(cid, x["id"]))
            f.write(json.dumps({"id": cid, "neighbors": out, "lookalikes": looks}, ensure_ascii=False) + "\n")
    log("wrote neighbors.jsonl")

    # ---- groups -------------------------------------------------------------------------------------------
    group_members: dict[str, set[str]] = defaultdict(set)
    for c in conditions.values():
        for a in ancestors(c.disease) - ({c.disease} if not c.synthetic else set()):
            group_members[a].add(c.id)
    groups = [{"id": g, "name": diseases[g].name, "definition": diseases[g].definition,
               "synonyms": [s for s, scope in diseases[g].synonyms if scope == "EXACT"][:8], "members": sorted(m)}
              for g, m in group_members.items() if 2 <= len(m) <= 800 and g in diseases]
    with open(OUT / "groups.jsonl", "w", encoding="utf-8") as f:
        for g in groups:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    log(f"groups: {len(groups)}")

    # ---- conditions -------------------------------------------------------------------------------------
    prevalence = orphanet.load_prevalence()

    def prevalence_of(mid: str) -> dict | None:
        orpha_ids = [x.replace("Orphanet:", "ORPHA:") for x in diseases[mid].equivalent("Orphanet")]
        items = [p for o in orpha_ids for p in prevalence.get(o, [])]
        point = [p for p in items if p.kind in ("Point prevalence", "Prevalence at birth") and p.klass not in ("", "Unknown", "Not yet documented")]
        point.sort(key=lambda p: (p.geography != "Worldwide", p.source != "ORPHANET", not p.validated))
        cases = [p for p in items if p.kind == "Cases/families" and p.value]
        cases.sort(key=lambda p: (p.geography != "Worldwide", -(p.value or 0)))
        if not point and not cases:
            return None
        return {"class": point[0].klass if point else None, "class_kind": point[0].kind if point else None,
                "class_geography": point[0].geography if point else None,
                "cases": int(cases[0].value) if cases else None, "cases_source": cases[0].source if cases else None,
                "source": "Orphanet", "url": f"https://www.orpha.net/en/disease/detail/{orpha_ids[0].split(':')[1]}"}

    def names_of(c: Condition) -> tuple[str, list[str]]:
        d = diseases[c.disease]
        symbol = gene_table[c.gene].symbol
        g2p_names = sorted({r.disease_name for r in g2p_by_pair.get((c.disease, c.gene), []) if r.confidence not in ("disputed", "refuted")})
        names = list(g2p_names)
        names += [s for s, scope in d.synonyms if scope == "EXACT" and f"{symbol}-related" in s]
        names.append(f"{symbol}-related {d.name}" if c.synthetic else d.name)
        names += ([d.name] if c.synthetic else []) + [s for s, scope in d.synonyms if scope == "EXACT"]
        names += [diseases[u].name for u in umbrella_of.get(c.disease, [])]
        seen, unique = set(), []
        for n in names:
            if n.lower() not in seen:
                seen.add(n.lower())
                unique.append(n)
        return unique[0][0].upper() + unique[0][1:], unique[1:]

    with open(OUT / "conditions.jsonl", "w", encoding="utf-8") as f:
        for cid in cond_ids:
            c = conditions[cid]
            d = diseases[c.disease]
            title, aka = names_of(c)
            evidence = [{k: v for k, v in e.items() if k != "strength" and v} for e in links[(c.disease, c.gene)]]
            other_genes = sorted(gene_table[g].symbol for g in candidates.get(c.disease, set()) if g != c.gene)
            phen = [{"id": h, "frequency": e["frequency"], "sources": sorted(set(e["sources"]))[:6], "refs": e["refs"]}
                    for h, e in cond_pheno[cid].items()]
            phen.sort(key=lambda p: -(symptom_index.term_ic(p["id"]) if p["id"] in symptom_index.col else 0))
            referenced_hpo.update(p["id"] for p in phen)
            row = {
                "id": cid, "name": title, "also_known_as": aka[:15], "disease": c.disease, "disease_name": d.name,
                "synthetic": c.synthetic, "definition": d.definition, "category": category_of(c),
                "gene": {"hgnc_id": c.gene, "symbol": gene_table[c.gene].symbol, "strength": genes_of[c.disease][c.gene], "evidence": evidence},
                "other_genes_for_this_disease": other_genes,
                "variant_effect": effects[cid],
                "inheritance": sorted(inheritance.get(c.disease, set())),
                "onset": sorted({onto.label(t) for t in course.get(c.disease, set()) if ONSET_ROOT in onto.ancestors(t)}),
                "prevalence": prevalence_of(c.disease),
                "phenotypes": phen,
                "xrefs": {p: d.equivalent(p) for p in ("OMIM", "Orphanet", "GARD", "MEDGEN", "DOID", "MESH") if d.equivalent(p)},
                "subsets": sorted(d.subsets), "umbrella_terms": umbrella_of.get(c.disease, []),
                "source_records": records_of.get(c.disease, []),
                "url": f"https://monarchinitiative.org/{c.disease}",
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    log("wrote conditions.jsonl")

    # ---- genes --------------------------------------------------------------------------------------------
    with open(OUT / "genes.jsonl", "w", encoding="utf-8") as f:
        for g in condition_genes:
            gt = gene_table[g]
            pw = sorted(pathways.get(g, []), key=lambda a: -mech_index["pathway"].term_ic(a.id))[:12]
            gd = sorted((a for a in go_direct.get(g, []) if a.id in mech_index["go"].col), key=lambda a: -mech_index["go"].term_ic(a.id))[:20]
            cx = complexes.get(g, [])
            referenced_mech.update(a.id for a in pw + gd + cx)
            f.write(json.dumps({
                "hgnc_id": g, "symbol": gt.symbol, "name": gt.name, "aliases": gt.aliases, "previous_symbols": gt.previous,
                "gene_groups": gt.groups, "uniprot": gt.uniprot_ids, "entrez": gt.entrez_id, "conditions": sorted(gene_conditions[g]),
                "complexes": [a.id for a in cx], "pathways": [a.id for a in pw], "go": [a.id for a in gd],
                "partners": [{"hgnc_id": p, "symbol": gene_table[p].symbol, "score": s / 1000, "has_condition": p in gene_conditions}
                             for p, s in sorted(partners.get(g, {}).items(), key=lambda x: -x[1])[:25]],
                "dosage": dosage.get(gt.symbol),
                "mechanism_neighbors": [{"hgnc_id": o, "symbol": gene_table[o].symbol, "score": round(s, 4)} for o, s in gene_neighbors.get(g, [])[:25]],
                "url": f"https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/{g}",
            }, ensure_ascii=False) + "\n")

    # ---- dictionaries ----------------------------------------------------------------------------------------
    with open(OUT / "phenotypes.jsonl", "w", encoding="utf-8") as f:
        for h in sorted(referenced_hpo):
            t = onto.terms[h]
            f.write(json.dumps({"id": h, "name": t.name, "plain": t.layperson[:3], "synonyms": t.synonyms[:8], "definition": t.definition,
                                "conditions_with_it": symptom_index.term_count(h) if h in symptom_index.col else 0}, ensure_ascii=False) + "\n")
    term_genes: dict[str, set[str]] = defaultdict(set)
    for name in ("complex", "pathway"):
        for g in condition_genes:
            for t in mech_sets[name][g]:
                term_genes[t].add(g)
    for g in condition_genes:
        for a in go_direct.get(g, []):
            term_genes[a.id].add(g)
    with open(OUT / "mechanisms.jsonl", "w", encoding="utf-8") as f:
        for term in sorted(referenced_mech | {t for t, gs in term_genes.items() if 2 <= len(gs) <= 300}):
            label, source, url = mech_names.get(term, (term, "", ""))
            kind = "complex" if term.startswith("CPX-") else "pathway" if term.startswith("R-HSA") else "go"
            ix = mech_index[kind]
            f.write(json.dumps({"id": term, "name": label, "source": source, "url": url,
                                "genes_with_it": ix.term_count(term) if term in ix.col else 0,
                                "condition_genes": sorted(gene_table[g].symbol for g in term_genes.get(term, ()))[:300]},
                               ensure_ascii=False) + "\n")

    # ---- search index ----------------------------------------------------------------------------------------
    with open(OUT / "search.jsonl", "w", encoding="utf-8") as f:
        def emit(text: str, kind: str, ref: str, label: str) -> None:
            if text:
                f.write(json.dumps({"text": text, "kind": kind, "id": ref, "label": label}, ensure_ascii=False) + "\n")
        for cid in cond_ids:
            c = conditions[cid]
            title, aka = names_of(c)
            ids = diseases[c.disease].equivalent("OMIM") + diseases[c.disease].equivalent("Orphanet")
            for text in [title] + aka + ([] if c.synthetic else ids + [c.disease]):
                emit(text, "condition", cid, title)
        for g in condition_genes:
            gt = gene_table[g]
            for text in [gt.symbol, gt.name] + gt.aliases + gt.previous:
                emit(text, "gene", g, gt.symbol)
        for h in sorted(referenced_hpo):
            t = onto.terms[h]
            for text in [t.name] + t.layperson + t.synonyms[:5]:
                emit(text, "symptom", h, t.name)
        for g in groups:
            for text in [g["name"]] + g["synonyms"]:
                emit(text, "group", g["id"], g["name"])
        for term, gs in term_genes.items():
            if term in mech_names and 2 <= len(gs) <= 200:
                emit(mech_names[term][0], "mechanism", term, mech_names[term][0])
    log("wrote genes, dictionaries, search index")

    report = {
        "conditions": len(conditions), "conditions_split_from_multi_gene_diseases": sum(c.synthetic for c in conditions.values()),
        "genes": len(condition_genes), "groups": len(groups),
        "umbrella_terms": len({u for us in umbrella_of.values() for u in us}), "multi_gene_diseases": len(multi),
        "conditions_with_symptoms": len(with_symptoms),
        "conditions_with_known_variant_effect": sum(1 for e in effects.values() if e["value"] != "unknown"),
        "variant_effects": Counter(e["value"] for e in effects.values()),
        "conditions_with_prevalence": sum(1 for c in conditions.values() if prevalence_of(c.disease)),
        "categories": Counter(category_of(c) for c in conditions.values()),
        "genes_with_complex": sum(1 for g in condition_genes if complexes.get(g)),
        "genes_with_pathway": sum(1 for g in condition_genes if pathways.get(g)),
        "genes_with_go": sum(1 for g in condition_genes if go_direct.get(g)),
        "genes_with_partners": sum(1 for g in condition_genes if partners.get(g)),
        "scales": {"symptom": sym_scale, "mechanism": mech_scale, "information_floor": info_floor},
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2))
    log(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
