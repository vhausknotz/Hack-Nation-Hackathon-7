"""Durable local task leases and signed submissions; never modifies the evidence ledger."""
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from ledger import identity
from ledger.canonical import canonical_json, content_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, condition_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL,
 actor TEXT, expires REAL, state TEXT NOT NULL DEFAULT 'open');
CREATE TABLE IF NOT EXISTS submissions (
 id TEXT PRIMARY KEY, actor TEXT NOT NULL, task_id TEXT NOT NULL, kind TEXT NOT NULL,
 payload TEXT NOT NULL, signature TEXT NOT NULL, created REAL NOT NULL,
 state TEXT NOT NULL DEFAULT 'queued', result TEXT);
CREATE INDEX IF NOT EXISTS pending ON submissions(state, created);
CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity (
 seq INTEGER PRIMARY KEY, at REAL NOT NULL, actor TEXT NOT NULL,
 task_id TEXT, condition_id TEXT, stage TEXT NOT NULL, submission_id TEXT);
"""


class Intake:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "intake.db", timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def enroll(self, name, model, family, allow_review=False, quota=100):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", name):
            raise ValueError("Name must be a lowercase slug of 2–61 characters")
        if not model.strip() or not family.strip() or not 1 <= quota <= 1000:
            raise ValueError("Model, model family and a quota between 1 and 1000 are required")
        actor = "agent:mcp-" + name
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM profiles WHERE id=?", (actor,)).fetchone():
                raise ValueError("Profile already exists; identities and review permissions are operator-managed")
            signer = identity.load_or_create(actor, self.root / "keys")
            profile = {"id": actor, "public_key": signer.public_key, "kind": "agent", "model": model,
                       "model_family": family, "allow_review": bool(allow_review), "daily_quota": quota,
                       "manifest": {"role": "mcp-contributor", "model": model, "model_family": family,
                                    "transport": "local-stdio", "version": "atlas-mcp@1"}}
            db.execute("INSERT INTO profiles VALUES (?,?)", (actor, json.dumps(profile)))
        return profile

    def profile(self, actor):
        with self.connect() as db:
            row = db.execute("SELECT body FROM profiles WHERE id=?", (actor,)).fetchone()
        if not row:
            raise ValueError("Unknown contributor; an operator must enroll this local connection first")
        return json.loads(row[0])

    def signer(self, actor):
        profile = self.profile(actor)
        path = self.root / "keys" / f"{actor.replace(':', '_')}.pem"
        if not path.exists():
            raise ValueError("Contributor key is missing; refusing to create a replacement")
        signer = identity.load_or_create(actor, self.root / "keys")
        if signer.public_key != profile["public_key"]:
            raise ValueError("Contributor key does not match enrolled identity")
        return signer

    @staticmethod
    def event(db, actor, task, stage, submission=None):
        db.execute("INSERT INTO activity(at,actor,task_id,condition_id,stage,submission_id) VALUES (?,?,?,?,?,?)",
                   (time.time(), actor, task["id"], task["condition_id"], stage, submission))

    def seed(self, tasks):
        with self.connect() as db:
            db.executemany("INSERT OR IGNORE INTO tasks(id,condition_id,kind,body) VALUES (?,?,?,?)",
                           [(t["id"], t["condition_id"], t["kind"], json.dumps(t)) for t in tasks])

    def tasks(self, condition_id=None, limit=20):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM tasks WHERE state != 'complete' AND (? IS NULL OR condition_id=?) "
                              "ORDER BY CASE kind WHEN 'review' THEN 0 ELSE 1 END, id LIMIT ?",
                              (condition_id, condition_id, limit)).fetchall()
        return [{**json.loads(r["body"]), "state": r["state"],
                 "claimed_by": r["actor"] if (r["expires"] or 0) > time.time() else None,
                 "lease_expires": r["expires"]} for r in rows]

    def claim(self, task_id, actor):
        self.profile(actor)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row or row["state"] == "complete":
                raise ValueError("No open task with this ID")
            if row["actor"] and row["actor"] != actor and (row["expires"] or 0) > time.time():
                raise ValueError("Task is leased to another contributor")
            active = db.execute("SELECT COUNT(*) FROM tasks WHERE actor=? AND expires>? AND state!='complete'", (actor, time.time())).fetchone()[0]
            if row["actor"] != actor and active >= 3:
                raise ValueError("At most three active tasks per contributor")
            expires = time.time() + 1800
            db.execute("UPDATE tasks SET actor=?,expires=? WHERE id=?", (actor, expires, task_id))
            self.event(db, actor, row, "task_claimed")
        return {**json.loads(row["body"]), "lease_expires": expires}

    def owned_task(self, task_id, actor):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row or row["actor"] != actor or (row["expires"] or 0) <= time.time() or row["state"] == "complete":
            raise ValueError("Claim or renew this task before submitting work")
        return dict(row)

    def task(self, task_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def enqueue(self, actor, task_id, kind, payload):
        profile = self.profile(actor)
        sid = content_id("submission", {"actor": actor, "task": task_id, "kind": kind, "payload": payload})
        envelope = {"id": sid, "actor": actor, "task_id": task_id, "kind": kind, "payload": payload}
        signature = self.signer(actor).sign(canonical_json(envelope))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id,state,result FROM submissions WHERE id=?", (sid,)).fetchone()
            if existing:
                return {"submission_id": sid, "state": existing["state"], "duplicate": True}
            task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not task or task["actor"] != actor or (task["expires"] or 0) <= time.time() or task["state"] == "complete":
                raise ValueError("An active task lease is required")
            n = db.execute("SELECT COUNT(*) FROM submissions WHERE actor=? AND created>?", (actor, time.time()-86400)).fetchone()[0]
            if n >= profile["daily_quota"]:
                raise ValueError("Daily submission quota reached; no model work was started")
            db.execute("INSERT INTO submissions(id,actor,task_id,kind,payload,signature,created) VALUES (?,?,?,?,?,?,?)",
                       (sid, actor, task_id, kind, json.dumps(payload), signature, time.time()))
            self.event(db, actor, task, "queued", sid)
        return {"submission_id": sid, "state": "queued", "notice": "Queued for the ledger worker; not reviewed or published. No model calls were made."}

    def submission(self, sid, actor):
        with self.connect() as db:
            row = db.execute("SELECT * FROM submissions WHERE id=? AND actor=?", (sid, actor)).fetchone()
        if not row:
            raise ValueError("No submission for this contributor")
        return {"submission_id": sid, "kind": row["kind"], "state": row["state"], "created": row["created"],
                "result": json.loads(row["result"]) if row["result"] else None}

    def activity(self, after=0, limit=50):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM activity WHERE seq>? ORDER BY seq LIMIT ?", (after, limit))]
