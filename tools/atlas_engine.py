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
    "daily_usd_cap": 1.0,
    "monthly_usd_cap": 12.0,  # owner's total project ceiling is $60/month: ~37 hosting + 12 reviews + 5 Luna scouts
    # Assumed list prices (USD per million tokens) until real Sol pricing is configured. Conservative on purpose.
    "prices": {"gpt-6-sol": [5.0, 30.0]},
    "peer_review_grace_seconds": 180,
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
        self.month_cap = float(config.get("monthly_usd_cap", 6.0))

    def path(self):
        return STATE / "spend" / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".json")

    @staticmethod
    def total(rows):
        return sum(r["actual"] if r.get("actual") is not None else r["reserved"] for r in rows.values())

    def spent(self):
        return self.total(load_json(self.path(), {}))

    def spent_month(self):
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return sum(self.total(load_json(p, {})) for p in (STATE / "spend").glob(month + "-*.json"))

    def reserve(self, key, model, input_bytes):
        pin, pout = self.prices[model]
        reserved = round((input_bytes / 3) / 1e6 * pin + MAX_OUTPUT_TOKENS / 1e6 * pout, 6)
        if self.spent() + reserved > self.cap or self.spent_month() + reserved > self.month_cap:
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
            reviews = [dict(v) for v in store.reviews_for(row["claim_id"])]
            if row["contributor"] == REFEREE or any(v["reviewer"] == REFEREE for v in reviews):
                continue
            # A peer review settles it, unless a peer rejected the finding: then the referee looks too,
            # so a single strict or careless reviewer cannot bury sourced work alone.
            if reviews and all(v["verdict"] in ("supports", "supports_with_qualification") for v in reviews):
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
            if not any(v["reviewer"] == REFEREE for v in ledger.store.reviews_for(claim_id)):
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


def refresh_plain(subjects, before_c, after_c):
    """Rewrite the everyday description of conditions whose recorded symptoms changed (GPT-6 Luna, cached)."""
    changed = [cid for cid in subjects if cid in after_c and
               [p["id"] for p in after_c[cid].get("phenotypes", [])] != [p["id"] for p in before_c.get(cid, {}).get("phenotypes", [])]]
    if not changed:
        return
    import plain_summaries
    path = ROOT / "data/build/plain.jsonl"
    rows = read_jsonl(path)
    genes = {g["hgnc_id"]: g for g in map(json.loads, (ROOT / "data/build/genes.jsonl").read_text(encoding="utf-8").splitlines()) if g}
    pheno = read_jsonl(ROOT / "data/build/phenotypes.jsonl")
    for cid in changed:
        summary = plain_summaries.summarize(after_c[cid], genes, pheno)
        if summary:
            rows[cid] = summary
            log(f"refreshed plain summary for {cid}")
    temp = path.with_suffix(".tmp")
    temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows.values()), encoding="utf-8")
    temp.replace(path)


def publish(engine, subjects):
    py = sys.executable
    before_n = read_jsonl(ROOT / "data/build/neighbors.jsonl")
    before_c = read_jsonl(ROOT / "data/build/conditions.jsonl")
    log("rebuilding graph from accepted claims…")
    engine.post(None, "rebuilding", {"subjects": sorted(subjects)[:20]})
    run([py, "pipeline/build_graph.py"])
    after_c = read_jsonl(ROOT / "data/build/conditions.jsonl")
    refresh_plain(subjects, before_c, after_c)
    try:
        run([py, "pipeline/study_contacts.py"])  # who runs any newly listed study (official records)
    except RuntimeError as error:
        log(f"study teams not refreshed: {error}")
    run([py, "pipeline/export_app.py"], env={"ATLAS_EXPORT_OUT": str(EXPORT)})
    after_n = read_jsonl(ROOT / "data/build/neighbors.jsonl")

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


# ---- peer review: what peers can review, and calibration cases for new reviewers -------------------------
PEER_PREDICATES = {"has_symptom", "has_asset", "represented_by", "has_name", "studied_by", "has_prevalence"}


