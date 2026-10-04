"""Bounded, resumable registry collection and screening; never writes the claims ledger.

python -m enrich.trials.full_run collect
python -m enrich.trials.full_run screen --budget 30 --workers 24
python -m enrich.trials.full_run export

Collection scans shared API pages once and indexes names locally. Screening keeps the
reviewed v2 prompt/quote gates; batches are scheduling waves, not changed model prompts.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from contextlib import contextmanager

from . import run as pilot
from pipeline import http_cache, llm
from ledger.canonical import sha256
from ledger.sources import archive

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/enrichment/trials/full"
FIELDS = "NCTId,BriefTitle,OfficialTitle,Condition,Keyword,BriefSummary,DetailedDescription,StudyType,PatientRegistry,EligibilityCriteria,StudyPopulation,InterventionType,InterventionName,InterventionDescription,PrimaryOutcomeMeasure,PrimaryOutcomeDescription,OverallStatus,WhyStopped,LastUpdatePostDate"


@contextmanager
def single_run(phase):
    """OS releases the lock on exit/crash; a second screener cannot double the budget."""
    import os
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f".{phase}.lock", "a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0"); lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def connect():
    OUT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(OUT / "jobs.db", timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS studies (nct TEXT PRIMARY KEY, body TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS pairs (cid TEXT, nct TEXT, priority INTEGER, decision TEXT, PRIMARY KEY(cid,nct));
        CREATE INDEX IF NOT EXISTS queue ON pairs(decision,priority);
        CREATE INDEX IF NOT EXISTS condition_queue ON pairs(cid,decision,priority,nct);
    """)
    return db


def meta(db, key, default=None):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_meta(db, key, value):
    db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))


def conditions():
    path = OUT / "conditions.jsonl"
    if not path.exists():
        rows = pilot.read_jsonl(ROOT / "data/build/conditions.jsonl")
        pilot.write_jsonl(path, [pilot.condition_context(c) for c in rows])
    return {c["id"]: c for c in pilot.read_jsonl(path)}


class NameIndex:
    """Token trie mirrors the pilot's case/punctuation-insensitive phrase boundaries.

    Unlike thousands of regex scans per record, each text token walks only matching
    prefixes. Generic aliases that the pilot excludes from queries are not indexed.
    """
    def __init__(self, rows, primary_only=False):
        self.root = {}
        self.ambiguous = {}
        for c in rows:
            names = [c.get("name"), c.get("disease_name"), *([] if primary_only else c.get("also_known_as") or [])]
            names = [n for n in names if n and len(n) >= 4 and n.casefold() not in pilot.GENERIC]
            terms = [c["gene"], *names]
            # Ordinary English words must look like gene symbols, or have a disease
            # name match. This prevents WAS matching the verb in almost every trial.
            if c["gene"] in {"WAS", "SET", "MET", "REST", "KIT", "CAT", "ARC", "CLOCK", "ACHE", "HR", "FAN", "SHE"}:
                self.ambiguous[c["id"]] = (c["gene"], [re.compile(r"(?<!\w)" + r"[\W_]+".join(re.escape(p) for p in re.findall(r"\w+", n)) + r"(?!\w)", re.I) for n in names])
            for term in terms:
                tokens = re.findall(r"[^\W_]+", term.casefold())
                if not tokens:
                    continue
                node = self.root
                for token in tokens:
                    node = node.setdefault(token, {})
                node.setdefault(None, set()).add(c["id"])

    def match(self, text):
        tokens = re.findall(r"[^\W_]+", text.casefold())
        found = set()
        for i, token in enumerate(tokens):
            node = self.root.get(token)
            j = i + 1
            while node is not None:
                found.update(node.get(None, ()))
                if j >= len(tokens):
                    break
                node = node.get(tokens[j])
                j += 1
        return {cid for cid in found if cid not in self.ambiguous or
                re.search(r"(?<!\w)" + re.escape(self.ambiguous[cid][0]) + r"(?!\w)", text) or
                any(p.search(text) for p in self.ambiguous[cid][1])}


