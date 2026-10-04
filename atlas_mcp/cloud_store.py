"""Azure intake primitives. Table transactions arbitrate leases, quotas and the outbox.

No SQLite, ledger access, model calls or website publication in this module. All
control rows share one partition so a conditional guard update makes multi-row
decisions atomic across scaled instances. Blob payloads are immutable; the Table
submission row is the durable outbox, avoiding a Table/Queue dual-write gap.
"""
import hashlib
import json
import re
import time
from copy import deepcopy

from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableTransactionError, UpdateMode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ledger.canonical import canonical_json, content_id
from ledger.identity import Signer


class CloudStore:
    PARTITION = "intake-v1"

    def __init__(self, table, container):
        self.table, self.container = table, container

    def initialize(self):
        """Operator-only provisioning; request paths never create Azure resources."""
        try:
            self.table.create_table()
        except ResourceExistsError:
            pass
        try:
            self.container.create_container()
        except ResourceExistsError:
            pass
        try:
            self.table.create_entity(self.entity("control", "guard", {"seq": 0}))
        except ResourceExistsError:
            pass

    @staticmethod
    def key(kind, identifier):
        return kind + "-" + hashlib.sha256(identifier.encode()).hexdigest()

    def entity(self, kind, identifier, body):
        return {"PartitionKey": self.PARTITION, "RowKey": self.key(kind, identifier),
                "kind": kind, "id": identifier, "body": json.dumps(body, ensure_ascii=True)}

    def get(self, kind, identifier):
        try:
            row = self.table.get_entity(self.PARTITION, self.key(kind, identifier))
        except ResourceNotFoundError:
            return None
        return json.loads(row["body"])

    def rows(self, kind):
        # kind is an internal constant, never user-controlled OData.
        if not re.fullmatch("[a-z]+", kind):
            raise ValueError("Invalid row kind")
        return [json.loads(row["body"]) for row in self.table.query_entities(
            "PartitionKey eq @partition and kind eq @kind", parameters={"partition": self.PARTITION, "kind": kind})]

    def immutable(self, name, data):
        blob = self.container.get_blob_client(name)
        try:
            blob.upload_blob(data, overwrite=False)
        except ResourceExistsError:
            if blob.download_blob().readall() != data:
                raise ValueError("Immutable blob content differs")
        return name

    def atomic(self, decide):
        """Retry read/decide on contention. decide must not perform external effects.

        Returns (result, rows to create/replace). Every mutator uses this guard;
        private storage permissions prevent callers bypassing it. Orphaned
        content-addressed blobs are harmless and can be cleaned independently.
        """
        for attempt in range(12):
            guard = self.table.get_entity(self.PARTITION, self.key("control", "guard"))
            seq = json.loads(guard["body"])["seq"] + 1
            result, changes = decide(seq)
            if not changes:
                return result
            operations = [("update", self.entity("control", "guard", {"seq": seq}),
                           {"mode": UpdateMode.REPLACE, "etag": guard.metadata["etag"],
                            "match_condition": MatchConditions.IfNotModified})]
            for kind, identifier, body in changes:
                operations.append(("upsert", self.entity(kind, identifier, body), {"mode": UpdateMode.REPLACE}))
            try:
                self.table.submit_transaction(operations)
                return result
            except TableTransactionError as exc:
                if exc.status_code not in (409, 412):
                    raise
                time.sleep(min(.1, .005 * (attempt+1)))
        raise ValueError("Intake is busy; retry the same operation safely")


