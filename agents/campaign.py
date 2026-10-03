"""Run a campaign: point the agents at conditions, write everything through the ledger, publish a receipt.

    python -m agents.campaign first-campaign MONDO:0014590 [MONDO:… …] [--max-papers 40]

Per condition: scout papers → archive abstracts → screen (Luna) → extract symptoms with quotes (Luna)
→ resolve to HPO terms (exact / embeddings + Sol) → propose claims (kernel checks quotes, IDs, signature)
→ verify each accepted claim (Sol) → review events. The receipt (data/campaigns/<name>.json) says what
was screened, proposed, accepted, rejected and what it cost.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

from . import ROOT
import llm  # noqa: E402
from ledger import identity  # noqa: E402
from ledger.api import Ledger, now  # noqa: E402
from ledger.schema import make_claim  # noqa: E402

from .literature import EXTRACT_MODEL, EXTRACT_PROMPT, archive_abstracts, extract_symptoms, frequency_text, scout, screen  # noqa: E402
from .resolve import HpoResolver  # noqa: E402
from .verify import MODEL_FAMILY, VERIFY_MODEL, verify_symptom  # noqa: E402

CAMPAIGNS = ROOT / "data" / "campaigns"


def load_conditions(ids: set[str]) -> dict[str, dict]:
    out = {}
    with open(ROOT / "data" / "build" / "conditions.jsonl", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c["id"] in ids:
                out[c["id"]] = c
    return out


def curated_pmids(ledger: Ledger, disease: str) -> list[str]:
    pmids = []
    for row in ledger.store.claims_where("subject = ? OR object = ?", (disease, disease)):
        for ev in json.loads(row["body"])["evidence"]:
            pmids += [str(p) for p in ev.get("pmids", []) + ev.get("refs", [])]
    return list(dict.fromkeys(pmids))[:30]


def usage_totals() -> tuple[int, int, float]:
    s = llm.usage_summary()
    return sum(v["input_tokens"] for v in s.values()), sum(v["output_tokens"] for v in s.values()), sum(v["usd"] for v in s.values())


def main(args: list[str]) -> None:
    max_papers = int(args[args.index("--max-papers") + 1]) if "--max-papers" in args else 40
    positional = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--max-papers")]
    name, ids = positional[0], positional[1:]
    t0 = time.time()
    tokens0 = usage_totals()

    ledger = Ledger()
    manifests = {
        "agent:scout": {"role": "scout", "tools": ["PubMed E-utilities"], "version": "scout@1"},
        "agent:screener-luna": {"role": "screener", "model": "gpt-6-luna", "model_family": MODEL_FAMILY, "prompt": "screen-paper@1"},
        "agent:extractor-luna": {"role": "extractor", "model": EXTRACT_MODEL, "model_family": MODEL_FAMILY, "prompt": EXTRACT_PROMPT,
                                 "resolver": "exact HPO names + text-embedding-3-large + gpt-6-sol"},
        "agent:verifier-sol": {"role": "verifier", "model": VERIFY_MODEL, "model_family": MODEL_FAMILY, "prompt": "verify-symptom@1"},
    }
    agents = {cid: ledger.register(identity.load_or_create(cid), kind="agent", manifest=m) for cid, m in manifests.items()}
    resolver = HpoResolver()
    conditions = load_conditions(set(ids))
    receipt = {"campaign": name, "started": now(), "conditions": {}}

    for cid in ids:
        c = conditions.get(cid)
        if c is None:
            print(f"{cid}: not in data/build/conditions.jsonl, skipped")
            continue
        r = Counter()
        pmids = scout(c["gene"]["symbol"], curated_pmids(ledger, c["disease"]), max_search=max_papers)
        papers = archive_abstracts(pmids, ledger, agents["agent:scout"])
        r["papers_found"], r["abstracts_archived"] = len(pmids), len(papers)
        decisions = screen(c, papers)
        relevant = {p: d for p, d in papers.items() if decisions.get(p, {}).get("relevance") == "direct"}
        r["papers_relevant"] = len(relevant)
        print(f"{c['name']}: {len(pmids)} papers, {len(papers)} abstracts, {len(relevant)} report patients")

        proposed = []
        for pmid, paper in relevant.items():
            for feat in extract_symptoms(c, paper):
                r["features_extracted"] += 1
                if feat["span"] is None:
                    r["dropped_quote_not_found"] += 1
                    continue
                res = resolver.resolve(feat.get("feature", ""), feat.get("quote", ""))
                if res is None:
                    r["dropped_no_hpo_term"] += 1
                    continue
                start, end = feat["span"]
                evidence = [{"type": "publication_text", "source_id": paper["source"].source_id, "pmid": f"PMID:{pmid}",
                             "quote": paper["text"][start:end], "start": start, "end": end,
                             "frequency": frequency_text(feat.get("frequency", "")), "evidence_level": feat.get("evidence_level", "clinical"),
                             "feature_as_written": feat.get("feature", ""), "resolution": res["method"]}]
                certainty = feat.get("certainty", "asserted")
                claim = make_claim(c["disease"], "has_symptom", res["hpo_id"], evidence,
                                   {"contributor": "agent:extractor-luna", "agent": "extractor", "model": EXTRACT_MODEL, "prompt": EXTRACT_PROMPT,
                                    "campaign": name, "created": now()},
                                   **({"certainty": certainty} if certainty in ("suggested", "speculative") else {}))
                result = ledger.propose(claim, agents["agent:extractor-luna"])
                r["claims_proposed"] += 1
                if result.accepted:
                    r["claims_kernel_accepted"] += 1
                    proposed.append((result.claim_id, claim, paper))
                else:
                    r["claims_kernel_rejected"] += 1

        for claim_id, claim, paper in proposed:
            term = resolver.onto.terms[claim["assertion"]["object"]]
            v = verify_symptom(c, term, claim, paper["text"])
            ledger.review(claim_id, v["verdict"], v["reason"], agents["agent:verifier-sol"], model_family=MODEL_FAMILY, model=VERIFY_MODEL)
            r[f"review_{v['verdict']}"] += 1
        receipt["conditions"][cid] = {"name": c["name"], **r}
        print(f"  {dict(r)}")

    tokens1 = usage_totals()
    head = ledger.publish_tree_head()
    receipt.update({
        "finished": now(), "seconds": round(time.time() - t0),
        "model_tokens": {"input": tokens1[0] - tokens0[0], "output": tokens1[1] - tokens0[1]},
        "usd_known_prices": round(tokens1[2] - tokens0[2], 4),
        "ledger_tree_head": {"size": head["size"], "root": head["root"]},
        "log_verified": ledger.verify_log()["ok"],
    })
    CAMPAIGNS.mkdir(parents=True, exist_ok=True)
    (CAMPAIGNS / f"{name}.json").write_text(json.dumps(receipt, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "conditions"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