def collect(max_pages=0):
    db = connect()
    if meta(db, "collection_complete", False):
        print("Collection already complete.", flush=True)
        return
    index = NameIndex(conditions().values())
    primary_index = NameIndex(conditions().values(), primary_only=True)
    http_cache.CACHE = OUT / "cache/http"
    count = 0
    while not max_pages or count < max_pages:
        page = meta(db, "pages", 0)
        token = meta(db, "page_token")
        params = {"format": "json", "pageSize": 1000, "countTotal": "true", "fields": FIELDS, "sort": "LastUpdatePostDate:desc"}
        if token:
            params["pageToken"] = token
        payload = http_cache.fetch_json(pilot.API, params, min_interval=1.25)
        records = payload.get("studies", [])
        retrieved = pilot.now()
        for study in records:
            p = study["protocolSection"]
            nct = p["identificationModule"]["nctId"]
            text = pilot.render(study)
            matches = index.match(text)
            if not matches:
                continue
            primary_population = primary_index.match("\n".join(value for key, value in pilot.study_fields(study) if key in {"Title", "Official title", "Conditions", "Study population"}))
            primary_eligibility = primary_index.match("\n".join(value for key, value in pilot.study_fields(study) if key == "Eligibility"))
            primary_full = primary_index.match(text)
            db.execute("INSERT OR IGNORE INTO studies VALUES (?,?,?)", (nct, json.dumps(study, ensure_ascii=False), json.dumps({"retrieved": retrieved})))
            db.executemany("INSERT OR IGNORE INTO pairs VALUES (?,?,?,NULL)", [(cid, nct, 0 if cid in primary_population else 1 if cid in primary_eligibility else 2 if cid in primary_full else 3) for cid in matches])
        set_meta(db, "pages", page + 1)
        set_meta(db, "records_seen", meta(db, "records_seen", 0) + len(records))
        set_meta(db, "registry_total", payload.get("totalCount"))
        set_meta(db, "page_token", payload.get("nextPageToken"))
        set_meta(db, "collection_updated", pilot.now())
        set_meta(db, "collection_complete", not payload.get("nextPageToken"))
        db.commit()
        count += 1
        print(json.dumps({"phase": "collect", "pages": page + 1, "records_seen": meta(db, "records_seen"), "matched_studies": db.execute("SELECT COUNT(*) FROM studies").fetchone()[0], "pairs": db.execute("SELECT COUNT(*) FROM pairs").fetchone()[0]}), flush=True)
        if not payload.get("nextPageToken"):
            break
    db.close()


class RateGate:
    def __init__(self, tpm=750000, rpm=700):
        self.tpm, self.rpm = tpm, rpm
        self.calls = deque()
        self.lock = threading.Lock()

    def acquire(self, tokens):
        if tokens > self.tpm:
            raise ValueError("One request exceeds the token admission limit")
        while True:
            with self.lock:
                now = time.monotonic()
                while self.calls and self.calls[0][0] <= now - 60:
                    self.calls.popleft()
                if len(self.calls) < self.rpm and sum(x[1] for x in self.calls) + tokens <= self.tpm:
                    self.calls.append((now, tokens))
                    return
                pause = max(.05, self.calls[0][0] + 60 - now)
            time.sleep(min(pause, 2))


def token_bound(messages):
    return len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 1024


def reserve_usd(messages):
    pin, pout = llm.PRICES[pilot.MODEL]
    return (2 * token_bound(messages) * pin + (1200 + 4096) * pout) / 1e6


def usage():
    rows = pilot.read_jsonl(llm.USAGE)
    if any(r.get("usd") is None or r.get("input_tokens") is None or r.get("output_tokens") is None for r in rows):
        raise RuntimeError("Missing token accounting; no more paid requests allowed")
    return {"calls": len(rows), "usd": sum(r["usd"] for r in rows),
            "input_tokens": sum(r["input_tokens"] for r in rows), "output_tokens": sum(r["output_tokens"] for r in rows)}