class CloudIntake:
    def __init__(self, store):
        self.store = store

    def enroll(self, name, model, family, principal, allow_review=False, quota=100):
        """Operator-only. Principal must be verified issuer + subject, not display name."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", name):
            raise ValueError("Use a lowercase contributor slug")
        if not model.strip() or not family.strip() or not 1 <= quota <= 1000 or not principal:
            raise ValueError("Model, family, verified principal and quota are required")
        actor = "agent:mcp-" + name
        key = Ed25519PrivateKey.generate()
        signer = Signer(actor, key)
        key_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        # Content-addressing permits safe retry, with no key overwrite on collision.
        key_path = "private/keys/" + hashlib.sha256(key_bytes).hexdigest() + ".pem"
        self.store.immutable(key_path, key_bytes)
        profile = {"id": actor, "public_key": signer.public_key, "kind": "agent", "model": model,
                   "model_family": family, "allow_review": bool(allow_review), "daily_quota": quota,
                   "key_path": key_path, "principal": principal,
                   "manifest": {"role": "mcp-contributor", "model": model, "model_family": family,
                                "transport": "authenticated-http", "version": "atlas-mcp@1"}}
        def decide(seq):
            if self.store.get("profile", actor) or self.store.get("principal", principal):
                raise ValueError("Contributor or principal is already enrolled")
            return profile, [("profile", actor, profile), ("principal", principal, {"actor": actor})]
        return self.store.atomic(decide)

    def principal_actor(self, principal):
        row = self.store.get("principal", principal)
        if not row:
            raise ValueError("Authenticated principal is not enrolled")
        self.profile(row["actor"])
        return row["actor"]

    def profile(self, actor):
        profile = self.store.get("profile", actor)
        if not profile or profile.get("disabled"):
            raise ValueError("Contributor is unknown or disabled")
        return profile

    def signer(self, actor):
        profile = self.profile(actor)
        raw = self.store.container.download_blob(profile["key_path"]).readall()
        signer = Signer(actor, serialization.load_pem_private_key(raw, password=None))
        if signer.public_key != profile["public_key"]:
            raise ValueError("Enrolled signing key mismatch")
        return signer

    @staticmethod
    def event(seq, actor, task, stage, submission=None):
        return ("activity", str(seq), {"seq": seq, "at": time.time(), "actor": actor,
                "task_id": task["id"], "condition_id": task["condition_id"], "stage": stage, "submission_id": submission})

    def seed(self, tasks):
        for task in tasks:
            def decide(seq, task=task):
                if self.store.get("task", task["id"]):
                    return None, []
                return None, [("task", task["id"], {**task, "actor": None, "expires": 0, "state": "open"})]
            self.store.atomic(decide)

    def task(self, tid):
        row = self.store.get("task", tid)
        return {**row, "body": json.dumps(row)} if row else None

    def tasks(self, condition_id=None, limit=20):
        rows = [r for r in self.store.rows("task") if r["state"] != "complete" and (not condition_id or r["condition_id"] == condition_id)]
        rows.sort(key=lambda r: (r["kind"] != "review", r["id"]))
        return [{**r, "claimed_by": r["actor"] if r["expires"] > time.time() else None,
                 "lease_expires": r["expires"]} for r in rows[:limit]]

    def claim(self, tid, actor):
        def decide(seq):
            self.profile(actor)
            task = self.store.get("task", tid)
            now = time.time()
            if not task or task["state"] == "complete":
                raise ValueError("No open task with this ID")
            if task["actor"] and task["actor"] != actor and task["expires"] > now:
                raise ValueError("Task is leased to another contributor")
            quota = self.store.get("quota", actor) or {"leases": {}, "submissions": []}
            leases = {k: v for k, v in quota["leases"].items() if v > now}
            if tid not in leases and len(leases) >= 3:
                raise ValueError("At most three active tasks per contributor")
            leases[tid] = now + 1800
            quota["leases"] = leases
            task.update(actor=actor, expires=leases[tid])
            return {**task, "lease_expires": task["expires"]}, [("task", tid, task), ("quota", actor, quota), self.event(seq, actor, task, "task_claimed")]
        return self.store.atomic(decide)

    def owned_task(self, tid, actor):
        task = self.task(tid)
        if not task or task["actor"] != actor or task["expires"] <= time.time() or task["state"] == "complete":
            raise ValueError("An active task lease is required")
        return task

    def enqueue(self, actor, tid, kind, payload):
        if kind not in {"claim", "review", "challenge"} or len(canonical_json(payload)) > 32000:
            raise ValueError("Unsupported submission or payload exceeds 32 KB")
        sid = content_id("submission", {"actor": actor, "task": tid, "kind": kind, "payload": payload})
        existing = self.store.get("submission", sid)
        if existing:
            self.profile(actor)
            return {"submission_id": sid, "state": existing["state"], "duplicate": True}
        profile = self.profile(actor)
        self.owned_task(tid, actor)
        quota = self.store.get("quota", actor) or {"submissions": []}
        if sum(t > time.time()-86400 for t in quota["submissions"]) >= profile["daily_quota"]:
            raise ValueError("Daily submission quota reached")
        envelope = {"id": sid, "actor": actor, "task_id": tid, "kind": kind, "payload": payload}
        signed = {"envelope": envelope, "signature": self.signer(actor).sign(canonical_json(envelope))}
        blob = "submissions/" + self.store.key("payload", sid) + ".json"
        encoded = canonical_json(signed)
        # Blob becomes discoverable only after the atomic quota/outbox commit.
        self.store.immutable(blob, encoded)
        def decide(seq):
            profile = self.profile(actor)
            existing = self.store.get("submission", sid)
            if existing:
                return {"submission_id": sid, "state": existing["state"], "duplicate": True}, []
            task = self.owned_task(tid, actor)
            quota = self.store.get("quota", actor) or {"leases": {}, "submissions": []}
            now = time.time()
            recent = [t for t in quota["submissions"] if t > now-86400]
            if len(recent) >= profile["daily_quota"]:
                raise ValueError("Daily submission quota reached")
            quota["submissions"] = recent + [now]
            record = {"id": sid, "actor": actor, "task_id": tid, "kind": kind, "blob": blob,
                      "sha256": hashlib.sha256(encoded).hexdigest(), "created": now, "state": "queued", "result": None}
            return {"submission_id": sid, "state": "queued", "notice": "Queued for the ledger worker; not reviewed or published. No model calls were made."}, [
                ("submission", sid, record), ("quota", actor, quota), self.event(seq, actor, task, "queued", sid)]
        return self.store.atomic(decide)

    def submission(self, sid, actor):
        self.profile(actor)
        row = self.store.get("submission", sid)
        if not row or row["actor"] != actor:
            raise ValueError("No submission for this contributor")
        return {"submission_id": sid, **{k: row[k] for k in ("kind", "state", "created", "result")}}

    def pending(self, limit=100):
        return sorted((r for r in self.store.rows("submission") if r["state"] == "queued"), key=lambda r: (r["created"], r["id"]))[:limit]

    def acknowledge(self, sid, result):
        """Operator worker only, after a durable signed ledger receipt."""
        def decide(seq):
            row = self.store.get("submission", sid)
            if not row:
                raise ValueError("Unknown submission")
            if row["state"] != "queued":
                if row["result"] != result:
                    raise ValueError("Acknowledgement conflicts with durable result")
                return None, []
            row.update(state=result["state"], result=deepcopy(result))
            task = self.store.get("task", row["task_id"])
            changes = [("submission", sid, row), self.event(seq, row["actor"], task, row["state"], sid)]
            if row["kind"] == "review" and result["state"] == "review_recorded":
                task.update(state="complete", expires=0)
                quota = self.store.get("quota", row["actor"])
                quota["leases"].pop(task["id"], None)
                changes.extend([("task", task["id"], task), ("quota", row["actor"], quota)])
            return None, changes
        return self.store.atomic(decide)

    def activity(self, after=0, limit=50):
        return sorted((r for r in self.store.rows("activity") if r["seq"] > after), key=lambda r: r["seq"])[:limit]

    def reserve_fetch(self, actor, tid):
        """Provider slots and daily quotas survive failure/restart; no free retry loop."""
        def decide(seq):
            self.profile(actor)
            task = self.owned_task(tid, actor)
            now = time.time()
            quota = self.store.get("fetchquota", actor) or {"requests": []}
            recent = [t for t in quota["requests"] if t > now-86400]
            if len(recent) >= 100:
                raise ValueError("Daily source-fetch limit reached")
            throttle = self.store.get("fetchclock", "official") or {"next": 0}
            delay = max(0, throttle["next"]-now)
            if delay > 5:
                raise ValueError("Source fetcher is busy; retry later")
            throttle["next"] = now+delay+1.25
            quota["requests"] = recent+[now]
            return delay, [("fetchquota", actor, quota), ("fetchclock", "official", throttle),
                           self.event(seq, actor, task, "source_fetch_started")]
        return self.store.atomic(decide)

    def record_source(self, src, raw, text, actor, tid, provider_key):
        from ledger.canonical import sha256
        if sha256(raw) != src["raw_hash"] or sha256(text.encode()) != src["text_hash"]:
            raise ValueError("Source content hashes differ")
        self.store.immutable("sources/raw/"+src["raw_hash"].split(":")[1], raw)
        self.store.immutable("sources/text/"+src["text_hash"].split(":")[1], text.encode())
        def decide(seq):
            task = self.owned_task(tid, actor)
            existing = self.store.get("source", src["source_id"])
            return None, [("source", src["source_id"], existing or src),
                          ("sourcecache", provider_key, {"source_id": src["source_id"]}),
                          self.event(seq, actor, task, "source_fetched")]
        self.store.atomic(decide)
