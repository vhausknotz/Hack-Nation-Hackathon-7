"""Re-review the misattributed quote and propose an archived, decision-carrying replacement.

Explicit operator job, two cached Sol judgments, no discovery searches. Never
changes a reviewer verdict by hand or overwrites an old claim.
"""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents import communities as c
from ledger import identity, sources
from ledger.api import Ledger, now

OLD = "claim:sha256:cf79bfc3dac323f6cc17e49a12a00076dc9c4f5ba06ae9181b08d851de8623c9"


def main():
    ledger = Ledger()
    try:
        scout = identity.load_or_create("agent:community-scout")
        reviewer = identity.load_or_create("agent:community-verifier-sol")
        old = json.loads(ledger.store.claim(OLD)["body"])
        a = old["assertion"]
        condition = c.load_conditions()[a["subject"]]
        org = {**a["qualifiers"]}
        src = ledger.store.source(old["evidence"][0]["source_id"])
        text = sources.read_text(src)
        profile = c.organization_profile(a["object"], ledger)
        start = text.index("Simons Searchlight is an online international research program")
        ending = "Simons Searchlight STXBP1 Facebook community"
        end = text.index(ending, start)+len(ending)
        quote = text[start:end]
        if len(quote) > 2000 or "STXBP1" not in quote:
            raise ValueError("Replacement quote fails the bounded condition-support check")
        receipt = {"campaign": "simons-stxbp1-quote-correction", "old_claim": OLD, "started": now(), "reviews": []}
        for old_or_new in ("old", "new"):
            claim = deepcopy(old)
            if old_or_new == "new":
                # Explicitly proposed from the program's own description; Sol
                # still decides whether this kind and scope are supported.
                claim["assertion"]["qualifiers"].update(org_type="research_program", scope="broader_group")
                claim["evidence"] = [{**old["evidence"][0], "quote": quote, "start": start, "end": end}, profile]
                claim["provenance"].update(created=now(), prompt="archived-community-quote-correction@1", campaign=receipt["campaign"],
                                           discovery="archived source inspection", supersedes_evidence_for=OLD)
                claim = c.reuse_claim(ledger, claim)
                proposed = ledger.propose(claim, scout)
                if not proposed.accepted:
                    raise ValueError("Corrected claim failed the kernel")
                cid = proposed.claim_id
            else:
                cid = OLD
            verdict = c.verify_community(condition, claim["assertion"]["qualifiers"], src["title"], claim["evidence"][0]["quote"], text, profile)
            prompt = c.PROFILE_VERIFY_PROMPT
            prior = ledger.store.db.execute("SELECT 1 FROM events WHERE type='review.attested' AND target=? AND json_extract(payload,'$.prompt')=?", (cid, prompt)).fetchone()
            if not prior:
                ledger.review(cid, verdict["verdict"], verdict["reason"], reviewer, model_family=c.MODEL_FAMILY, model=c.VERIFY_MODEL, prompt=prompt)
            receipt["reviews"].append({"which": old_or_new, "claim_id": cid, **verdict, "status": ledger.claim_status(cid)})
        receipt["ledger_tree_head"] = ledger.publish_tree_head()
        receipt["log_verified"] = ledger.verify_log()["ok"]
        c.save_receipt(ROOT/"data/campaigns/simons-stxbp1-quote-correction.json", receipt)
        print(json.dumps(receipt, indent=2))
    finally:
        ledger.store.close()


if __name__ == "__main__":
    main()