def peer_frontier(engine):
    """Kernel-accepted MCP claims still open for review, plus their full claim records for get_claim."""
    from ledger.policy import claim_review_status
    from atlas_mcp.challenge_view import challenge_view
    store = Store(LEDGER, readonly=True)
    items, records = [], {}
    try:
        for row in store.claims_where("kernel_ok=1 AND origin='contributed'"):
            if row["predicate"] not in PEER_PREDICATES or row["subject"] not in engine.conditions:
                continue
            claim = json.loads(row["body"])
            if not claim.get("provenance", {}).get("intake_submission"):
                continue
            reviews = [dict(v) for v in store.reviews_for(row["claim_id"])]
            status = claim_review_status(reviews)
            if status in {"independently_reviewed", "human_reviewed", "rejected"}:
                continue
            items.append({"claim_id": row["claim_id"], "condition_id": row["subject"], "contributor": row["contributor"],
                          "predicate": row["predicate"], "object": row["object"],
                          "reviewed_families": sorted({v["model_family"] for v in reviews if v["model_family"]}),
                          "reviewers": sorted({v["reviewer"] for v in reviews if v.get("reviewer")})})
            history = [{"seq": r["seq"], "type": r["type"], "actor": r["actor"], "at": r["ts"], "redacted": bool(r["redacted"])} for r in store.events_for(row["claim_id"])]
            records[row["claim_id"]] = {"claim_id": row["claim_id"], "claim": claim, "origin": row["origin"], "kernel_accepted": True,
                                        "review_status": status, "reviews": reviews, "history": history, **challenge_view(store, row)}
    finally:
        store.close()
    return items, records


def upload_peer_frontier(engine):
    items, records = peer_frontier(engine)
    digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
    if digest == engine.state.get("peer_frontier"):
        return
    container = engine.cloud.container
    for cid, record in records.items():
        container.upload_blob("live/claims/" + cid.split(":")[-1] + ".json", json.dumps(record, ensure_ascii=False).encode(), overwrite=True)
    container.upload_blob("live/review-frontier.json", json.dumps(items).encode(), overwrite=True)
    engine.state["peer_frontier"] = digest
    save_json(STATE / "state.json", engine.state)


def calibration_cases(engine, limit=60):
    """Known-answer cases from reviewed claims. Answers stay private in storage; agents only see the case.

    Positives and negatives are the referee's recorded decisions; symptom swaps (a real quote paired with a
    symptom it does not mention) are certain negatives. Cases measure careful reading, not outside knowledge.
    """
    import random
    from atlas_mcp.cloud_worker import label
    store = Store(LEDGER, readonly=True)
    cases, symptoms = [], []
    try:
        for row in store.claims_where("kernel_ok=1 AND origin='contributed'"):
            if row["predicate"] not in ("has_symptom", "has_asset", "represented_by") or row["subject"] not in engine.conditions:
                continue
            reviews = [dict(v) for v in store.reviews_for(row["claim_id"])]
            if len(reviews) != 1:
                continue
            claim = json.loads(row["body"])
            ev = claim["evidence"][0]
            src = store.source(ev["source_id"])
            text = sources.read_text(src, root=LEDGER.parent / "sources") if src and src.get("redistributable") else None
            i = text.find(ev["quote"]) if text else -1
            context = text[max(0, i - 1200): i + len(ev["quote"]) + 1200] if i >= 0 else None
            c = engine.conditions[row["subject"]]
            q = claim["assertion"].get("qualifiers", {})
            statement = {"has_symptom": f"Patients with this condition have: {label(row['object']) or row['object']}",
                         "has_asset": f"This study is a {q.get('asset_type', 'study')} relevant to people with this condition",
                         "represented_by": f"{q.get('name') or row['object']} is a {str(q.get('org_type', 'organization')).replace('_', ' ')} serving people with this condition ({q.get('scope', '')})"}[row["predicate"]]
            answer = "support" if reviews[0]["verdict"] in ("supports", "supports_with_qualification") else "reject"
            case = {"condition": f"{c['name']} (gene {c['gene']['symbol']})", "claim": statement, "qualifiers": q,
                    "quote": ev["quote"][:1500], "source_context": context, "answer": answer, "kind": row["predicate"]}
            cases.append(case)
            if row["predicate"] == "has_symptom" and answer == "support":
                symptoms.append((case, row["object"]))
    finally:
        store.close()
    rng = random.Random(7)
    names = [label(h) for _, h in symptoms if label(h)]
    for case, hpo in symptoms:
        other = next((n for n in rng.sample(names, len(names)) if n != label(hpo) and n.lower() not in case["quote"].lower()), None)
        if other:
            cases.append({**case, "claim": f"Patients with this condition have: {other}", "answer": "reject", "kind": "has_symptom (swapped)"})
    rng.shuffle(cases)
    balanced = [c for c in cases if c["answer"] == "reject"][:limit // 2] + [c for c in cases if c["answer"] == "support"][:limit // 2]
    rng.shuffle(balanced)
    for c in balanced:
        c["id"] = "cal-" + hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:16]
    return balanced