def screen_one(job, gate):
    c, nct, text, messages, truncated, study = job
    attempts, answer, spans, error = [], {}, None, None
    for cap in (1200, 4096):
        from openai import RateLimitError
        for throttle_attempt in range(8):
            gate.acquire(token_bound(messages) + cap)
            try:
                raw = llm.chat(pilot.MODEL, messages, task="trials-full-v2", json_mode=True, max_completion_tokens=cap)
                break
            except RateLimitError:
                if throttle_attempt == 7:
                    raise
                time.sleep(min(45, 5 * (throttle_attempt + 1)))
        try:
            answer = pilot.normalize_decision(json.loads(raw))
            spans = pilot.validate_decision(answer, text, c)
            error = None
        except (ValueError, TypeError) as exc:
            error = str(exc)
        attempts.append({"max_completion_tokens": cap, "raw_output": raw, "validation_error": error})
        if error is None:
            break
    if not isinstance(answer, dict):
        answer = {}
    positive = error is None and spans is not None and answer.get("relevance") in {"direct", "includes_this_condition"}
    return {"condition_id": c["id"], "nct_id": nct, "decision": answer, "span": spans,
            "validation_error": error, "candidate": positive, "created": pilot.now(), "attempts": attempts,
            "truncated_fields": truncated, "status": study["protocolSection"].get("statusModule", {}).get("overallStatus", ""),
            "input_hash": sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode())}


def screen(budget, workers, max_pairs=0):
    db = connect()
    rows = conditions()
    llm.CACHE = OUT / "cache/llm"
    llm.USAGE = OUT / "cache/llm_usage.jsonl"
    # No implicit SDK retries: uncertain calls retain their entire wave reservation.
    # Bounded transient recovery below reserves the next attempt separately.
    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    provider()  # warm the shared token before workers can launch parallel PowerShell logins
    credential_lock = threading.Lock()
    def serialized_token():
        with credential_lock:
            return provider()
    llm._client = llm.client().with_options(api_key=serialized_token, max_retries=0)
    gate = RateGate()
    processed = 0
    stopped_with_error = False
    transient_streak = 0
    transient_total = 0
    previous_uncertain = meta(db, "uncertain_reserved_usd", 0)
    set_meta(db, "budget_usd", budget)
    set_meta(db, "screening_complete", False)
    set_meta(db, "stop_reason", "running")
    set_meta(db, "errors", [])
    db.commit()
    counts = dict(db.execute("SELECT cid,COUNT(*) FROM pairs WHERE decision IS NOT NULL GROUP BY cid").fetchall())
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while not max_pairs or processed < max_pairs:
            available = db.execute("SELECT cid,MIN(priority) AS priority FROM pairs WHERE decision IS NULL GROUP BY cid").fetchall()
            chosen = sorted(available, key=lambda r: (r["priority"], counts.get(r["cid"], 0), r["cid"]))[:workers]
            pending = [db.execute("SELECT cid,nct FROM pairs WHERE cid=? AND decision IS NULL ORDER BY priority,nct LIMIT 1", (r["cid"],)).fetchone() for r in chosen]
            if not pending:
                if meta(db, "collection_complete", False):
                    set_meta(db, "screening_complete", True); set_meta(db, "stop_reason", "complete"); db.commit(); break
                time.sleep(5)
                continue
            spent = usage()["usd"] + previous_uncertain
            jobs, reserve = [], 0
            for pair in pending:
                if max_pairs and processed + len(jobs) >= max_pairs:
                    break
                study = json.loads(db.execute("SELECT body FROM studies WHERE nct=?", (pair["nct"],)).fetchone()[0])
                c = rows[pair["cid"]]
                text = pilot.render(study)
                excerpt, truncated = pilot.screening_excerpt(c, study)
                messages = pilot.messages_for(c, excerpt)
                bound = reserve_usd(messages)
                if spent + reserve + bound > budget:
                    break
                reserve += bound
                jobs.append((c, pair["nct"], text, messages, truncated, study))
            if not jobs:
                set_meta(db, "stop_reason", "budget_cap"); db.commit(); break
            # Durable reservation survives a crash, even if usage logging was interrupted.
            set_meta(db, "uncertain_reserved_usd", previous_uncertain + reserve); db.commit()
            futures = [pool.submit(screen_one, job, gate) for job in jobs]
            failures = []
            transient_only = True
            for job, future in zip(jobs, futures):
                try:
                    decision = future.result()
                    db.execute("UPDATE pairs SET decision=? WHERE cid=? AND nct=?", (json.dumps(decision, ensure_ascii=False), decision["condition_id"], decision["nct_id"]))
                    db.commit()
                    processed += 1
                    counts[decision["condition_id"]] = counts.get(decision["condition_id"], 0) + 1
                except Exception as exc:
                    failures.append(type(exc).__name__ + ": " + str(exc)[:300])
                    transient_only = transient_only and isinstance(exc, (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError))
            if failures:
                transient_streak += 1
                transient_total += 1
                previous_uncertain += reserve
                if transient_only and transient_streak <= 3 and transient_total <= 10:
                    set_meta(db, "stop_reason", "transient_backoff")
                    recovery = meta(db, "recoveries", [])
                    recovery.append({"at": pilot.now(), "errors": failures, "retained_reservation_usd": reserve})
                    set_meta(db, "recoveries", recovery); db.commit()
                    print(json.dumps({"retrying_after_transient_error": failures, "retained_reservation_usd": previous_uncertain}), flush=True)
                    export()
                    time.sleep(min(45, 15 * transient_streak))
                    continue
                stopped_with_error = True
                set_meta(db, "stop_reason", "request_error_reserved_for_review")
                set_meta(db, "errors", failures); db.commit()
                print(json.dumps({"stopped": failures, "reserved_usd": previous_uncertain}), flush=True)
                break
            transient_streak = 0
            set_meta(db, "stop_reason", "running")
            measured = usage()
            set_meta(db, "uncertain_reserved_usd", previous_uncertain)
            set_meta(db, "screening_usage", measured)
            set_meta(db, "screening_updated", pilot.now()); db.commit()
            print(json.dumps({"phase": "screen", "processed_this_run": processed, **measured}), flush=True)
            if processed % 240 == 0:
                export()
    if max_pairs and processed >= max_pairs:
        set_meta(db, "stop_reason", "batch_checkpoint"); db.commit()
    db.close()
    export()
    if stopped_with_error:
        raise RuntimeError("Screening stopped on request errors; see manifest and retained budget reservation")


