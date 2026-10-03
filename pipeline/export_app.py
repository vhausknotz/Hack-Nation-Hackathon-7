"""Export the built graph (data/build/) into the web app's static data bundles (app/public/data/).

Each entity page needs exactly one fetch: entities are grouped into shard files by a stable hash of
their ID (FNV-1a, mirrored in app/src/lib/data.ts), and every bundle carries the labels it references.
Usage: python pipeline/export_app.py
"""

import json
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"
OUT = ROOT / "app" / "public" / "data"
SHARDS = {"c": 256, "g": 128, "s": 128, "grp": 64, "m": 128}
MAX_NEIGHBORS = 20
MAX_SYMPTOMS = 80
MAX_LIST = 250


def fnv1a(text: str) -> int:
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def shard_of(kind: str, key: str) -> int:
    return fnv1a(key) % SHARDS[kind]


def load(name: str) -> list[dict]:
    with open(BUILD / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> None:
    conditions = {c["id"]: c for c in load("conditions.jsonl")}
    neighbors = {n["id"]: n for n in load("neighbors.jsonl")}
    genes = {g["hgnc_id"]: g for g in load("genes.jsonl")}
    phenotypes = {p["id"]: p for p in load("phenotypes.jsonl")}
    mechanisms = {m["id"]: m for m in load("mechanisms.jsonl")}
    groups = {g["id"]: g for g in load("groups.jsonl")}
    report = json.loads((BUILD / "report.json").read_text())
    gene_by_symbol = {g["symbol"]: g for g in genes.values()}

    if OUT.exists():
        shutil.rmtree(OUT)
    shards: dict[str, dict[int, dict]] = {k: defaultdict(dict) for k in SHARDS}

    def symptom_entry(h: str) -> list:
        p = phenotypes.get(h, {})
        return [p.get("name", h), (p.get("plain") or [None])[0], p.get("conditions_with_it", 0)]

    def mech_entry(m: str) -> list:
        """[name, genes with it]; the source and URL follow from the ID (see app/src/lib/links.ts)."""
        t = mechanisms.get(m, {})
        return [t.get("name", m), t.get("genes_with_it", 0)]

    def brief(cid: str) -> dict:
        c = conditions[cid]
        return {"id": cid, "name": c["name"], "gene": c["gene"]["symbol"], "category": c["category"]}

    # ---- conditions -----------------------------------------------------------------------------------
    for cid, c in conditions.items():
        nb = neighbors.get(cid, {"neighbors": [], "lookalikes": []})
        sym_dict, mech_dict = {}, {}
        rows = []
        for x in nb["neighbors"][:MAX_NEIGHBORS]:
            for s in x["symptoms"]:
                sym_dict[s] = symptom_entry(s)
            for m in x["mechanisms"]:
                if m["k"] in ("complex", "pathway", "go"):
                    mech_dict[m["id"]] = mech_entry(m["id"])
            rows.append({**brief(x["id"]), **{k: x[k] for k in ("score", "sym", "mech", "same_gene", "effect", "same_category", "symptoms", "mechanisms")}})
        looks = [{**brief(x["id"]), **{k: x[k] for k in ("family", "sym", "mech", "same_category")}} for x in nb.get("lookalikes", [])]
        phen = c["phenotypes"][:MAX_SYMPTOMS]
        for p in phen:
            sym_dict[p["id"]] = symptom_entry(p["id"])
        g = genes.get(c["gene"]["hgnc_id"], {})
        for m in g.get("complexes", []) + g.get("pathways", [])[:6] + g.get("go", [])[:8]:
            mech_dict[m] = mech_entry(m)
        bundle = {
            "id": cid, "name": c["name"], "also_known_as": c["also_known_as"][:10], "disease": c["disease"], "disease_name": c["disease_name"],
            "synthetic": c["synthetic"], "definition": c["definition"], "category": c["category"],
            "gene": {**c["gene"], "name": g.get("name", ""), "evidence": [{k: e.get(k) for k in ("source", "confidence", "mechanism", "inheritance", "url", "date", "pmids") if e.get(k)} for e in c["gene"]["evidence"]]},
            "other_genes_for_this_disease": c["other_genes_for_this_disease"][:20],
            "variant_effect": c["variant_effect"], "inheritance": c["inheritance"], "onset": c["onset"], "prevalence": c["prevalence"],
            "phenotypes": [{"id": p["id"], "frequency": p["frequency"], "sources": p["sources"][:4], "refs": p["refs"][:3]} for p in phen],
            "phenotype_count": len(c["phenotypes"]),
            "xrefs": c["xrefs"], "url": c["url"],
            "machinery": {"complexes": g.get("complexes", []), "pathways": g.get("pathways", [])[:6], "go": g.get("go", [])[:8],
                          "partners": g.get("partners", [])[:12], "dosage": g.get("dosage")},
            "other_conditions_of_gene": [brief(o) for o in g.get("conditions", []) if o != cid],
            "neighbors": rows, "lookalikes": looks,
            "dict": {"symptoms": sym_dict, "mechanisms": mech_dict},
        }
        shards["c"][shard_of("c", cid)][cid] = bundle

    # ---- genes ------------------------------------------------------------------------------------------
    for gid, g in genes.items():
        mech_dict = {m: mech_entry(m) for m in g["complexes"] + g["pathways"] + g["go"]}
        shards["g"][shard_of("g", g["symbol"])][g["symbol"]] = {
            **{k: g[k] for k in ("hgnc_id", "symbol", "name", "aliases", "previous_symbols", "gene_groups", "uniprot", "entrez", "complexes",
                                 "pathways", "go", "partners", "dosage", "mechanism_neighbors", "url")},
            "conditions": [{**brief(c), "effect": conditions[c]["variant_effect"]["value"], "phenotype_count": len(conditions[c]["phenotypes"]),
                            "inheritance": conditions[c]["inheritance"]} for c in g["conditions"]],
            "dict": {"mechanisms": mech_dict},
        }

    # ---- symptoms ----------------------------------------------------------------------------------------
    by_symptom: dict[str, list[tuple]] = defaultdict(list)
    for cid, c in conditions.items():
        for p in c["phenotypes"]:
            by_symptom[p["id"]].append((cid, p["frequency"]))
    for h, p in phenotypes.items():
        rows = by_symptom.get(h, [])
        shards["s"][shard_of("s", h)][h] = {
            "id": h, "name": p["name"], "plain": p["plain"], "synonyms": p["synonyms"], "definition": p["definition"],
            "conditions_with_it": p["conditions_with_it"], "direct_count": len(rows),
            "conditions": [{**brief(cid), "frequency": freq} for cid, freq in rows[:MAX_LIST]],
            "url": f"https://hpo.jax.org/browse/term/{h}",
        }

    # ---- groups -------------------------------------------------------------------------------------------
    for gid, gr in groups.items():
        shards["grp"][shard_of("grp", gid)][gid] = {
            "id": gid, "name": gr["name"], "definition": gr["definition"], "synonyms": gr["synonyms"], "member_count": len(gr["members"]),
            "conditions": [brief(m) for m in gr["members"][:MAX_LIST]], "url": f"https://monarchinitiative.org/{gid}",
        }

    # ---- mechanisms ---------------------------------------------------------------------------------------
    for mid, m in mechanisms.items():
        conds = []
        for sym in m["condition_genes"]:
            for cid in gene_by_symbol.get(sym, {}).get("conditions", []):
                conds.append(brief(cid))
        if not m["condition_genes"]:
            continue
        shards["m"][shard_of("m", mid)][mid] = {
            "id": mid, "name": m["name"], "source": m["source"], "url": m["url"], "genes_with_it": m["genes_with_it"],
            "condition_genes": m["condition_genes"], "conditions": conds[:MAX_LIST], "condition_count": len(conds),
        }

    # ---- write shards ----------------------------------------------------------------------------------------
    total = 0
    for kind, by_shard in shards.items():
        (OUT / kind).mkdir(parents=True, exist_ok=True)
        for n, items in by_shard.items():
            text = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
            (OUT / kind / f"{n}.json").write_text(text, encoding="utf-8")
            total += len(text.encode("utf-8"))

    # ---- search index: [text, kind, id, label, extra] ----------------------------------------------------------
    kind_code = {"condition": "c", "gene": "g", "symptom": "s", "group": "grp", "mechanism": "m"}
    entries, seen = [], set()
    with open(BUILD / "search.jsonl", encoding="utf-8") as f:
        for r in map(json.loads, f):
            kind = kind_code[r["kind"]]
            if kind == "m" and r["id"] not in shards["m"][shard_of("m", r["id"])]:
                continue
            ref = gene_by_symbol[r["label"]]["symbol"] if kind == "g" else r["id"]
            key = (r["text"].lower(), kind, ref)
            if key in seen:
                continue
            seen.add(key)
            extra = ""
            if kind == "c":
                extra = conditions[r["id"]]["gene"]["symbol"]
            elif kind == "s":
                extra = str(phenotypes.get(r["id"], {}).get("conditions_with_it", ""))
            elif kind == "g":
                extra = str(len(gene_by_symbol[r["label"]]["conditions"]))
            entries.append([r["text"], kind, ref, r["label"] if r["label"] != r["text"] else "", extra])
    (OUT / "search.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    shutil.copyfile(BUILD / "map.json", OUT / "map.json")

    meta = {
        "built": date.today().isoformat(), "shards": SHARDS, "counts": report,
        "sources": json.loads((ROOT / "data" / "sources_manifest.json").read_text()),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {sum(len(v) for v in shards.values())} shard files ({total / 1e6:.1f} MB) and search index with {len(entries)} entries "
          f"({(OUT / 'search.json').stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
