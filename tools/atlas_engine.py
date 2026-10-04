"""The always-running atlas engine: cloud intake -> kernel -> review -> projection -> live website.

    ./.venv/Scripts/python tools/atlas_engine.py            # run until data/engine/stop exists
    ./.venv/Scripts/python tools/atlas_engine.py --once     # one pass, for tests and manual operation

Each pass:
1. pulls signed MCP submissions from Azure and runs them through the kernel (local signed ledger);
2. reviews new kernel-accepted MCP claims. Contributor peer reviews arrive through MCP like any other
   submission; GPT-6 Sol acts as the referee for claims nobody else has reviewed, under a hard daily
   dollar cap with reservations made before every call (an uncertain call keeps its reservation);
3. when the ledger changed, rebuilds the graph, exports into a staging folder, uploads only the shards
   that differ from the deployed website as a versioned live overlay, refreshes the MCP read snapshot,
   and posts what changed (new symptoms, new connections) to the public activity feed.

Only one engine runs at a time (OS lease). Nothing here writes the graph directly: every change is a
claim in the ledger, and the website shows the projection of reviewed claims.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "pipeline"):
    sys.path.insert(0, str(p))

from ledger import identity, sources  # noqa: E402
from ledger.canonical import sha256  # noqa: E402
from ledger.locking import WriterLease  # noqa: E402
from ledger.store import Store  # noqa: E402

STATE = ROOT / "data/engine"
CONFIG = STATE / "config.json"
LEDGER = ROOT / "data/ledger/ledger.db"
BASE = ROOT / "app/public/data"          # what the deployed website serves
EXPORT = STATE / "export"                 # staging export compared against BASE
REFEREE = "agent:atlas-referee-sol"
PUBLISHER = "agent:atlas-publisher"
MODEL, FAMILY = "gpt-6-sol", "openai-gpt6"
MAX_OUTPUT_TOKENS = 4000
DEFAULT_CONFIG = {
    "daily_usd_cap": 5.0,
    # Assumed list prices (USD per million tokens) until real Sol pricing is configured. Conservative on purpose.
    "prices": {"gpt-6-sol": [5.0, 30.0]},
    "peer_review_grace_seconds": 0,
    "poll_seconds": 15,
    "reviewable_predicates": ["has_symptom", "has_asset", "represented_by", "has_name", "studied_by", "has_variant_effect", "has_prevalence"],
}


def log(message):
    line = f"{datetime.now().strftime('%H:%M:%S')} {message}"
    print(line, flush=True)
    with (STATE / "engine.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


# ---- spending: a hard daily cap with reservations ------------------------------------------------------
class Budget:
    def __init__(self, config):
        self.cap, self.prices = float(config["daily_usd_cap"]), config["prices"]

    def path(self):
        return STATE / "spend" / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".json")

    def spent(self):
        rows = load_json(self.path(), {})
        return sum(r["actual"] if r.get("actual") is not None else r["reserved"] for r in rows.values())

    def reserve(self, key, model, input_bytes):
        pin, pout = self.prices[model]
        reserved = round((input_bytes / 3) / 1e6 * pin + MAX_OUTPUT_TOKENS / 1e6 * pout, 6)
        if self.spent() + reserved > self.cap:
            return None
        rows = load_json(self.path(), {})
        rows[key] = {"model": model, "reserved": reserved, "actual": None, "at": time.time()}
        save_json(self.path(), rows)  # reserve BEFORE the call; a crash never frees it
        return reserved

    def settle(self, key, model, usage):
        pin, pout = self.prices[model]
        rows = load_json(self.path(), {})
        if key in rows and usage:
            rows[key]["actual"] = round(usage[0] / 1e6 * pin + usage[1] / 1e6 * pout, 6)
            rows[key]["tokens"] = usage
            save_json(self.path(), rows)


# ---- review ------------------------------------------------------------------------------------------
class Referee:
    def __init__(self, config, conditions):
        import llm
        self.llm, self.config, self.conditions = llm, config, conditions
        self.budget = Budget(config)
        self.onto = None

    def hpo(self):
        if self.onto is None:
            from sources import hpo
            self.onto = hpo.load_ontology()
        return self.onto

    def chat(self, key):
        """A bounded Sol call: reserved first, no SDK retries, usage settled from the token log."""
        def bounded(model, messages, task, **options):
            size = len(json.dumps(messages, ensure_ascii=False).encode())
            if model != MODEL or size > 60_000:
                raise ValueError("Review request exceeds the engine's input allowance")
            if self.budget.reserve(key, model, size) is None:
                raise BudgetExhausted()
            before = self.llm.USAGE.stat().st_size if self.llm.USAGE.exists() else 0
            try:
                return self.llm.chat_json(model, messages, task=task, max_completion_tokens=MAX_OUTPUT_TOKENS,
                                          request_client=self.llm.client().with_options(max_retries=0, timeout=120))
            finally:
                if self.llm.USAGE.exists():
                    with self.llm.USAGE.open("rb") as f:
                        f.seek(before)
                        lines = [json.loads(l) for l in f.read().decode("utf-8").splitlines() if l.strip()]
                    mine = [l for l in lines if l.get("model") == model]
                    if mine:
                        self.budget.settle(key, model, (sum(l.get("input_tokens") or 0 for l in mine), sum(l.get("output_tokens") or 0 for l in mine)))
        return bounded

    def judge(self, claim_id, claim, source_text):
        from agents import verify, trials_import, communities
        a, chat = claim["assertion"], self.chat(claim_id)
        condition = self.conditions[a["subject"]]
        text = window(source_text, [e["quote"] for e in claim["evidence"]])
        if a["predicate"] == "has_symptom":
            term = self.hpo().terms.get(self.hpo().resolve(a["object"]) or "")
            if term is None:
                return {"verdict": "out_of_scope", "reason": "The cited symptom term is not a current HPO term."}
            return verify.verify_symptom(condition, term, claim, text, chat_json=chat)
        if a["predicate"] == "has_asset":
            return trials_import.verify_asset(condition, claim, text, chat_json=chat)
        if a["predicate"] == "represented_by":
            q = a.get("qualifiers", {})
            org = {"name": q.get("name") or a["object"], "homepage": q.get("homepage", ""), "org_type": q.get("org_type"), "scope": q.get("scope")}
            return communities.verify_community(condition, org, "", claim["evidence"][0]["quote"], text, chat_json=chat)
        return verify.verify_generic(condition, claim, text, chat_json=chat)


class BudgetExhausted(Exception):
    pass


def window(text, quotes, limit=30_000):
    """Whole source when small; otherwise the passages around each quote, never silently cut."""
    if len(text) <= limit:
        return text
    parts = []
    for q in quotes:
        i = text.find(q)
        if i >= 0:
            parts.append(text[max(0, i - 3000): i + len(q) + 3000])
    return "\n…\n".join(parts)[:limit]


def review_pass(engine):
    """Referee unreviewed MCP claims. Returns the claims reviewed in this pass."""
    from ledger.api import Ledger
    config = engine.config
    store = Store(LEDGER, readonly=True)
    candidates = []
    try:
        for row in store.claims_where("kernel_ok=1 AND origin='contributed'"):
            claim = json.loads(row["body"])
            if not claim.get("provenance", {}).get("intake_submission"):
                continue  # only MCP contributions; earlier campaigns have their own reviews
            if row["predicate"] not in config["reviewable_predicates"] or row["subject"] not in engine.conditions:
                continue
            if row["contributor"] == REFEREE or store.reviews_for(row["claim_id"]):
                continue
            if store.challenges_for(row["claim_id"]) or store.challenges_for(row["assertion_id"]):
                continue
            created = claim["provenance"].get("created", "")
            age = time.time() - datetime.fromisoformat(created).timestamp() if created else 1e9
            if age < config["peer_review_grace_seconds"]:
                continue  # give contributor reviewers the first chance
            texts = []
            for e in claim["evidence"]:
                src = store.source(e["source_id"])
                text = sources.read_text(src, root=LEDGER.parent / "sources") if src else None
                if text is None or sha256(text.encode()) != src["text_hash"]:
                    texts = None
                    break
                texts.append(text)
            if texts:
                candidates.append((row["claim_id"], claim, "\n\n".join(dict.fromkeys(texts))))
    finally:
        store.close()
    reviewed = []
    attempts = load_json(STATE / "attempts.json", {})
    for claim_id, claim, text in candidates:
        if attempts.get(claim_id, {}).get("state") in ("uncertain", "complete"):
            continue
        judgment = attempts.get(claim_id, {}).get("judgment")
        if not judgment:
            try:
                judgment = engine.referee.judge(claim_id, claim, text)
                if judgment.get("verdict") not in {"supports", "supports_with_qualification", "does_not_support", "out_of_scope"} or not judgment.get("reason"):
                    raise ValueError("Reviewer returned no usable judgment")
            except BudgetExhausted:
                log("daily review budget reached; remaining claims wait for peer review or tomorrow")
                engine.post(None, "budget_reached", {"cap_usd": engine.config["daily_usd_cap"]})
                break
            except Exception as error:
                attempts[claim_id] = {"state": "uncertain", "error": type(error).__name__}
                save_json(STATE / "attempts.json", attempts)
                log(f"review uncertain for {claim_id[:22]}: {type(error).__name__}: {error}")
                continue
            attempts[claim_id] = {"state": "judged", "judgment": judgment}
            save_json(STATE / "attempts.json", attempts)
        ledger = Ledger(LEDGER)
        try:
            if not ledger.store.reviews_for(claim_id):
                signer = ledger.register(identity.load_or_create(REFEREE), kind="agent", manifest={
                    "role": "referee", "model": MODEL, "model_family": FAMILY, "prompt": "engine-referee@1"})
                ledger.review(claim_id, judgment["verdict"], judgment["reason"], signer, model_family=FAMILY, model=MODEL, prompt="engine-referee@1")
                ledger.publish_tree_head()
        finally:
            ledger.store.close()
        attempts[claim_id]["state"] = "complete"
        save_json(STATE / "attempts.json", attempts)
        a = claim["assertion"]
        from atlas_mcp.cloud_worker import label
        engine.post(a["subject"], "review_recorded", {"verdict": judgment["verdict"], "reason": judgment["reason"][:300],
                                                      "predicate": a["predicate"], "object": a["object"], "label": label(a["object"]) or a.get("qualifiers", {}).get("name"),
                                                      "claim_id": claim_id, "reviewer": "GPT-6 Sol (referee)"}, actor=REFEREE)
        log(f"reviewed {a['predicate']} {a['object']} for {a['subject']}: {judgment['verdict']}")
        reviewed.append(claim_id)
    return reviewed


# ---- publication ---------------------------------------------------------------------------------------
def file_hashes(folder):
    out = {}
    for kind in ("c", "g", "s", "grp", "m"):
        for path in (folder / kind).glob("*.json"):
            out[f"{kind}/{path.name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def same_content(a, b):
    try:
        return a.exists() and json.loads(a.read_text(encoding="utf-8")) == json.loads(b.read_text(encoding="utf-8"))
    except ValueError:
        return False


def top_related(neighbors_row):
    rows = [n for n in neighbors_row.get("neighbors", []) if not n.get("same_gene")]
    rows.sort(key=lambda n: (-n["score"], n["id"]))
    return rows[:8]


def read_jsonl(path):
    return {r["id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if r} if path.exists() else {}


def run(args, env=None):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=900, env={**os.environ, **(env or {})})
    if result.returncode:
        raise RuntimeError(f"{Path(args[1]).name} failed: {result.stderr[-1500:]}")
    return result.stdout


def publish(engine, subjects):
    py = sys.executable
    before_n = read_jsonl(ROOT / "data/build/neighbors.jsonl")
    before_c = read_jsonl(ROOT / "data/build/conditions.jsonl")
    log("rebuilding graph from accepted claims…")
    engine.post(None, "rebuilding", {"subjects": sorted(subjects)[:20]})
    run([py, "pipeline/build_graph.py"])
    run([py, "pipeline/export_app.py"], env={"ATLAS_EXPORT_OUT": str(EXPORT)})
    after_n = read_jsonl(ROOT / "data/build/neighbors.jsonl")
    after_c = read_jsonl(ROOT / "data/build/conditions.jsonl")

    base_meta = load_json(BASE / "meta.json", {})
    base_id = base_meta.get("data_id")
    if not base_id:
        raise RuntimeError("Deployed export has no data_id; run a full website deployment first (tools/deploy_website.py)")
    base, staged = file_hashes(BASE), file_hashes(EXPORT)
    manifest = load_json(STATE / "overlay.json", {})
    if manifest.get("base") != base_id:
        manifest = {"base": base_id, "files": {}, "hashes": {}, "changes": []}
    version = hashlib.sha256(f"{time.time()}:{sorted(staged.items())}".encode()).hexdigest()[:16]
    container = engine.cloud.container
    uploaded = 0
    files, hashes = {}, {}
    for path, digest in staged.items():
        if base.get(path) == digest or same_content(BASE / path, EXPORT / path):
            continue  # identical to what the website already serves (key order may differ)
        if manifest["hashes"].get(path) == digest:
            files[path], hashes[path] = manifest["files"][path], digest
            continue
        container.upload_blob(f"live/v/{version}/{path}", (EXPORT / path).read_bytes(), overwrite=True)
        files[path], hashes[path] = version, digest
        uploaded += 1

    changes = []
    for cid in sorted(subjects):
        if cid not in after_c:
            continue
        old = {n["id"] for n in top_related(before_n.get(cid, {}))}
        new_rows = top_related(after_n.get(cid, {}))
        added = [{"id": n["id"], "name": after_c[n["id"]]["name"], "score": n["score"]} for n in new_rows if n["id"] not in old]
        new_symptoms = len(after_c[cid].get("phenotypes", [])) - len(before_c.get(cid, {}).get("phenotypes", []))
        change = {"condition_id": cid, "name": after_c[cid]["name"], "version": version, "at": time.time(),
                  "new_symptoms": new_symptoms, "symptoms": len(after_c[cid].get("phenotypes", [])),
                  "new_connections": added, "connections": len(after_n.get(cid, {}).get("neighbors", []))}
        changes.append(change)
    manifest = {"base": base_id, "version": version, "published_at": time.time(), "files": files, "hashes": hashes,
                "changes": (manifest.get("changes", []) + changes)[-30:]}
    save_json(STATE / "overlay.json", manifest)
    public = {k: manifest[k] for k in ("base", "version", "published_at", "files", "changes")}
    container.upload_blob("live/current.json", json.dumps(public).encode(), overwrite=True)
    log(f"live overlay {version}: {uploaded} new files, {len(files)} total over base {base_id}")
    for change in changes:
        engine.post(change["condition_id"], "published", {k: change[k] for k in ("name", "new_symptoms", "symptoms", "new_connections", "connections")})

    from atlas_mcp.cloud_publish import publish as publish_snapshot
    snapshot = publish_snapshot(engine.cloud, LEDGER, ROOT / "data/build")
    log(f"MCP read snapshot {snapshot['prefix']}")
    return manifest


# ---- the loop --------------------------------------------------------------------------------------------
class Engine:
    def __init__(self):
        STATE.mkdir(parents=True, exist_ok=True)
        if not CONFIG.exists():
            save_json(CONFIG, DEFAULT_CONFIG)
        self.config = {**DEFAULT_CONFIG, **load_json(CONFIG, {})}
        from tools.azure_mcp_operator import Operator
        from atlas_mcp.cloud_store import CloudIntake
        self.cloud = Operator().store()
        self.intake = CloudIntake(self.cloud)
        self.conditions = read_jsonl(ROOT / "data/build/conditions.jsonl")
        self.referee = Referee(self.config, self.conditions)
        self.state = load_json(STATE / "state.json", {"published_size": 0, "pending_subjects": []})

    def post(self, condition_id, stage, detail=None, actor=PUBLISHER):
        try:
            self.intake.post(actor, condition_id, stage, detail)
        except Exception as error:
            log(f"feed post failed: {error}")

    def ledger_size(self):
        store = Store(LEDGER, readonly=True)
        try:
            return store.size()
        finally:
            store.close()

    def once(self, force=False):
        from atlas_mcp.cloud_worker import pull_and_drain
        receipt = pull_and_drain(self.intake, ROOT / "data/contributions/cloud-bridge", LEDGER, limit=50)
        processed = receipt.get("processed", [])
        if processed:
            log(f"kernel processed {len(processed)} submission(s): " + ", ".join(p["state"] for p in processed))
        if not receipt.get("log_verified", True):
            raise RuntimeError("Ledger verification failed; stopping before review or publication")
        reviewed = review_pass(self)
        subjects = set(self.state.get("pending_subjects", []))
        if reviewed:
            store = Store(LEDGER, readonly=True)
            try:
                subjects |= {store.claim(c)["subject"] for c in reviewed}
            finally:
                store.close()
        size = self.ledger_size()
        if force or (size != self.state["published_size"] and subjects) or (reviewed and subjects):
            self.state["pending_subjects"] = sorted(subjects)
            save_json(STATE / "state.json", self.state)
            publish(self, subjects)
            self.state = {"published_size": size, "pending_subjects": [], "published_at": time.time()}
            save_json(STATE / "state.json", self.state)
        elif size != self.state["published_size"] and not subjects:
            self.state["published_size"] = size  # e.g. rejected claims only: nothing visible changed
            save_json(STATE / "state.json", self.state)
        save_json(STATE / "status.json", {"at": time.time(), "processed": len(processed), "reviewed": len(reviewed),
                                          "ledger_size": size, "spent_today_usd": round(self.referee.budget.spent(), 4),
                                          "cap_usd": self.config["daily_usd_cap"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force-publish", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    lease = WriterLease(STATE / "engine.lock")
    try:
        engine = Engine()
        log(f"engine started (cap ${engine.config['daily_usd_cap']}/day)")
        while True:
            try:
                engine.once(force=args.force_publish)
                args.force_publish = False
            except Exception as error:
                log(f"pass failed: {type(error).__name__}: {error}")
                (STATE / "last-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
                if args.once:
                    raise
            if args.once or (STATE / "stop").exists():
                break
            time.sleep(engine.config["poll_seconds"])
        log("engine stopped")
    finally:
        lease.close()


if __name__ == "__main__":
    main()
