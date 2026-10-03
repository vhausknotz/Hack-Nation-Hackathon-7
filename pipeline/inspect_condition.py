"""Print a condition from the built graph with its neighbors and the reasons behind them.

Usage: python pipeline/inspect_condition.py <condition id | gene symbol> [more ...] [--n 10]
"""

import json
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent / "data" / "build"


def load(name: str, key: str = "id") -> dict:
    with open(BUILD / name, encoding="utf-8") as f:
        return {r[key]: r for r in map(json.loads, f)}


def main(args: list[str]) -> None:
    n = int(args[args.index("--n") + 1]) if "--n" in args else 10
    queries = [a for i, a in enumerate(args) if a != "--n" and (i == 0 or args[i - 1] != "--n")]
    conditions, neighbors = load("conditions.jsonl"), load("neighbors.jsonl")
    phenotypes, mechanisms, genes = load("phenotypes.jsonl"), load("mechanisms.jsonl"), load("genes.jsonl", "hgnc_id")
    by_symbol = {g["symbol"]: g for g in genes.values()}

    def mech_label(m: dict, via: list[str]) -> str:
        if m["k"] == "interaction":
            return f"{via[0]} and {via[1]} physically interact ({m['score']:.2f})"
        if m["k"] == "partner":
            return f"both interact with {m.get('symbol', m['id'])}"
        t = mechanisms.get(m["id"], {})
        return f"{t.get('name', m['id'])} [{m['k']}, {t.get('genes_with_it', '?')} genes]"

    for q in queries:
        ids = [q] if q in conditions else by_symbol.get(q.upper(), {}).get("conditions", [])
        if not ids:
            print(f"{q}: not found")
        for cid in ids:
            c = conditions[cid]
            print(f"\n### {c['name']}  ({cid})  gene={c['gene']['symbol']}  effect={c['variant_effect']['value']}  "
                  f"symptoms={len(c['phenotypes'])}  category={c['category']}")
            print(f"    aka: {c['also_known_as'][:4]}")
            if c["prevalence"]:
                print(f"    prevalence: {c['prevalence']['class']}  cases: {c['prevalence']['cases']}")
            for x in neighbors[cid]["neighbors"][:n]:
                o = conditions[x["id"]]
                tag = "SAME GENE " if x["same_gene"] else ""
                print(f"  {x['score']:.2f}  sym={x['sym']:.2f} mech={x['mech']:.2f}  {tag}{o['name'][:60]}  [{o['gene']['symbol']}]  effect:{x['effect']}")
                via = [c["gene"]["symbol"], o["gene"]["symbol"]]
                if x["mechanisms"]:
                    print("        machinery: " + "; ".join(mech_label(m, via) for m in x["mechanisms"][:3]))
                if x["symptoms"]:
                    print("        symptoms:  " + "; ".join(f"{phenotypes[s]['name']} ({phenotypes[s]['conditions_with_it']})" for s in x["symptoms"][:3]))
            for x in neighbors[cid].get("lookalikes", []):
                o = conditions[x["id"]]
                print(f"  LOOK-ALIKE  {o['name'][:60]}  [{o['gene']['symbol']}]  family: {x['family']}  sym={x['sym']:.2f} mech={x['mech']:.2f}  "
                      f"{'same body system' if x['same_category'] else 'different body system: ' + o['category']}")


if __name__ == "__main__":
    main(sys.argv[1:])
