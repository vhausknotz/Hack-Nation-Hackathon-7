"""SQLite storage for the ledger (PostgreSQL when hosted; the schema is deliberately portable).

`events` is the append-only log; every other table is an index derived from it and can be
rebuilt by replaying the events. Bulk reference imports store their claims in `claims` and are
represented in the log by one `import.recorded` event whose payload commits to all of them.
"""

import json
import sqlite3
from pathlib import Path

from . import LEDGER_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY,           -- position in the log (0-based leaf index = seq - 1)
    id         TEXT UNIQUE NOT NULL,          -- content id of the unsigned event
    type       TEXT NOT NULL,
    target     TEXT,
    actor      TEXT NOT NULL,
    ts         TEXT NOT NULL,
    payload    TEXT,                          -- canonical JSON; NULL once redacted
    signature  TEXT NOT NULL,
    leaf_hash  BLOB NOT NULL,
    redacted   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS events_target ON events(target);
CREATE INDEX IF NOT EXISTS events_type ON events(type);

CREATE TABLE IF NOT EXISTS contributors (
    id          TEXT PRIMARY KEY,
    public_key  TEXT NOT NULL,
    kind        TEXT NOT NULL,                -- agent | human | importer | kernel | log
    manifest    TEXT NOT NULL,
    registered  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id      TEXT PRIMARY KEY,
    assertion_id  TEXT NOT NULL,
    subject       TEXT NOT NULL,
    predicate     TEXT NOT NULL,
    object        TEXT NOT NULL,
    body          TEXT NOT NULL,              -- canonical claim JSON
    contributor   TEXT NOT NULL,
    origin        TEXT NOT NULL,              -- reference | contributed
    import_id     TEXT,                       -- for reference claims: the import event id
    kernel_ok     INTEGER NOT NULL,
    created_seq   INTEGER
);
CREATE INDEX IF NOT EXISTS claims_assertion ON claims(assertion_id);
CREATE INDEX IF NOT EXISTS claims_subject ON claims(subject, predicate);
CREATE INDEX IF NOT EXISTS claims_object ON claims(object, predicate);
CREATE INDEX IF NOT EXISTS claims_origin ON claims(origin);

CREATE TABLE IF NOT EXISTS reviews (
    event_id      TEXT PRIMARY KEY,
    claim_id      TEXT NOT NULL,
    reviewer      TEXT NOT NULL,
    reviewer_kind TEXT NOT NULL,              -- model | human
    model_family  TEXT,                       -- e.g. openai-gpt6, deepseek; NULL for humans
    model         TEXT,
    verdict       TEXT NOT NULL,
    reason        TEXT NOT NULL,
    seq           INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS reviews_claim ON reviews(claim_id);

CREATE TABLE IF NOT EXISTS challenges (
    event_id      TEXT PRIMARY KEY,
    target        TEXT NOT NULL,              -- claim id or assertion id
    counter_claim TEXT,                       -- claim id of the counter-evidence, if any
    challenger    TEXT NOT NULL,
    reason        TEXT NOT NULL,
    seq           INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS challenges_target ON challenges(target);

CREATE TABLE IF NOT EXISTS sources (
    source_id     TEXT PRIMARY KEY,
    body          TEXT NOT NULL               -- Source record as JSON
);

CREATE TABLE IF NOT EXISTS tree_heads (
    size          INTEGER PRIMARY KEY,
    root          TEXT NOT NULL,
    ts            TEXT NOT NULL,
    signature     TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path = LEDGER_DIR / "ledger.db", *, readonly: bool = False):
        if not readonly:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) if readonly else sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        if readonly:
            self.db.execute("BEGIN")  # one consistent snapshot while a campaign appends
        else:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # ---- events -------------------------------------------------------------------------------------
    def append_event(self, event: dict, leaf_hash: bytes) -> int:
        cur = self.db.execute(
            "INSERT INTO events (id, type, target, actor, ts, payload, signature, leaf_hash) VALUES (?,?,?,?,?,?,?,?)",
            (event["id"], event["type"], event.get("target"), event["actor"], event["ts"],
             json.dumps(event["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False), event["signature"], leaf_hash),
        )
        return cur.lastrowid

    def event(self, event_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

    def events_for(self, target: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM events WHERE target = ? ORDER BY seq", (target,)).fetchall()

    def leaf_hashes(self, size: int | None = None) -> list[bytes]:
        q = "SELECT leaf_hash FROM events ORDER BY seq" + (f" LIMIT {int(size)}" if size is not None else "")
        return [bytes(r[0]) for r in self.db.execute(q)]

    def size(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def redact(self, event_id: str) -> None:
        self.db.execute("UPDATE events SET payload = NULL, redacted = 1 WHERE id = ?", (event_id,))

    # ---- contributors -------------------------------------------------------------------------------
    def add_contributor(self, cid: str, public_key: str, kind: str, manifest: dict, ts: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO contributors VALUES (?,?,?,?,?)", (cid, public_key, kind, json.dumps(manifest, sort_keys=True), ts))

    def contributor(self, cid: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM contributors WHERE id = ?", (cid,)).fetchone()

    # ---- claims ---------------------------------------------------------------------------------------
    def add_claims(self, rows: list[tuple]) -> None:
        self.db.executemany("INSERT OR IGNORE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)

    def claim(self, claim_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()

    def claims_where(self, sql: str = "1=1", params: tuple = ()) -> list[sqlite3.Row]:
        return self.db.execute(f"SELECT * FROM claims WHERE {sql}", params).fetchall()

    # ---- reviews, challenges, sources, tree heads ---------------------------------------------------------
    def add_review(self, row: tuple) -> None:
        self.db.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", row)

    def reviews_for(self, claim_id: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM reviews WHERE claim_id = ? ORDER BY seq", (claim_id,)).fetchall()

    def all_reviews(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM reviews ORDER BY seq").fetchall()

    def add_challenge(self, row: tuple) -> None:
        self.db.execute("INSERT INTO challenges VALUES (?,?,?,?,?,?)", row)

    def challenges_for(self, target: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM challenges WHERE target = ? ORDER BY seq", (target,)).fetchall()

    def all_challenges(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM challenges ORDER BY seq").fetchall()

    def add_source(self, source_id: str, body: dict) -> None:
        self.db.execute("INSERT OR IGNORE INTO sources VALUES (?,?)", (source_id, json.dumps(body, sort_keys=True)))

    def source(self, source_id: str) -> dict | None:
        row = self.db.execute("SELECT body FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def add_tree_head(self, size: int, root: str, ts: str, signature: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO tree_heads VALUES (?,?,?,?)", (size, root, ts, signature))

    def tree_heads(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM tree_heads ORDER BY size").fetchall()

    def commit(self) -> None:
        self.db.commit()
