"""Continuously refill work, adapt concurrency, keep per-job durable cost reservations."""
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import heapq
import json
import math
import statistics
import threading
import time

from . import full_run as base


class AdaptiveGate:
    def __init__(self, initial=96, maximum=384, target_tpm=950000, target_rpm=950, clock=time.monotonic):
        self.clock = clock
        self.target, self.maximum = min(initial, maximum), maximum
        self.tpm, self.rpm = target_tpm, target_rpm
        self.calls, self.completions, self.errors = deque(), deque(), deque()
        self.lock = threading.RLock()
        self.local = threading.local()
        self.ratio = .30  # observed prompt tokens / serialized UTF-8 bytes; refined from actual responses
        self.cooldown = self.last_backoff = 0
        self.last_adjust = clock()
        self.baseline = None
        self.factor = 1.0

    def trim(self, now):
        for queue in (self.calls, self.completions, self.errors):
            while queue and queue[0][0] <= now-60:
                queue.popleft()

    def acquire_request(self, messages, cap):
        size = len(json.dumps(messages, ensure_ascii=False).encode())
        self.local.input_bytes = size
        while True:
            with self.lock:
                now = self.clock(); self.trim(now)
                estimate = math.ceil(size * self.ratio * 1.08) + cap + 32
                if estimate > self.tpm * self.factor:
                    raise ValueError("Request exceeds rate admission capacity")
                # Smooth requests as well as enforcing rolling minute limits.
                spacing = 60 / (self.rpm * self.factor)
                allowed = not self.calls or now-self.calls[-1][0] >= spacing
                if now >= self.cooldown and allowed and len(self.calls) < self.rpm*self.factor and sum(c[1] for c in self.calls)+estimate <= self.tpm*self.factor:
                    self.calls.append((now, estimate))
                    return
            time.sleep(.05)

    def observed(self, entry):
        with self.lock:
            now = self.clock(); self.trim(now)
            self.completions.append((now, entry["input_tokens"]+entry["output_tokens"], entry["seconds"]))
            size = getattr(self.local, "input_bytes", 0)
            if size:
                measured = entry["input_tokens"] / size
                self.ratio = max(.1, min(1.0, .95*self.ratio + .05*measured))

    def failed(self, exc):
        with self.lock:
            now = self.clock()
            self.errors.append((now, type(exc).__name__))
            # One shared backoff per interval, rather than multiplying it by every worker.
            if now-self.last_backoff < 10:
                return
            self.last_backoff = now
            self.target = max(8, int(self.target*.7))
            if type(exc).__name__ == "RateLimitError":
                self.factor = max(.35, self.factor*.85)
                headers = getattr(getattr(exc, "response", None), "headers", {})
                try:
                    pause = float(headers.get("retry-after", 5))
                except (ValueError, TypeError):
                    pause = 5
                self.cooldown = max(self.cooldown, now + min(120, max(1, pause)))

    def snapshot(self, adjust=True):
        with self.lock:
            now = self.clock(); self.trim(now)
            latencies = sorted(x[2] for x in self.completions)
            median = statistics.median(latencies) if latencies else 0
            p95 = latencies[min(len(latencies)-1, int(.95*len(latencies)))] if latencies else 0
            if adjust and now-self.last_adjust >= 15:
                self.last_adjust = now
                if self.baseline is None and len(latencies) >= 20:
                    self.baseline = median
                worsened = self.baseline and median > max(3, self.baseline*1.8)
                if worsened:
                    self.target = max(8, int(self.target*.8))
                elif not self.errors:
                    self.target = min(self.maximum, self.target+max(8, self.target//4))
                    self.factor = min(1., self.factor+.03)
                    if median:
                        self.baseline = median if self.baseline is None else self.baseline*.95+median*.05
            return {"rolling_actual_tpm": sum(x[1] for x in self.completions), "rolling_actual_rpm": len(self.completions),
                    "rolling_admitted_tpm": sum(x[1] for x in self.calls), "rolling_admitted_rpm": len(self.calls),
                    "latency_median_seconds": median, "latency_p95_seconds": p95, "errors_last_minute": len(self.errors),
                    "target_concurrency": self.target, "prompt_tokens_per_byte": round(self.ratio, 3), "rate_factor": round(self.factor, 3)}


def run(budget=30, initial=96, maximum=384, max_pairs=0):
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
    import httpx
    db = base.connect()
    conditions = base.conditions()
    base.llm.CACHE = base.OUT / "cache/llm"
    base.llm.USAGE = base.OUT / "cache/llm_usage.jsonl"
    provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    provider()
    auth_lock = threading.Lock()
    def token():
        with auth_lock:
            return provider()
    base.llm._client = base.llm.client().with_options(api_key=token, max_retries=0, timeout=120,
        http_client=httpx.Client(limits=httpx.Limits(max_connections=maximum, max_keepalive_connections=maximum), timeout=120))
    gate = AdaptiveGate(initial, maximum)
    measured = base.usage()
    usage_lock = threading.Lock()
    original_log = base.llm.log_usage
    def observe(entry):
        original_log(entry)  # write the billing receipt before releasing any reservation
        if any(entry.get(k) is None for k in ("usd", "input_tokens", "output_tokens")):
            raise RuntimeError("Missing token accounting; reservation retained")
        with usage_lock:
            measured["calls"] += 1
            for key in ("usd", "input_tokens", "output_tokens"):
                measured[key] += entry[key]
        gate.observed(entry)
    base.llm.log_usage = observe
    retained = base.meta(db, "uncertain_reserved_usd", 0)
    reserved = retained
    counts = dict(db.execute("SELECT cid,COUNT(*) FROM pairs WHERE decision IS NOT NULL GROUP BY cid").fetchall())
    heap = [(r[1], counts.get(r[0], 0), r[0]) for r in db.execute("SELECT cid,MIN(priority) FROM pairs WHERE decision IS NULL GROUP BY cid")]
    heapq.heapify(heap)
    retries, delayed, pending = {}, [], {}
    completed = 0
    last_report = time.monotonic()
    last_export = 0
    stopping, reason = False, "running"
    stop_file = base.OUT / "stop-screening"
    for k, value in {"budget_usd": budget, "screening_complete": False, "stop_reason": reason, "scheduler": "continuous@1"}.items():
        base.set_meta(db, k, value)
    db.commit()

    def requeue(cid, delay=0):
        row = db.execute("SELECT priority FROM pairs WHERE cid=? AND decision IS NULL ORDER BY priority,nct LIMIT 1", (cid,)).fetchone()
        if row:
            item = (row[0], counts.get(cid, 0), cid)
            if delay:
                heapq.heappush(delayed, (time.monotonic()+delay, item))
            else:
                heapq.heappush(heap, item)

    try:
        with ThreadPoolExecutor(max_workers=maximum) as pool:
            while pending or (not stopping and (heap or delayed)):
                now = time.monotonic()
                while delayed and delayed[0][0] <= now:
                    heapq.heappush(heap, heapq.heappop(delayed)[1])
                stats = gate.snapshot()
                if stop_file.exists():
                    stopping, reason = True, "operator_checkpoint"
                if max_pairs and completed >= max_pairs:
                    stopping, reason = True, "batch_checkpoint"
                while not stopping and heap and len(pending) < gate.target and (not max_pairs or completed+len(pending) < max_pairs):
                    priority, count, cid = heapq.heappop(heap)
                    pair = db.execute("SELECT nct FROM pairs WHERE cid=? AND decision IS NULL ORDER BY priority,nct LIMIT 1", (cid,)).fetchone()
                    if not pair:
                        continue
                    nct = pair[0]
                    study = json.loads(db.execute("SELECT body FROM studies WHERE nct=?", (nct,)).fetchone()[0])
                    c = conditions[cid]
                    excerpt, truncated = base.pilot.screening_excerpt(c, study)
                    messages = base.pilot.messages_for(c, excerpt)
                    bound = base.reserve_usd(messages)
                    with usage_lock:
                        spent = measured["usd"]
                    if spent+reserved+bound > budget:
                        heapq.heappush(heap, (priority, count, cid))
                        if not pending:
                            stopping, reason = True, "budget_cap"
                        break
                    reserved += bound
                    base.set_meta(db, "uncertain_reserved_usd", reserved); db.commit()
                    job = (c, nct, base.pilot.render(study), messages, truncated, study)
                    pending[pool.submit(base.screen_one, job, gate)] = (cid, nct, bound)
                if pending:
                    done, _ = wait(pending, timeout=.5, return_when=FIRST_COMPLETED)
                else:
                    done = set()
                    if delayed and not stopping:
                        time.sleep(.1)
                for future in done:
                    cid, nct, bound = pending.pop(future)
                    try:
                        decision = future.result()
                        db.execute("UPDATE pairs SET decision=? WHERE cid=? AND nct=?", (json.dumps(decision, ensure_ascii=False), cid, nct))
                        completed += 1
                        counts[cid] = counts.get(cid, 0)+1
                        reserved = max(retained, reserved-bound)
                        base.set_meta(db, "uncertain_reserved_usd", reserved)
                        db.commit()  # result and reservation release commit atomically
                        requeue(cid)
                    except Exception as exc:
                        # Leave this request's worst-case reservation in place on uncertain billing.
                        retained += bound
                        gate.failed(exc)
                        key = (cid, nct)
                        retries[key] = retries.get(key, 0)+1
                        transient = isinstance(exc, (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError))
                        print(json.dumps({"request_error": type(exc).__name__, "condition": cid, "study": nct,
                                          "attempt": retries[key], "retained_usd": retained}), flush=True)
                        if transient and retries[key] <= 3:
                            requeue(cid, delay=min(60, retries[key]*10))
                        else:
                            stopping, reason = True, "request_error_reserved_for_review"
                if now-last_report >= 10:
                    with usage_lock:
                        totals = dict(measured)
                    report = {"phase": "continuous_screen", "processed_this_run": completed, "in_flight": len(pending),
                              "retained_uncertain_usd": retained, "reserved_including_in_flight_usd": reserved, **totals, **gate.snapshot(False)}
                    base.set_meta(db, "screening_usage", totals)
                    base.set_meta(db, "throughput", report)
                    base.set_meta(db, "screening_updated", base.pilot.now()); db.commit()
                    print(json.dumps(report), flush=True)
                    (base.OUT / "throughput.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    last_report = now
                if completed-last_export >= 1000:
                    base.export()
                    last_export = completed
        if reason == "running":
            reason = "complete" if base.meta(db, "collection_complete", False) else "collection_checkpoint"
        base.set_meta(db, "stop_reason", reason)
        base.set_meta(db, "screening_complete", reason == "complete")
        base.set_meta(db, "screening_usage", measured)
        db.commit()
    finally:
        # Worker threads have ended before restoring the shared observer.
        base.llm.log_usage = original_log
        db.close()
    base.export()
    if reason == "request_error_reserved_for_review":
        raise RuntimeError("Screening stopped after repeated or non-transient request errors")
