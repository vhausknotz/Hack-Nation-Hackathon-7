"""Operator's local bridge: pull signed cloud work, invoke the kernel, acknowledge.

This is intentionally tied to one persistent local checkout. It is not a cloud
ledger failover system. Cloud intake remains available while this worker is off.
"""
import hashlib
import json
import uuid
from pathlib import Path

from ledger import identity, sources
from ledger.canonical import canonical_json, content_id, sha256
from .intake import Intake
from .worker import drain


def pull_and_drain(cloud, state, ledger_path, registry_=None, limit=100):
    local = Intake(Path(state))
    from ledger.locking import WriterLease
    lease = WriterLease(local.root / "cloud-bridge.lock")
    try:
        return _drain_locked(cloud, local, ledger_path, registry_, limit)
    finally:
        lease.close()


def _drain_locked(cloud, local, ledger_path, registry_, limit):
    # Pin this cloud inbox to one local worker store. Do not automatically switch
    # to a fresh checkout containing an older ledger or missing receipt history.
    marker = local.root / "cloud-worker-id"
    if not marker.exists():
        marker.write_text(uuid.uuid4().hex)
    worker_id = marker.read_text()
    def bind(seq):
        owner = cloud.store.get("worker", "owner")
        if owner and owner["id"] != worker_id:
            raise ValueError("Cloud inbox is bound to another local worker; explicit recovery is required")
        return None, [] if owner else [("worker", "owner", {"id": worker_id})]
    cloud.store.atomic(bind)
    # Same-checkout bridge invocations are excluded separately from the ledger
    # lease, which the existing drain acquires for all actual signed log writes.
    selected = cloud.pending(limit)
    payloads = {}
    for row in selected:
        raw = cloud.store.container.download_blob(row["blob"]).readall()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Cloud payload hash differs")
        signed = json.loads(raw)
        envelope, signature = signed["envelope"], signed["signature"]
        payloads[row["id"]] = (row["kind"], envelope["payload"])
        actor, sid = row["actor"], row["id"]
        profile = cloud.profile(actor)
        if envelope["actor"] != actor or envelope["id"] != sid or envelope["task_id"] != row["task_id"] or envelope["kind"] != row["kind"]:
            raise ValueError("Cloud outbox/envelope mismatch")
        expected = content_id("submission", {"actor": actor, "task": row["task_id"], "kind": row["kind"], "payload": envelope["payload"]})
        if sid != expected or not identity.verify(profile["public_key"], canonical_json(envelope), signature):
            raise ValueError("Cloud submission signature differs")
        pem = cloud.store.container.download_blob(profile["key_path"]).readall()
        key_dir = local.root/"keys"
        key_dir.mkdir(exist_ok=True)
        key_path = key_dir/(actor.replace(":", "_")+".pem")
        if key_path.exists() and key_path.read_bytes() != pem:
            raise ValueError("Local contributor signing key differs")
        key_path.write_bytes(pem)
        if identity.load_or_create(actor, key_dir).public_key != profile["public_key"]:
            raise ValueError("Cloud key does not match enrollment")
        for evidence in envelope["payload"].get("evidence", []):
            src = cloud.store.get("source", evidence["source_id"])
            if not src:
                continue  # existing ledger sources are resolved by the kernel
            content = cloud.store.container.download_blob("sources/raw/"+src["raw_hash"].split(":")[1]).readall()
            text = cloud.store.container.download_blob("sources/text/"+src["text_hash"].split(":")[1]).readall()
            if sha256(content) != src["raw_hash"] or sha256(text) != src["text_hash"]:
                raise ValueError("Cloud source archive differs")
            copied = sources.archive(content, src["url"], src["media_type"], src["license"], src["redistributable"], root=local.root/"sources")
            if copied.source_id != src["source_id"]:
                raise ValueError("Cloud source canonicalization differs")
            with local.connect() as db:
                db.execute("INSERT OR IGNORE INTO sources VALUES (?,?)", (src["source_id"], json.dumps(src)))
        task = cloud.task(row["task_id"])
        with local.connect() as db:
            old = db.execute("SELECT body FROM profiles WHERE id=?", (actor,)).fetchone()
            earned = {"allow_review", "qualified_at", "calibration_score", "display",  # changed by qualification, not identity
                      "base_quota", "daily_quota", "reputation", "suspended", "suspended_reason", "suspended_at"}  # track record, moderation
            if old:
                previous = json.loads(old[0])
                if {k: v for k, v in previous.items() if k not in earned} != {k: v for k, v in profile.items() if k not in earned}:
                    raise ValueError("Cloud/local enrollment differs; operator reconciliation required")
                if previous != profile:
                    db.execute("UPDATE profiles SET body=? WHERE id=?", (json.dumps(profile), actor))
            db.execute("INSERT OR IGNORE INTO profiles VALUES (?,?)", (actor, json.dumps(profile)))
            db.execute("INSERT OR IGNORE INTO tasks(id,condition_id,kind,body) VALUES (?,?,?,?)", (task["id"], task["condition_id"], task["kind"], task["body"]))
            db.execute("INSERT OR IGNORE INTO submissions(id,actor,task_id,kind,payload,signature,created) VALUES (?,?,?,?,?,?,?)",
                       (sid, actor, row["task_id"], row["kind"], json.dumps(envelope["payload"]), signature, row["created"]))
    receipt = drain(local.root, Path(ledger_path), registry_, limit)
    for row in selected:
        result = local.submission(row["id"], row["actor"])
        if result["state"] != "queued":
            cloud.acknowledge(row["id"], result["result"], ack_detail(*payloads[row["id"]], result["result"]))
    return receipt


_LABELS = {}


def label(entity):
    """Readable name for a symptom ID in public feed details (HPO index built by atlas_mcp.terms)."""
    if not _LABELS:
        from .terms import INDEX
        _LABELS.update({k: v[0] for k, v in json.loads(INDEX.read_text(encoding="utf-8")).items()} if INDEX.exists() else {"": ""})
    return _LABELS.get(entity)


def ack_detail(kind, payload, result):
    """Public summary of a kernel decision: what was claimed and, if rejected, which checks failed."""
    detail = {"kind": kind}
    if kind == "claim":
        a = payload.get("assertion", {})
        q = a.get("qualifiers", {})
        detail.update(predicate=a.get("predicate"), object=str(a.get("object"))[:120],
                      label=label(a.get("object")) or q.get("name") or None, claim_id=result.get("claim_id"))
    if kind == "review":
        detail.update(verdict=payload.get("verdict"), claim_id=payload.get("claim_id"), reviewer="peer")
    failed = [{"check": c.get("name"), "detail": str(c.get("detail", ""))[:160]}
              for c in result.get("checks", []) if isinstance(c, dict) and not c.get("passed", True)]
    if failed:
        detail["failed_checks"] = failed[:6]
    if result.get("error"):
        detail["error"] = result["error"][:200]
    return detail
