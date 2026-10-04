"""Resumable operator cycle. Paid review is restricted by a pinned local plan.

An uncertain request retains its attempt reservation forever. Restarting cannot
silently retry it, enlarge the budget, or reset publication progress.
"""
import hashlib
import json
import os
from pathlib import Path

from ledger.locking import WriterLease


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def validate_plan(plan):
    if plan.get("version") != 1 or not isinstance(plan.get("max_review_attempts"), int):
        raise ValueError("Expected version 1 and an explicit review-attempt allowance")
    if not 0 <= plan["max_review_attempts"] <= 10:
        raise ValueError("Pilot supports 0..10 lifetime review attempts only")
    if not plan.get("allowed_contributors") or not plan.get("approved_assets"):
        raise ValueError("Explicit contributor and condition/record allowlists required")
    if not isinstance(plan.get("publish_website"), bool):
        raise ValueError("Explicit website publication choice required")


class Cycle:
    def __init__(self, root, plan):
        validate_plan(plan)
        self.root = Path(root)
        self.plan = plan
        self.lease = WriterLease(self.root / "cycle.lock")
        self.path = self.root / "receipt.json"
        digest = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {
            "plan_sha256": digest, "attempts": {}, "publication": {}, "cycles": 0}
        if self.state["plan_sha256"] != digest:
            self.lease.close()
            raise ValueError("Plan changed: do not reset a running campaign's budget or scope")

    def close(self):
        self.lease.close()

    def save(self):
        atomic_json(self.path, self.state)

    def run(self, backend):
        self.state["cycles"] += 1
        self.state.pop("error", None)
        self.state["stage"] = "draining"
        self.save()
        try:
            self.state["drain"] = backend.drain()
            if not self.state["drain"].get("log_verified"):
                raise ValueError("Ledger verification failed; stop before review or publication")
            self.state["stage"] = "reviewing"
            self.save()
            for candidate in backend.candidates(self.plan):
                cid = candidate["claim_id"]
                attempts = self.state["attempts"]
                attempt = attempts.get(cid)
                if attempt and attempt["state"] in {"reserved", "uncertain", "failed", "complete"}:
                    continue
                if not attempt:
                    if len(attempts) >= self.plan["max_review_attempts"]:
                        break
                    attempts[cid] = attempt = {"state": "reserved"}
                    self.save()  # reserve BEFORE any network call; crashes never free it
                    try:
                        judgment = backend.review(candidate)
                        if judgment.get("verdict") not in {"supports", "supports_with_qualification", "does_not_support", "out_of_scope"} or not judgment.get("reason"):
                            raise ValueError("Reviewer returned no usable judgment")
                        attempt.update(state="judged", judgment=judgment)
                        self.save()  # resume attestation without re-paying for review
                    except Exception as error:
                        attempt.update(state="uncertain", error_type=type(error).__name__)
                        self.save()
                        continue
                backend.attest(candidate, attempt["judgment"])
                attempt["state"] = "complete"
                self.save()
            self.state["stage"] = "publishing"
            self.save()
            # Backend holds the ledger writer lease for a consistent publication.
            backend.publish(self.state, self.save, self.plan)
            self.state["stage"] = "idle"
            self.save()
            return self.state
        except Exception as error:
            self.state["error"] = {"stage": self.state["stage"], "type": type(error).__name__}
            self.save()
            raise


def publish_stages(state, save, revision, stages):
    """Checkpoint each successful side effect; retries do not repeat earlier stages."""
    publication = state["publication"]
    if publication.get("revision") != revision:
        state["publication"] = publication = {"revision": revision, "completed": [], "results": {}}
        save()
    for name, operation in stages:
        if name in publication["completed"]:
            continue
        publication["running"] = name
        save()
        result = operation()
        publication["results"][name] = result
        publication["completed"].append(name)
        publication.pop("running", None)
        save()
