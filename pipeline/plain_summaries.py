"""One plain sentence per condition, for "You are here": what this is, in words a parent can follow.

    python pipeline/plain_summaries.py [--limit N]

GPT-6 Luna rewrites only the facts it is given (MONDO definition, the most informative HPO symptoms
with their everyday names, inheritance, onset, gene). The app labels the result as written by AI from
those sources and shows the sources one tap away. A deterministic guard rejects summaries that introduce
numbers absent from the input. Output: data/build/plain.jsonl (cached, so reruns are free).
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import llm

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"
MODEL, PROMPT = "gpt-6-luna", "plain-summary@1"
SYSTEM = (
    "You write for parents who just heard a diagnosis and have no medical background. Rewrite the facts given into "
    "one or two short sentences (at most 40 words) saying what this condition is and how it usually shows. Rules: "
    "use only the facts given; everyday words (explain an unavoidable medical word in a few words); say it is a rare "
    "genetic condition caused by changes in the named gene; describe the most telling signs, not every sign; no "
    "statistics, life expectancy, prognosis or treatments; calm and factual, never alarming; if the facts are thin, "
    'say less rather than guess. Return JSON {"summary": "..."}.'
)


def facts(c: dict, genes: dict, pheno: dict) -> dict:
    signs = []
    for p in c["phenotypes"][:12]:
        t = pheno.get(p["id"], {})
        name = (t.get("plain") or [None])[0] or t.get("name", p["id"])
        if name not in signs:
            signs.append(name)
    return {
        "condition": c["name"],
        "other_names": c["also_known_as"][:3],
        "gene": f"{c['gene']['symbol']} ({genes.get(c['gene']['hgnc_id'], {}).get('name', '')})",
        "definition": c["definition"],
        "signs_recorded": signs,
        "inheritance": c["inheritance"],
        "onset": c["onset"],
        "body_system": c["category"],
    }


def summarize(c: dict, genes: dict, pheno: dict) -> dict | None:
    f = facts(c, genes, pheno)
    try:
        reply = llm.chat_json(MODEL, [{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": json.dumps(f, ensure_ascii=False)}], task=PROMPT)
    except Exception as e:  # noqa: BLE001 - one failure must not stop the batch
        print(f"{c['id']}: {e}", file=sys.stderr)
        return None
    text = str(reply.get("summary", "")).strip()
    source_digits = set(re.findall(r"\d+", json.dumps(f)))
    if not text or len(text.split()) > 60 or any(d not in source_digits for d in re.findall(r"\d+", text)):
        return None
    return {"id": c["id"], "summary": text, "model": MODEL, "prompt": PROMPT}


def main(args: list[str]) -> None:
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    load = lambda name: [json.loads(line) for line in open(BUILD / name, encoding="utf-8")]  # noqa: E731
    conditions = load("conditions.jsonl")[:limit]
    genes = {g["hgnc_id"]: g for g in load("genes.jsonl")}
    pheno = {p["id"]: p for p in load("phenotypes.jsonl")}
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda c: summarize(c, genes, pheno), conditions))
    ok = [r for r in results if r]
    with open(BUILD / "plain.jsonl", "w", encoding="utf-8") as f:
        for r in ok:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(ok)} plain summaries ({len(conditions) - len(ok)} skipped); usage: "
          f"{ {k: v for k, v in llm.usage_summary().items() if k.startswith(PROMPT)} }")


if __name__ == "__main__":
    main(sys.argv[1:])