def export():
    db = connect()
    sources, candidates, decisions = {}, [], []
    for row in db.execute("SELECT decision FROM pairs WHERE decision IS NOT NULL"):
        d = json.loads(row[0])
        if d["candidate"]:
            study = json.loads(db.execute("SELECT body FROM studies WHERE nct=?", (d["nct_id"],)).fetchone()[0])
            source = sources.get(d["nct_id"])
            if source is None:
                source = archive(pilot.render(study).encode(), f"https://clinicaltrials.gov/study/{d['nct_id']}", "text", "ClinicalTrials.gov (public domain)", True, root=OUT / "archive").to_dict()
                source["retrieved"] = json.loads(db.execute("SELECT source FROM studies WHERE nct=?", (d["nct_id"],)).fetchone()[0])["retrieved"]
                sources[d["nct_id"]] = source
                pilot.write_json(OUT / "studies" / f"{d['nct_id']}.json", study)
            d["source_id"] = source["source_id"]
            claim = pilot.candidate_for(d)
            check = pilot.Kernel(None, None).check_schema(claim)
            if not check.passed:
                raise ValueError(check.detail)
            candidates.append(claim)
        decisions.append(d)
    pilot.write_jsonl(OUT / "candidates.jsonl", candidates)
    pilot.write_jsonl(OUT / "sources.jsonl", sources.values())
    pilot.write_jsonl(OUT / "decisions.jsonl", decisions)
    manifest = {"model": pilot.MODEL, "prompt": pilot.PROMPT_VERSION, "mode": "full-registry-local-index",
                "conditions": len(conditions()), "screened_pairs": len(decisions), "candidates": len(candidates),
                "review_status": "unreviewed; never published directly", "coverage": "Whole-word gene and specific supplied condition names in selected registry fields; broader-category studies may be missed.",
                **{r["key"]: json.loads(r["value"]) for r in db.execute("SELECT * FROM meta") if r["key"] != "page_token"}}
    pilot.write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"exported_candidates": len(candidates), "screened_pairs": len(decisions)}), flush=True)
    db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["collect", "screen", "export"])
    parser.add_argument("--budget", type=float, default=30)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--max-pairs", type=int, default=0)
    args = parser.parse_args()
    if not 0 < args.budget <= 30 or not 1 <= args.workers <= 96:
        parser.error("Budget must be <=30 USD; concurrency must be 1..96 (shared token/request gates still apply)")
    with single_run("collect" if args.phase == "collect" else "screen"):
        if args.phase == "collect":
            collect(args.max_pages)
        elif args.phase == "screen":
            screen(args.budget, args.workers, args.max_pairs)
        else:
            export()


if __name__ == "__main__":
    main()
