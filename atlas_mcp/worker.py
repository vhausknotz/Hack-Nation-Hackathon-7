"""Explicit single-writer drain. No model calls, graph publication or automatic reviews."""
import json
from datetime import datetime, timezone
from pathlib import Path

from ledger import identity, sources
from ledger.api import Ledger
from ledger.canonical import canonical_json, content_id, sha256
from .intake import Intake


def drain(state, ledger_path, registry_=None, limit=100):
    intake = Intake(Path(state))
    ledger_path = Path(ledger_path)
    archive = ledger_path.parent / "sources"
    ledger = Ledger(ledger_path, registry_=registry_, keys_dir=ledger_path.parent / "keys", source_root=archive)
    results = []
    try:
        with intake.connect() as db:
            pending = [dict(r) for r in db.execute("SELECT * FROM submissions WHERE state='queued' ORDER BY created,id LIMIT ?", (limit,))]
        for row in pending:
            payload = json.loads(row["payload"])
            actor, kind = row["actor"], row["kind"]
            try:
                profile = intake.profile(actor)
                envelope = {"id": row["id"], "actor": actor, "task_id": row["task_id"], "kind": kind, "payload": payload}
                expected = content_id("submission", {"actor": actor, "task": row["task_id"], "kind": kind, "payload": payload})
                if expected != row["id"] or not identity.verify(profile["public_key"], canonical_json(envelope), row["signature"]):
                    raise ValueError("Submission content or signature was changed")
                signer = intake.signer(actor)
                existing = ledger.store.contributor(actor)
                kind_ = "human" if profile.get("kind") == "human" else "agent"  # operator-vetted experts review as people
                if existing and (existing["public_key"] != profile["public_key"] or existing["kind"] != kind_):
                    raise ValueError("Ledger identity conflicts with operator enrollment")
                ledger.register(signer, kind=kind_, manifest=profile["manifest"])
                already = ledger.store.db.execute("SELECT payload FROM events WHERE actor=? AND type='intake.processed' AND json_extract(payload,'$.intake_submission')=?",
                                                   (actor, row["id"])).fetchone()
                if already:
                    result = json.loads(already["payload"])["result"]
                elif kind == "claim":
                    for evidence in payload["evidence"]:
                        sid = evidence["source_id"]
                        if ledger.store.source(sid):
                            continue
                        with intake.connect() as db:
                            stored = db.execute("SELECT body FROM sources WHERE id=?", (sid,)).fetchone()
                        if not stored:
                            continue
                        src = json.loads(stored[0])
                        raw = sources.read_raw(src, root=intake.root / "sources")
                        text = sources.read_text(src, root=intake.root / "sources")
                        if raw is None or text is None or sha256(raw) != src["raw_hash"] or sha256(text.encode()) != src["text_hash"]:
                            raise ValueError("Intake source archive is missing or changed")
                        copied = sources.archive(raw, src["url"], src["media_type"], src["license"], src["redistributable"], root=archive)
                        if copied.source_id != sid:
                            raise ValueError("Source canonicalization changed")
                        copied.retrieved = src["retrieved"]
                        ledger.add_source(copied, signer)
                    created = datetime.fromtimestamp(row["created"], timezone.utc).isoformat(timespec="microseconds")
                    claim = {"assertion": payload["assertion"], "evidence": payload["evidence"],
                             "provenance": {"contributor": actor, "agent": "mcp-contributor", "model": profile["model"],
                                            "prompt": payload["prompt"], "created": created, "intake_submission": row["id"]}}
                    proposed = ledger.propose(claim, signer)
                    result = {"state": "kernel_accepted" if proposed.accepted else "kernel_rejected", "claim_id": proposed.claim_id,
                              "assertion_id": proposed.assertion_id, "checks": proposed.checks,
                              "review_status": ledger.claim_status(proposed.claim_id) if proposed.accepted else "not_reviewable", "published": False}
                elif kind == "review":
                    if not profile["allow_review"]:
                        raise ValueError("Reviewer permission was revoked or not granted")
                    prior = ledger.store.db.execute("SELECT id FROM events WHERE type='review.attested' AND actor=? AND json_extract(payload,'$.submission_id')=?",
                                                    (actor, row["id"])).fetchone()
                    human = profile.get("kind") == "human"
                    eid = prior[0] if prior else ledger.review(payload["claim_id"], payload["verdict"], payload["reason"], signer,
                                                              model_family=None if human else profile["model_family"], model=None if human else profile["model"],
                                                              prompt=payload["prompt"], submission_id=row["id"])
                    result = {"state": "review_recorded", "event_id": eid, "claim_id": payload["claim_id"],
                              "review_status": ledger.claim_status(payload["claim_id"]), "published": False}
                elif kind == "challenge":
                    if not ledger.store.claim(payload["claim_id"]):
                        raise ValueError("Challenge target no longer exists")
                    prior = ledger.store.db.execute("SELECT id FROM events WHERE type='claim.challenged' AND actor=? AND json_extract(payload,'$.submission_id')=?",
                                                    (actor, row["id"])).fetchone()
                    eid = prior[0] if prior else ledger.challenge(payload["claim_id"], payload["reason"], signer, payload.get("counter_claim"), submission_id=row["id"])
                    result = {"state": "challenge_recorded", "event_id": eid, "claim_id": payload["claim_id"], "published": False}
                else:
                    raise ValueError("Unsupported submission kind")
                if not already:
                    ledger._append(signer, "intake.processed", result.get("claim_id"), {"intake_submission": row["id"], "result": result})
                    ledger.store.commit()
            except (ValueError, KeyError, TypeError) as error:
                result = {"state": "rejected", "error": str(error)[:400], "published": False}
            with intake.connect() as db:
                db.execute("UPDATE submissions SET state=?,result=? WHERE id=?", (result["state"], json.dumps(result), row["id"]))
                task = db.execute("SELECT * FROM tasks WHERE id=?", (row["task_id"],)).fetchone()
                intake.event(db, actor, task, result["state"], row["id"])
                if kind == "review" and result["state"] == "review_recorded":
                    db.execute("UPDATE tasks SET state='complete',expires=0 WHERE id=?", (row["task_id"],))
            results.append({"submission_id": row["id"], **result})
        if results:
            ledger.publish_tree_head()
        return {"processed": results, "log_verified": ledger.verify_log()["ok"], "model_calls": 0, "website_published": False}
    finally:
        ledger.store.close()
