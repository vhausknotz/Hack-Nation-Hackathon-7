"""Run one bounded cloud-intake -> Sol review -> tested publication cycle.

The local plan fixes the only contributors and condition/study pairs allowed to
spend on review. Reservations persist across restarts; there are no paid retries.
No public MCP caller can invoke this operator command or enlarge its allowance.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from atlas_mcp.cycle import Cycle, publish_stages
from ledger import identity, sources
from ledger.api import Ledger
from ledger.canonical import sha256
from ledger.locking import WriterLease
from ledger.store import Store
from tools.azure_mcp_operator import Operator

REVIEWER = "agent:asset-verifier-sol"
MODEL = "gpt-6-sol"
PROMPT = "verify-asset-bounded@1"
MAX_INPUT_BYTES = 40_000
MAX_OUTPUT_TOKENS = 4_000


def approved(row, claim, plan, conditions):
    assertion = claim["assertion"]
    pairs = {(a["condition_id"], a["record_id"]) for a in plan["approved_assets"]}
    return (row["contributor"] in plan["allowed_contributors"] and row["contributor"] != REVIEWER
            and bool(claim.get("provenance", {}).get("intake_submission"))
            and assertion["predicate"] == "has_asset" and assertion["subject"] in conditions
            and (assertion["subject"], assertion["object"]) in pairs)


class Backend:
    def __init__(self, state):
        self.state = state
        self.operator = Operator()
        self.cloud = self.operator.store()
        self.ledger_path = ROOT / "data/ledger/ledger.db"
        self.conditions = {c["id"]: c for c in map(json.loads, (ROOT / "data/build/conditions.jsonl").read_text(encoding="utf-8").splitlines())}

    def drain(self):
        from atlas_mcp.cloud_store import CloudIntake
        from atlas_mcp.cloud_worker import pull_and_drain
        return pull_and_drain(CloudIntake(self.cloud), ROOT / "data/contributions/cloud-bridge", self.ledger_path, limit=25)

    def candidates(self, plan):
        store = Store(self.ledger_path, readonly=True)
        result = []
        try:
            for row in store.claims_where("kernel_ok=1 AND origin='contributed' AND predicate='has_asset'"):
                if store.reviews_for(row["claim_id"]):
                    continue  # don't overwrite prior review, rejection or disagreement
                if store.challenges_for(row["claim_id"]) or store.challenges_for(row["assertion_id"]):
                    continue  # contested work needs an explicit dispute workflow
                claim = json.loads(row["body"])
                if not approved(row, claim, plan, self.conditions):
                    continue
                sid = {e.get("source_id") for e in claim["evidence"]}
                if len(sid) != 1:
                    continue  # this pilot reviews one complete official study record
                source = store.source(sid.pop())
                if not source or source["url"] != f'https://clinicaltrials.gov/study/{claim["assertion"]["object"]}':
                    continue
                text = sources.read_text(source)
                if text is None or sha256(text.encode()) != source["text_hash"]:
                    raise ValueError("Archived review source changed or is missing")
                if len(text.encode()) > 32_000:
                    continue  # never truncate away eligibility to fit a paid review
                result.append({"claim_id": row["claim_id"], "claim": claim, "text": text,
                               "condition": self.conditions[claim["assertion"]["subject"]]})
        finally:
            store.close()
        return sorted(result, key=lambda c: c["claim_id"])

    def review(self, candidate):
        from agents.trials_import import verify_asset
        import llm
        def bounded_chat(model, messages, task):
            if model != MODEL or len(json.dumps(messages, ensure_ascii=False).encode()) > MAX_INPUT_BYTES:
                raise ValueError("Review request exceeds the pinned model/input allowance")
            # Disable SDK retries: an ambiguous timeout keeps its reservation.
            return llm.chat_json(model, messages, task=PROMPT, max_completion_tokens=MAX_OUTPUT_TOKENS,
                                 request_client=llm.client().with_options(max_retries=0, timeout=90))
        return verify_asset(candidate["condition"], candidate["claim"], candidate["text"], chat_json=bounded_chat)

    def attest(self, candidate, judgment):
        ledger = Ledger()
        try:
            if ledger.store.reviews_for(candidate["claim_id"]):
                return  # crash after attestation: don't append a second review
            signer = ledger.register(identity.load_or_create(REVIEWER), kind="agent", manifest={
                "role": "verifier", "model": MODEL, "model_family": "openai", "prompt": PROMPT})
            ledger.review(candidate["claim_id"], judgment["verdict"], judgment["reason"], signer,
                          model_family="openai", model=MODEL, prompt=PROMPT)
            if not ledger.verify_log()["ok"]:
                raise ValueError("Ledger integrity failed; do not publish")
            ledger.publish_tree_head()
        finally:
            ledger.store.close()

    def command(self, args):
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=360)
        if result.returncode:
            raise RuntimeError(f"Publication check failed: {Path(args[0]).name}; exit={result.returncode}")
        return {"ok": True}

    def publish(self, state, save, plan):
        from atlas_mcp.cloud_publish import publish
        from tools.deploy_website import deploy
        # Freeze ledger writers through export, tests and both publication steps.
        lease = WriterLease(self.ledger_path.with_suffix(".writer.lock"))
        try:
            store = Store(self.ledger_path, readonly=True)
            try:
                head = store.db.execute("SELECT size,root FROM tree_heads ORDER BY size DESC LIMIT 1").fetchone()
                if not head or head["size"] != store.size():
                    raise ValueError("The latest ledger state has no signed tree head")
                if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
                    raise ValueError("Commit and review repository changes before automatic publication")
                code = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
                revision = f'{head["size"]}:{head["root"]}:{code}'
            finally:
                store.close()
            py = sys.executable
            npm = "npm.cmd" if os.name == "nt" else "npm"
            stages = []
            if plan["publish_website"]:
                stages += [
                    ("export", lambda: self.command([py, "pipeline/export_app.py"])),
                    ("build", lambda: self.command([npm, "--prefix", "app", "run", "build"])),
                    ("browser_checks", lambda: self.command([py, "tools/check_family_brief.py", "http://localhost:4173", str(self.state / "qa")])),
                ]
            stages.append(("cloud_snapshot", lambda: publish(self.cloud, self.ledger_path, ROOT / "data/build")))
            if plan["publish_website"]:
                stages += [("website", deploy), ("live_check", lambda: self.command([py, "tools/check_shared_research_live.py"]))]
            publish_stages(state, save, revision, stages)
        finally:
            lease.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    cycle = Cycle(args.state, plan)
    try:
        result = cycle.run(Backend(args.state))
        print(json.dumps({"stage": result["stage"], "attempts_reserved": len(result["attempts"]),
                          "attempt_limit": plan["max_review_attempts"], "publication": result["publication"]}, indent=2))
    finally:
        cycle.close()


if __name__ == "__main__":
    main()
