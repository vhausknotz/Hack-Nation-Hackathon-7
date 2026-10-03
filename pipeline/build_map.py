"""Build the star map: a 2D position for every condition, clusters ("constellations") and their names.

- Position: UMAP over the combined similarity (shared symptoms + shared machinery), so conditions that
  share biology sit close together. Conditions with too little data to compare form a faint outer ring.
- Clusters: Louvain communities on the nearest-neighbor graph.
- Names: GPT-6 Sol names each cluster in plain words from what its members demonstrably share
  (enriched symptoms and machinery), and the label says it was named by AI.
Output: data/build/map.json (copied into the app by export_app.py).
Usage: python pipeline/build_map.py
"""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np

import llm

BUILD = Path(__file__).resolve().parent.parent / "data" / "build"
K_LAYOUT = 15  # neighbors per condition fed to the layout
K_EDGES = 3  # neighbors per condition drawn as faint lines on the map
MIN_LABELED_CLUSTER = 6
NAMING_MODEL = "gpt-6-sol"


def load(name: str) -> list[dict]:
    with open(BUILD / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> None:
    conditions = load("conditions.jsonl")
    neighbors = {r["id"]: r["neighbors"] for r in load("neighbors.jsonl")}
    genes = {g["symbol"]: g for g in load("genes.jsonl")}
    phenotypes = {p["id"]: p for p in load("phenotypes.jsonl")}
    mechanisms = {m["id"]: m for m in load("mechanisms.jsonl")}
    ids = [c["id"] for c in conditions]
    index = {cid: i for i, cid in enumerate(ids)}
    by_id = {c["id"]: c for c in conditions}
    n = len(ids)

    # ---- similarity graph ------------------------------------------------------------------------------
    graph = nx.Graph()
    graph.add_nodes_from(range(n))
    for cid, rows in neighbors.items():
        i = index[cid]
        for x in sorted(rows, key=lambda r: -r["score"])[:K_LAYOUT]:
            j = index[x["id"]]
            s = float(x["score"])
            if graph.has_edge(i, j):
                graph[i][j]["weight"] = max(graph[i][j]["weight"], s)
            else:
                graph.add_edge(i, j, weight=s)

    # ---- layout: UMAP over each condition's full profile (symptoms + its gene's machinery) -------------------
    import umap  # imported late: slow to import
    from scipy import sparse
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    from sources import hgnc, hpo, mechanism

    onto = hpo.load_ontology()
    gene_table = hgnc.load()
    symbols = hgnc.symbol_index(gene_table)
    uniprot = mechanism.uniprot_to_hgnc(gene_table)
    cpx, rea = mechanism.load_complexes(uniprot), mechanism.load_reactome(uniprot)
    go_direct, go = mechanism.load_go(symbols)

    def symptom_terms(c):
        out = set()
        for p in c["phenotypes"]:
            if p["id"] in onto.terms:
                out |= {t for t in onto.ancestors(p["id"]) if onto.is_phenotypic_abnormality(t)}
        return out

    def machinery_terms(c):
        g = c["gene"]["hgnc_id"]
        out = {a.id for a in cpx.get(g, [])} | {a.id for a in rea.get(g, [])}
        for a in go_direct.get(g, []):
            out |= go.ancestors(a.id)
        return out - {"GO:0008150", "GO:0005575", "GO:0003674"}

    def tfidf(term_sets):
        vocab = {}
        df = Counter(t for ts in term_sets for t in ts)
        rows, cols, vals = [], [], []
        for i, ts in enumerate(term_sets):
            for t in ts:
                if df[t] < 2:
                    continue
                rows.append(i)
                cols.append(vocab.setdefault(t, len(vocab)))
                vals.append(math.log(n / df[t]))
        return normalize(sparse.csr_matrix((vals, (rows, cols)), shape=(n, max(len(vocab), 1))))

    sym_x = tfidf([symptom_terms(by_id[cid]) for cid in ids])
    mech_x = tfidf([machinery_terms(by_id[cid]) for cid in ids])
    features_x = sparse.hstack([sym_x / math.sqrt(2), mech_x / math.sqrt(2)]).tocsr()
    has_features = np.asarray(features_x.getnnz(axis=1) > 0)
    placed = [i for i in range(n) if has_features[i]]
    print(f"{len(placed)} of {n} conditions have a profile; {n - len(placed)} go to the outer ring")
    reduced = normalize(TruncatedSVD(n_components=100, random_state=42).fit_transform(features_x[placed]))
    coords = umap.UMAP(n_neighbors=30, min_dist=0.08, metric="cosine", random_state=42).fit_transform(reduced)
    coords -= np.median(coords, axis=0)
    radius = float(np.percentile(np.linalg.norm(coords, axis=1), 99))
    coords = coords / radius * 1000.0
    xy = np.zeros((n, 2), dtype=np.float32)
    xy[placed] = coords
    unplaced = [i for i in range(n) if not has_features[i]]
    for k, i in enumerate(unplaced):  # faint outer ring for conditions without enough data
        angle = 2 * math.pi * k / max(len(unplaced), 1)
        r = 1250 + 40 * ((k * 7919) % 5)
        xy[i] = (r * math.cos(angle), r * math.sin(angle))
    print("layout done")

    # ---- clusters: two levels, found in the same profile space the layout uses --------------------------
    from sklearn.neighbors import NearestNeighbors

    knn = NearestNeighbors(n_neighbors=16, metric="cosine").fit(reduced)
    dist, nbr = knn.kneighbors(reduced)
    profile_graph = nx.Graph()
    profile_graph.add_nodes_from(placed)
    for row, (ds, js) in enumerate(zip(dist, nbr)):
        for d_, j in zip(ds[1:], js[1:]):
            profile_graph.add_edge(placed[row], placed[j], weight=float(max(1e-3, 1 - d_)))

    def communities_at(resolution: float) -> tuple[list[set[int]], np.ndarray]:
        comms = sorted(nx.community.louvain_communities(profile_graph, weight="weight", resolution=resolution, seed=42), key=len, reverse=True)
        of = np.full(n, -1, dtype=np.int32)
        for k, members in enumerate(comms):
            for i in members:
                of[i] = k
        return comms, of

    regions, region_of = communities_at(0.6)
    constellations, constellation_of = communities_at(3.0)
    print(f"{len(regions)} regions, {len(constellations)} constellations")

    # ---- what each cluster shares ----------------------------------------------------------------------------
    pheno_df = Counter(p["id"] for c in conditions for p in c["phenotypes"])
    mech_df = Counter()
    gene_terms = {}
    for sym, g in genes.items():
        terms = set(g["complexes"]) | set(g["pathways"]) | set(g["go"])
        gene_terms[sym] = terms
        mech_df.update(terms)

    def features(members: set[int]) -> dict:
        size = len(members)
        cats = Counter(by_id[ids[i]]["category"] for i in members)
        pc, mc = Counter(), Counter()
        for i in members:
            c = by_id[ids[i]]
            pc.update({p["id"] for p in c["phenotypes"]})
            mc.update(gene_terms.get(c["gene"]["symbol"], set()))

        def top(counter, df, total, names, k=6):
            scored = [(cnt / size * math.log(total / df[t]), t) for t, cnt in counter.items() if cnt >= max(2, size * 0.15) and df[t]]
            return [names(t) for _, t in sorted(scored, reverse=True)[:k]]

        central = sorted(members, key=lambda i: -profile_graph.degree(i, weight="weight"))[:12]
        return {
            "size": size,
            "body_systems": [c for c, _ in cats.most_common(3)],
            "shared_symptoms": top(pc, pheno_df, n, lambda t: phenotypes.get(t, {}).get("name", t)),
            "shared_machinery": top(mc, mech_df, len(genes), lambda t: mechanisms.get(t, {}).get("name", t)),
            "example_members": [by_id[ids[i]]["name"] for i in central],
        }

    def name_all(comms: list[set[int]], level: str, min_size: int) -> list[dict]:
        labeled = [k for k, m in enumerate(comms) if len(m) >= min_size]
        feats = {k: features(comms[k]) for k in labeled}
        names: dict[int, dict] = {}
        for start in range(0, len(labeled), 12):
            chunk = labeled[start:start + 12]
            reply = llm.chat_json(NAMING_MODEL, [
                {"role": "system", "content": (
                    "You name areas on a map of rare genetic diseases for families with no science background. "
                    f"These are {'large regions' if level == 'region' else 'small, specific groups'}. "
                    "For each, use ONLY the features given: what its members share. Return JSON "
                    '{"clusters": [{"id": <id>, "name": <2-4 plain words, Title Case, no gene symbols, no word \'cluster\'>, '
                    '"blurb": <one plain sentence, max 18 words, saying what these conditions have in common>}]}. '
                    + ("Name the broad area of the body or the cell it is about." if level == "region"
                       else "Be specific: name the particular machinery, organ or feature that sets this group apart.")
                    + " Do not invent facts. Each name must be distinct from the others in this request.")},
                {"role": "user", "content": json.dumps([{"id": k, **feats[k]} for k in chunk], ensure_ascii=False)},
            ], task=f"map-{level}-names")
            for item in reply.get("clusters", []):
                names[int(item["id"])] = {"name": item["name"], "blurb": item.get("blurb", "")}
        print(f"named {len(names)} {level}s")
        out = []
        for k in labeled:
            members = list(comms[k])
            cx, cy = np.median(xy[members], axis=0)
            out.append({"id": k, "level": level, "name": names.get(k, {}).get("name", ""), "blurb": names.get(k, {}).get("blurb", ""),
                        "x": round(float(cx), 1), "y": round(float(cy), 1), "size": len(members), "named_by": NAMING_MODEL,
                        "features": feats[k]})
        return out

    region_labels = name_all(regions, "region", MIN_LABELED_CLUSTER)
    constellation_labels = name_all(constellations, "constellation", 8)

    # ---- write ---------------------------------------------------------------------------------------------
    categories = sorted({c["category"] for c in conditions}, key=lambda c: (c == "other", c))
    cat_index = {c: i for i, c in enumerate(categories)}
    edges = set()
    for cid, rows in neighbors.items():
        i = index[cid]
        for x in sorted(rows, key=lambda r: -r["score"])[:K_EDGES]:
            j = index[x["id"]]
            edges.add((min(i, j), max(i, j), round(float(x["score"]), 3)))
    out = {
        "categories": categories,
        # [id, name, gene, x, y, region, constellation, category, connections]
        "nodes": [[cid, by_id[cid]["name"], by_id[cid]["gene"]["symbol"], round(float(xy[i, 0]), 1), round(float(xy[i, 1]), 1),
                   int(region_of[i]), int(constellation_of[i]), cat_index[by_id[cid]["category"]], int(graph.degree(i))] for i, cid in enumerate(ids)],
        "edges": sorted(edges),
        "regions": region_labels,
        "constellations": constellation_labels,
        "unplaced": len(unplaced),
    }
    (BUILD / "map.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote map.json: {n} nodes, {len(edges)} edges, {len(region_labels)} regions, {len(constellation_labels)} constellations")
    print(json.dumps(llm.usage_summary(), indent=1))


if __name__ == "__main__":
    main()
