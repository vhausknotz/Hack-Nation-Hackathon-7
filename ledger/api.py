"""The ledger's one door: every contribution, from our agents or from MCP contributors, goes through here.

    ledger = Ledger()
    agent = ledger.register(identity.load_or_create("agent:extractor"), kind="agent", manifest={...})
    result = ledger.propose(claim, agent)          # kernel-checked, logged, stored
    ledger.review(result.claim_id, "supports", "…", reviewer, model_family="openai-gpt6", model="gpt-6-sol")
    ledger.publish_tree_head()                     # signed Merkle root over the whole log
"""

import json
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import LEDGER_DIR, identity, merkle, policy, registry
from .canonical import canonical_json, content_id
from .kernel import KERNEL_VERSION, Kernel, passed
from .schema import REVIEW_VERDICTS, assertion_id, claim_id
from .sources import Source
from .store import Store
from .locking import WriterLease

REDACTION_CATEGORIES = {"personal_data", "secret", "illegal_content", "legal_obligation"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ProposalResult:
    claim_id: str
    assertion_id: str
    accepted: bool
    checks: list[dict] = field(default_factory=list)


class Ledger:
    def __init__(self, path: Path = LEDGER_DIR / "ledger.db", registry_=None, keys_dir: Path = identity.KEYS_DIR, source_root=None):
        lease = WriterLease(path.with_suffix(".writer.lock"))
        self.store = Store(path)
        self.store.on_close = lease.close
        weakref.finalize(self.store, lease.close)
        self.registry = registry_ or registry.default()
        self.kernel = Kernel(self.registry, self.store, source_root)
        self.keys_dir = keys_dir
        self.kernel_signer = self._system("kernel", "Mechanical checks: schema, identifiers, sources, quotes, datasets, signatures")
        self.log_signer = self._system("log", "Signs Merkle tree heads over the event log")

    def _system(self, kind: str, purpose: str) -> identity.Signer:
        signer = identity.load_or_create(f"system:{kind}", self.keys_dir)
        existing = self.store.contributor(signer.contributor)
        if existing is not None and existing["public_key"] != signer.public_key:
            raise ValueError("System signing key does not match the ledger; restore the original keys")
        if self.store.contributor(signer.contributor) is None:
            self.register(signer, kind=kind, manifest={"purpose": purpose, "version": KERNEL_VERSION if kind == "kernel" else "log@1"})
        return signer

    # ---- events -------------------------------------------------------------------------------------------
    def _append(self, signer: identity.Signer, type_: str, target: str | None, payload: dict) -> tuple[str, int]:
        unsigned = {"type": type_, "target": target, "actor": signer.contributor, "ts": now(), "payload": payload}
        event_id = content_id("event", unsigned)
        signature = signer.sign(event_id.encode())
        event = {**unsigned, "id": event_id, "signature": signature}
        seq = self.store.append_event(event, merkle.leaf_hash(canonical_json(event)))
        return event_id, seq

    # ---- contributors ---------------------------------------------------------------------------------------
    def register(self, signer: identity.Signer, kind: str, manifest: dict) -> identity.Signer:
        """Register a contributor (agent, human, importer). The manifest says what it is and can access."""
        if self.store.contributor(signer.contributor) is None:
            self.store.add_contributor(signer.contributor, signer.public_key, kind, manifest, now())
            self._append(signer, "contributor.registered", signer.contributor, {"public_key": signer.public_key, "kind": kind, "manifest": manifest})
            self.store.commit()
        return signer

    # ---- sources --------------------------------------------------------------------------------------------
    def add_source(self, source: Source, signer: identity.Signer) -> str:
        if self.store.source(source.source_id) is None:
            self.store.add_source(source.source_id, source.to_dict())
            self._append(signer, "source.archived", source.source_id, source.to_dict())
            self.store.commit()
        return source.source_id

    # ---- contributed claims ----------------------------------------------------------------------------------
    def propose(self, claim: dict, signer: identity.Signer) -> ProposalResult:
        signature = signer.sign(canonical_json(claim))
        cid, aid = claim_id(claim), assertion_id(claim)
        existing = self.store.claim(cid)
        if existing is not None:
            return ProposalResult(cid, aid, bool(existing["kernel_ok"]), [])
        auth = self.kernel.check_signature(claim, signature) if self.kernel.check_schema(claim).passed else None
        if auth is None or not auth.passed:  # unauthenticated submissions are refused at the door, never logged
            return ProposalResult(cid, aid, False, [(auth.to_dict() if auth else self.kernel.check_schema(claim).to_dict())])
        checks = self.kernel.check_claim(claim, signature)
        ok = passed(checks)
        _, seq = self._append(signer, "claim.proposed", cid, {"claim": claim, "claim_signature": signature, "assertion_id": aid})
        self._append(self.kernel_signer, "kernel.checked", cid, {"kernel": KERNEL_VERSION, "registry": self.registry.version,
                                                                   "passed": ok, "checks": [c.to_dict() for c in checks]})
        a = claim["assertion"]
        self.store.add_claims([(cid, aid, a["subject"], a["predicate"], str(a["object"]), canonical_json(claim).decode(),
                                signer.contributor, "contributed", None, int(ok), seq)])
        self.store.commit()
        return ProposalResult(cid, aid, ok, [c.to_dict() for c in checks])

    def review(self, claim_id_: str, verdict: str, reason: str, signer: identity.Signer, model_family: str | None = None, model: str | None = None,
               prompt: str | None = None, submission_id: str | None = None) -> str:
        if verdict not in REVIEW_VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(REVIEW_VERDICTS)}")
        claim = self.store.claim(claim_id_)
        if claim is None or not claim["kernel_ok"]:
            raise ValueError("only kernel-accepted claims can be reviewed")
        if claim["contributor"] == signer.contributor:
            raise ValueError("contributors cannot review their own claims")
        contributor = self.store.contributor(signer.contributor)
        kind = "human" if contributor and contributor["kind"] == "human" else "model"
        if kind == "model" and not model_family:
            raise ValueError("model reviews must declare their model family")
        event_id, seq = self._append(signer, "review.attested", claim_id_, {"verdict": verdict, "reason": reason, "model_family": model_family, "model": model,
                                                                          **({"prompt": prompt} if prompt else {}),
                                                                          **({"submission_id": submission_id} if submission_id else {})})
        self.store.add_review((event_id, claim_id_, signer.contributor, kind, model_family, model, verdict, reason, seq))
        self.store.commit()
        return event_id

    def challenge(self, target: str, reason: str, signer: identity.Signer, counter_claim: str | None = None, submission_id: str | None = None) -> str:
        """Challenge a claim (misreads its source) or an assertion (counter-evidence, cited as a counter-claim)."""
        if counter_claim and self.store.claim(counter_claim) is None:
            raise ValueError("counter-claim must be proposed first")
        event_id, seq = self._append(signer, "claim.challenged", target, {"reason": reason, "counter_claim": counter_claim,
                                                                      **({"submission_id": submission_id} if submission_id else {})})
        self.store.add_challenge((event_id, target, counter_claim, signer.contributor, reason, seq))
        self.store.commit()
        return event_id

    # ---- reference imports ------------------------------------------------------------------------------------
    def record_import(self, dataset: str, importer: str, claims: list[dict], signer: identity.Signer) -> dict:
        """Bulk import from a pinned reference dataset: one log event commits to every claim via a Merkle root."""
        accepted, rejected = [], []
        for claim in claims:
            checks = self.kernel.check_claim(claim, verify_signature=False)
            (accepted if passed(checks) else rejected).append((claim, checks))
        ids = sorted({claim_id(c) for c, _ in accepted})
        root = merkle.root([merkle.leaf_hash(i.encode()) for i in ids]).hex()
        reasons: dict[str, int] = {}
        for _, checks in rejected:
            for c in checks:
                if not c.passed:
                    key = f"{c.name}: {c.detail.split(':')[0]}"
                    reasons[key] = reasons.get(key, 0) + 1
        payload = {"dataset": dataset, "dataset_hash": self.registry.dataset_hash(dataset), "importer": importer,
                   "kernel": KERNEL_VERSION, "registry": self.registry.version, "claims": len(ids), "claims_root": root,
                   "rejected": len(rejected), "rejection_reasons": dict(sorted(reasons.items(), key=lambda x: -x[1])[:10])}
        import_id, seq = self._append(signer, "import.recorded", dataset, payload)
        rows, seen = [], set()
        for claim, _ in accepted:
            cid = claim_id(claim)
            if cid in seen:
                continue
            seen.add(cid)
            a = claim["assertion"]
            rows.append((cid, assertion_id(claim), a["subject"], a["predicate"], str(a["object"]), canonical_json(claim).decode(),
                         signer.contributor, "reference", import_id, 1, seq))
        self.store.add_claims(rows)
        self.store.commit()
        return {"import_id": import_id, **payload}

    # ---- redaction ---------------------------------------------------------------------------------------------
    def redact(self, event_id: str, category: str, signer: identity.Signer) -> str:
        """Remove an event's content (keeping its leaf hash, so the log still verifies). Never used to hide disagreement."""
        if category not in REDACTION_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(REDACTION_CATEGORIES)}")
        if self.store.event(event_id) is None:
            raise ValueError("unknown event")
        tombstone, _ = self._append(signer, "content.redacted", event_id, {"category": category})
        self.store.redact(event_id)
        self.store.db.execute("DELETE FROM claims WHERE claim_id = (SELECT target FROM events WHERE id = ? AND type = 'claim.proposed')", (event_id,))
        # These projections duplicate event reasons. Removing only the event
        # payload would otherwise leak the redacted content through exports.
        self.store.db.execute("DELETE FROM reviews WHERE event_id = ?", (event_id,))
        self.store.db.execute("DELETE FROM challenges WHERE event_id = ?", (event_id,))
        self.store.commit()
        return tombstone

    # ---- log integrity -------------------------------------------------------------------------------------------
    def publish_tree_head(self) -> dict:
        leaves = self.store.leaf_hashes()
        head = {"size": len(leaves), "root": merkle.root(leaves).hex(), "ts": now()}
        signature = self.log_signer.sign(canonical_json(head))
        self.store.add_tree_head(head["size"], head["root"], head["ts"], signature)
        self.store.commit()
        return {**head, "signature": signature, "log_key": self.log_signer.public_key}

    def inclusion_proof(self, event_id: str, size: int | None = None) -> dict:
        row = self.store.event(event_id)
        leaves = self.store.leaf_hashes(size)
        index = row["seq"] - 1
        return {"index": index, "size": len(leaves), "leaf": bytes(row["leaf_hash"]).hex(),
                "proof": [p.hex() for p in merkle.inclusion_proof(index, leaves)], "root": merkle.root(leaves).hex()}

    def consistency_proof(self, old_size: int) -> dict:
        leaves = self.store.leaf_hashes()
        return {"old_size": old_size, "new_size": len(leaves), "proof": [p.hex() for p in merkle.consistency_proof(old_size, leaves)],
                "old_root": merkle.root(leaves[:old_size]).hex(), "new_root": merkle.root(leaves).hex()}

    def verify_log(self) -> dict:
        """Recompute every non-redacted leaf from its stored event and check every signature."""
        problems = []
        for row in self.store.db.execute("SELECT * FROM events ORDER BY seq"):
            if row["redacted"]:
                continue
            event = {"type": row["type"], "target": row["target"], "actor": row["actor"], "ts": row["ts"], "payload": json.loads(row["payload"])}
            if content_id("event", event) != row["id"]:
                problems.append(f"seq {row['seq']}: content does not match its id")
                continue
            signed = {**event, "id": row["id"], "signature": row["signature"]}
            if merkle.leaf_hash(canonical_json(signed)) != bytes(row["leaf_hash"]):
                problems.append(f"seq {row['seq']}: leaf hash mismatch")
            actor = self.store.contributor(row["actor"])
            if actor is None or not identity.verify(actor["public_key"], row["id"].encode(), row["signature"]):
                problems.append(f"seq {row['seq']}: bad signature")
        return {"events": self.store.size(), "problems": problems, "ok": not problems}

    # ---- reading ---------------------------------------------------------------------------------------------------
    def claim_status(self, claim_id_: str) -> str:
        return policy.claim_review_status([dict(r) for r in self.store.reviews_for(claim_id_)])

    def assertion_state(self, assertion_id_: str) -> dict:
        rows = self.store.claims_where("assertion_id = ? AND kernel_ok = 1", (assertion_id_,))
        claims = [(json.loads(r["body"]), r["origin"], self.claim_status(r["claim_id"])) for r in rows]
        contested = any(
            ch["counter_claim"] and self.claim_status(ch["counter_claim"]) in ("independently_reviewed", "human_reviewed")
            for target in [assertion_id_] + [r["claim_id"] for r in rows]
            for ch in self.store.challenges_for(target)
        )
        return policy.evidence_state(claims, contested)

    def history(self, target: str) -> list[dict]:
        return [{"seq": r["seq"], "type": r["type"], "actor": r["actor"], "ts": r["ts"], "redacted": bool(r["redacted"]),
                 "payload": json.loads(r["payload"]) if r["payload"] else None} for r in self.store.events_for(target)]