def upload_calibration(engine):
    cases = calibration_cases(engine)
    engine.cloud.container.upload_blob("live/calibration.json", json.dumps(cases, ensure_ascii=False).encode(), overwrite=True)
    log(f"calibration set: {len(cases)} cases ({sum(c['answer'] == 'reject' for c in cases)} negatives)")


# ---- keeping the diff base equal to what the website actually serves ---------------------------------------
SITE = os.environ.get("ATLAS_SITE_URL", "https://salmon-island-04aa8f603.1.azurestaticapps.net")


def sync_base(engine):
    """If a new website release was deployed (from anywhere), download its data as the new diff base.

    Returns True when the base changed: the next publication then re-uploads everything newer than that
    release as the live overlay, so a deploy made from an older data snapshot heals itself within minutes."""
    import requests
    if time.time() - engine.state.get("base_checked", 0) < 300:
        return False
    engine.state["base_checked"] = time.time()
    save_json(STATE / "state.json", engine.state)
    meta = requests.get(f"{SITE}/data/meta.json", params={"v": str(time.time())}, timeout=30).json()
    if meta.get("data_id") == load_json(BASE / "meta.json", {}).get("data_id"):
        return False
    log(f"website now serves data {meta.get('data_id')}; downloading it as the new diff base")
    staging = STATE / "base-download"
    if staging.exists():
        import shutil
        shutil.rmtree(staging)
    session = requests.Session()
    for kind, count in meta["shards"].items():
        (staging / kind).mkdir(parents=True, exist_ok=True)
        for n in range(count):
            r = session.get(f"{SITE}/data/{kind}/{n}.json", params={"v": meta["data_id"]}, timeout=60)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            (staging / kind / f"{n}.json").write_bytes(r.content)
    (staging / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    import shutil
    old = BASE.with_name("data.old")
    if old.exists():
        shutil.rmtree(old)
    if BASE.exists():
        BASE.rename(old)
    staging.rename(BASE)
    shutil.rmtree(old, ignore_errors=True)
    return True


# ---- impact frontier: what agents should work on next ----------------------------------------------------
def upload_impact_frontier(engine):
    """Rank conditions by expected impact (pipeline/frontier.py) and publish it for the MCP task list and the website."""
    if time.time() - engine.state.get("frontier_at", 0) < 900:
        return
    engine.state["frontier_at"] = time.time()
    import frontier
    from project_actions import load_actions
    conditions = read_jsonl(ROOT / "data/build/conditions.jsonl")
    variants = load_json(ROOT / "data/build/variants_summary.json", {})
    requests = engine.intake.requests()
    changes = load_json(STATE / "overlay.json", {}).get("changes", [])
    recent = {c["condition_id"] for c in changes if time.time() - c.get("at", 0) < 3 * 86400}
    campaigns = {cid: c["title"] for c in engine.cloud.rows("campaign") if c["status"] == "open" for cid in c["conditions"]}
    rows = frontier.frontier(conditions, load_actions(conditions), variants, {k: v for k, v in requests.items() if k in conditions}, recent,
                             campaigns=campaigns)
    body = {"at": time.time(), "goals": frontier.GOALS, "conditions": rows}
    engine.cloud.container.upload_blob("live/evidence-frontier.json", json.dumps(body).encode(), overwrite=True)
    log(f"impact frontier: top {rows[0]['condition_id'] if rows else '-'} ({sum(1 for r in rows if r['requests'])} requested)")


# ---- contributor track records and earned limits ---------------------------------------------------------
ATLAS_RUN = ("agent:mcp-luna-scout-",)  # MCP identities operated by the atlas itself


def upload_track_records(engine):
    """Public track record per contributor (pipeline/track_record.py); scale MCP contributors' daily limits by level."""
    if time.time() - engine.state.get("records_at", 0) < 900:
        return
    engine.state["records_at"] = time.time()
    import track_record
    from ledger.policy import claim_review_status
    store = Store(LEDGER, readonly=True)
    try:
        claims = [dict(r) for r in store.claims_where("origin = 'contributed'")]
        reviews = [dict(r) for r in store.all_reviews()]
        challenges = [dict(r) for r in store.all_challenges()]
        seqs = {c["created_seq"] for c in claims if c["created_seq"]}
        times = {r[0]: r[1] for r in store.db.execute("SELECT seq, ts FROM events WHERE type LIKE 'claim%'") if r[0] in seqs}
        # Growth history for the replay: each accepted finding at the time of its first supporting review.
        review_ts = dict(store.db.execute("SELECT seq, ts FROM events WHERE type = 'review.attested'").fetchall())
        first_support = {}
        for r in sorted(reviews, key=lambda r: r["seq"]):
            if r["verdict"] in ("supports", "supports_with_qualification") and r["claim_id"] not in first_support:
                first_support[r["claim_id"]] = review_ts.get(r["seq"])
        code = {"has_symptom": "s", "represented_by": "g", "has_asset": "t"}
        findings = sorted([first_support[c["claim_id"]], c["subject"], code.get(c["predicate"], "o")] for c in claims
                          if c["kernel_ok"] and first_support.get(c["claim_id"]) and claim_review_status(
                              [r for r in reviews if r["claim_id"] == c["claim_id"]]) in track_record.ACCEPTED)
        # Expert queue: recent quote-checked findings that no person has reviewed yet (atlas_mcp/expert.py).
        human = {r["claim_id"] for r in reviews if r["reviewer_kind"] == "human"}
        recent = sorted((c for c in claims if c["kernel_ok"] and c["claim_id"] not in human), key=lambda c: -(c["created_seq"] or 0))[:60]
        expert_rows = []
        for c in recent:
            body = json.loads(c["body"])
            evidence = body.get("evidence", [])
            src = store.source(evidence[0]["source_id"]) if evidence and evidence[0].get("source_id") else None
            mine = [r for r in reviews if r["claim_id"] == c["claim_id"]]
            expert_rows.append({"claim_id": c["claim_id"], "condition_id": c["subject"], "predicate": c["predicate"], "object": c["object"],
                                "quotes": [e.get("quote", "") for e in evidence if e.get("quote")], "source_url": (src or {}).get("url", ""),
                                "contributor": c["contributor"], "at": None, "seq": c["created_seq"],
                                "status": claim_review_status(mine), "_claim": {k: c[k] for k in ("predicate", "object", "body")},
                                "ai_reason": mine[-1]["reason"] if mine else None})
    finally:
        store.close()
    terms = load_json(ROOT / "data/build/hpo_terms.json", {})

    def label(c):
        if c["predicate"] == "has_symptom" and terms.get(c["object"]):
            return terms[c["object"]][0]
        q = json.loads(c["body"]).get("qualifiers", {}) if c.get("body") else {}
        return str(q.get("name") or q.get("title") or c["object"])[:120]

    rows = track_record.records(claims, reviews, challenges, lambda seq: times.get(seq), label,
                                lambda cid: engine.conditions.get(cid, {}).get("name", cid))
    profiles = {p["id"]: p for p in engine.cloud.rows("profile")}
    public = []
    for actor, rec in rows.items():
        prof = profiles.get(actor, {})
        mcp = actor.startswith("agent:mcp-")
        public.append({"id": actor.removeprefix("agent:mcp-").removeprefix("agent:").removeprefix("human:"), "name": prof.get("display") or actor.removeprefix("agent:mcp-").removeprefix("agent:").removeprefix("human:expert-"),
                       "family": prof.get("model_family"), "model": prof.get("model"),
                       "run_by": "expert" if actor.startswith("human:expert-") else "atlas" if not mcp or actor.startswith(ATLAS_RUN) else "community",
                       "reviewer": bool(prof.get("allow_review")), "calibration_score": prof.get("calibration_score"),
                       "suspended": prof.get("suspended_reason") if prof.get("suspended") else None,
                       "daily_limit": prof.get("daily_quota"), **{k: v for k, v in rec.items() if k not in ("reviews_agreed",)}})
        if mcp and prof and not actor.startswith(ATLAS_RUN):
            base = prof.get("base_quota", prof.get("daily_quota", 100))
            quota = track_record.earned_quota(base, rec["level"])
            if prof.get("daily_quota") != quota or prof.get("reputation") != rec["level"]:
                def decide(seq, actor=actor, base=base, quota=quota, lvl=rec["level"]):
                    current = engine.cloud.get("profile", actor)
                    return None, [("profile", actor, {**current, "base_quota": base, "daily_quota": quota, "reputation": lvl})]
                engine.cloud.atomic(decide)
                log(f"{actor}: level {rec['level']}, daily limit {quota}")
            public[-1]["daily_limit"] = quota
    kinds = {"has_symptom": "symptom", "has_asset": "study", "represented_by": "patient group", "has_name": "name",
             "studied_by": "researcher", "has_variant_effect": "gene effect", "has_prevalence": "prevalence"}
    for row in expert_rows:
        prof = profiles.get(row["contributor"], {})
        row.update(kind=kinds.get(row["predicate"], row["predicate"]), at=times.get(row.pop("seq")),
                   label=label(row.pop("_claim")),
                   condition=engine.conditions.get(row["condition_id"], {}).get("name", row["condition_id"]),
                   contributor=prof.get("display") or row["contributor"].removeprefix("agent:mcp-").removeprefix("agent:"),
                   status={"unreviewed": "awaiting review", "reviewed": "accepted by one AI reviewer", "independently_reviewed": "accepted by independent reviewers",
                           "rejected": "rejected by an AI reviewer", "review_disagreement": "AI reviewers disagree"}.get(row["status"], row["status"]))
    connections = []
    for e in engine.cloud.rows("activity"):
        if e.get("stage") == "published" and e.get("condition_id"):
            when = datetime.fromtimestamp(e["at"], timezone.utc).isoformat(timespec="seconds")
            connections += [[when, e["condition_id"], n["id"]] for n in (e.get("detail") or {}).get("new_connections", [])]
    engine.cloud.container.upload_blob("live/history.json", json.dumps({"at": time.time(), "findings": findings,
                                                                        "connections": sorted(connections)}).encode(), overwrite=True)
    # Campaign progress (tools/campaigns.py): findings accepted since the start, symptoms now, requests, spend.
    current = read_jsonl(ROOT / "data/build/conditions.jsonl")
    requests_now = engine.intake.requests()
    public_campaigns = []
    for camp in engine.cloud.rows("campaign"):
        since = datetime.fromtimestamp(camp["created"], timezone.utc).isoformat(timespec="seconds")
        public_campaigns.append({**{k: camp.get(k) for k in ("id", "title", "goal", "sponsor", "budget_usd", "spent_usd", "status", "created", "rounds")},
                                 "conditions": [{"condition_id": cid, "name": current.get(cid, {}).get("name", cid),
                                                 "gene": current.get(cid, {}).get("gene", {}).get("symbol"),
                                                 "symptoms": len(current.get(cid, {}).get("phenotypes", [])),
                                                 "findings_since_start": sum(1 for f in findings if f[1] == cid and f[0] >= since),
                                                 "requests": requests_now.get(cid, 0)} for cid in camp["conditions"]]})
    engine.cloud.container.upload_blob("live/campaigns.json", json.dumps({"at": time.time(), "campaigns": public_campaigns}).encode(), overwrite=True)
    engine.cloud.container.upload_blob("live/expert-queue.json", json.dumps({"at": time.time(), "claims": expert_rows}).encode(), overwrite=True)
    public.sort(key=lambda r: (-r["accepted"], -r["reviews_given"], r["id"]))
    engine.cloud.container.upload_blob("live/contributors.json", json.dumps({"at": time.time(), "contributors": public}).encode(), overwrite=True)


# ---- the loop --------------------------------------------------------------------------------------------
class Engine:
    def __init__(self):
        STATE.mkdir(parents=True, exist_ok=True)
        if not CONFIG.exists():
            save_json(CONFIG, DEFAULT_CONFIG)
        self.config = {**DEFAULT_CONFIG, **load_json(CONFIG, {})}
        from atlas_mcp.cloud_store import CloudIntake
        if os.environ.get("ATLAS_STORAGE_CONNECTION_STRING"):  # cloud engine: protected environment file
            from atlas_mcp.cloud import configured_store
            self.cloud = configured_store()
        else:  # operator's PC: Az PowerShell login fetches the key into memory
            from tools.azure_mcp_operator import Operator
            self.cloud = Operator().store()
        self.intake = CloudIntake(self.cloud)
        self.conditions = read_jsonl(ROOT / "data/build/conditions.jsonl")
        self.referee = Referee(self.config, self.conditions)
        self.state = load_json(STATE / "state.json", {"published_size": 0, "pending_subjects": []})
        self.last_beat = 0.0

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
        try:
            if sync_base(self):
                force = True  # republish everything newer than the freshly deployed release
        except Exception as error:
            log(f"base sync skipped: {type(error).__name__}: {error}")
        if time.time() - self.state.get("freshness_at", 0) > 6 * 3600:  # recheck listed studies' registry status
            self.state["freshness_at"] = time.time()
            save_json(STATE / "state.json", self.state)
            # Background collectors (people: PubMed/NIH; variants: weekly ClinVar) changed their output.
            for name, key in (("people.json", "people_size"), ("variants_summary.json", "variants_size")):
                path = ROOT / "data/build" / name
                if path.exists() and path.stat().st_size != self.state.get(key, 0):
                    self.state[key] = path.stat().st_size
                    save_json(STATE / "state.json", self.state)
                    log(f"{name} changed; republishing")
                    force = True
            path = ROOT / "data/build/study_contacts.json"
            before = path.read_bytes() if path.exists() else b""
            try:
                run([sys.executable, "pipeline/study_contacts.py"])
                if path.exists() and path.read_bytes() != before:
                    log("study registry records changed; republishing")
                    force = True
            except RuntimeError as error:
                log(f"freshness check skipped: {error}")
            try:  # retractions of cited papers, organization pages still saying what was quoted (signed ledger events)
                import freshness
                from ledger.api import Ledger
                ledger = Ledger(LEDGER, keys_dir=LEDGER.parent / "keys", source_root=LEDGER.parent / "sources")
                try:
                    counts = freshness.recheck(ledger)
                finally:
                    ledger.store.close()
                if counts:
                    log(f"evidence rechecked: {counts}")
                    force = True
            except Exception as error:
                log(f"evidence recheck skipped: {type(error).__name__}: {error}")
        receipt = pull_and_drain(self.intake, ROOT / "data/contributions/cloud-bridge", LEDGER, limit=50)
        processed = receipt.get("processed", [])
        if processed:
            log(f"kernel processed {len(processed)} submission(s): " + ", ".join(p["state"] for p in processed))
        if not receipt.get("log_verified", True):
            raise RuntimeError("Ledger verification failed; stopping before review or publication")
        try:
            upload_peer_frontier(self)
        except Exception as error:
            log(f"peer frontier upload failed: {error}")
        try:
            upload_track_records(self)
        except Exception as error:
            log(f"track records upload failed: {type(error).__name__}: {error}")
        try:
            upload_impact_frontier(self)
        except Exception as error:
            log(f"impact frontier upload failed: {type(error).__name__}: {error}")
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
            if not subjects:
                subjects = set()
            self.state["pending_subjects"] = sorted(subjects)
            save_json(STATE / "state.json", self.state)
            publish(self, subjects)
            self.state.update(published_size=size, pending_subjects=[], published_at=time.time())
            save_json(STATE / "state.json", self.state)
        elif size != self.state["published_size"] and not subjects:
            self.state["published_size"] = size  # e.g. rejected claims only: nothing visible changed
            save_json(STATE / "state.json", self.state)
        status = {"at": time.time(), "host": os.environ.get("ATLAS_ENGINE_HOST", "operator-pc"), "processed": len(processed),
                  "reviewed": len(reviewed), "ledger_size": size, "spent_today_usd": round(self.referee.budget.spent(), 4),
                  "spent_month_usd": round(self.referee.budget.spent_month(), 4), "cap_usd": self.config["daily_usd_cap"],
                  "month_cap_usd": self.config["monthly_usd_cap"]}
        save_json(STATE / "status.json", status)
        if time.time() - self.last_beat > 60:  # public heartbeat: the website shows whether the engine is online
            try:
                self.cloud.container.upload_blob("live/engine.json", json.dumps(status).encode(), overwrite=True)
                self.last_beat = time.time()
            except Exception as error:
                log(f"heartbeat failed: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force-publish", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    lease = WriterLease(STATE / "engine.lock")
    try:
        engine = Engine()
        log(f"engine started (caps ${engine.config['daily_usd_cap']}/day, ${engine.config['monthly_usd_cap']}/month)")
        upload_calibration(engine)
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
