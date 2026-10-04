"""Public, read-only live layer for the website: activity, agent presence and the data overlay.

Everything here is operational status, never evidence. Presence says an agent is working
near a condition; only kernel checks and reviews make its work part of the atlas. Rows are
sanitized before they leave the service: no payloads, prompts, keys or principals.
"""
import json
import re
import threading
import time

from azure.core.exceptions import ResourceNotFoundError

PRESENCE_TTL = 900  # seconds an agent stays on the map (fading) after its last tool call
FEED_EVENTS = 80
OVERLAY_PATH = re.compile(r"[a-f0-9]{16}/(c|g|s|grp|m)/\d{1,3}\.json")
GENE_SYMBOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,29}")
CONDITION_ID = re.compile(r"MONDO:\d{7}(-HGNC:\d{1,6})?")

# Tool -> what the agent is doing, in plain words (shown on the map).
DOING = {
    "search": "searching the atlas", "condition": "reading a condition", "claim": "inspecting a claim",
    "schema": "reading the contribution rules", "frontier": "looking for open tasks", "claim_task": "taking on a task",
    "source": "reading a source", "fetch_source": "fetching a source", "submit_claim": "submitting a finding",
    "submit_review": "reviewing a finding", "submit_challenge": "challenging a claim", "submission": "checking its submissions",
    "search_terms": "looking up symptom terms", "request_condition": "requesting work on a condition",
    "fetch_page": "archiving an organization page",
    "calibration_case": "qualifying as a reviewer", "submit_calibration": "qualifying as a reviewer",
}


def display(profile):
    """Public name: the contributor's chosen label, else its slug."""
    return profile.get("display") or profile["id"].removeprefix("agent:mcp-").removeprefix("agent:")


def task_condition(task_id):
    """Evidence tasks carry their condition in the ID; other tasks resolve through the store."""
    if isinstance(task_id, str) and task_id.startswith("evidence:"):
        return task_id.split(":", 1)[1]
    return None


class Presence:
    """Wraps a per-request atlas; records which agent is working where, then delegates."""
    ARG = {"condition": 0, "frontier": 0, "request_condition": 0}
    TASK_ARG = {"claim_task", "fetch_source", "submit_claim", "submit_review", "submit_challenge", "fetch_page"}
    _last: dict = {}
    _lock = threading.Lock()

    def __init__(self, atlas, store, actor):
        self._atlas, self._store, self._actor = atlas, store, actor

    def __getattr__(self, name):
        value = getattr(self._atlas, name)
        if name not in DOING or not callable(value):
            return value
        def call(*args, **kwargs):
            condition = None
            if name in self.ARG and args:
                condition = args[self.ARG[name]]
            elif name in self.TASK_ARG and args:
                condition = task_condition(args[0])
                if not condition:
                    task = self._store.get("task", args[0]) if isinstance(args[0], str) else None
                    condition = task and task.get("condition_id")
            try:
                self.touch(name, condition if isinstance(condition, str) else None)
            except Exception:
                pass  # presence is best effort and must never block contribution
            return value(*args, **kwargs)
        return call

    def touch(self, tool, condition):
        now = time.time()
        with self._lock:
            last = self._last.get(self._actor)
            condition = condition or (last or {}).get("condition_id")
            if last and last["tool"] == tool and last["condition_id"] == condition and now - last["at"] < 10:
                return
            self._last[self._actor] = {"tool": tool, "condition_id": condition, "at": now}
        profile = self._store.get("profile", self._actor) or {"id": self._actor}
        row = {"actor": self._actor, "name": display(profile), "family": profile.get("model_family"),
               "model": profile.get("model"), "tool": tool, "doing": DOING[tool], "condition_id": condition, "at": now}
        self._store.table.upsert_entity(self._store.entity("presence", self._actor, row))


class Feed:
    """Cached public feed. One instance per process; refreshed at most every few seconds."""
    def __init__(self, store, ttl=3.0):
        self.store, self.ttl = store, ttl
        self.lock = threading.Lock()
        self.events, self.max_seq, self.loaded = [], 0, 0.0
        self.cached, self.cached_at = None, 0.0

    def _activity(self):
        if not self.events:
            rows = self.store.rows("activity")
        else:
            rows = [json.loads(r["body"]) for r in self.store.table.query_entities(
                "PartitionKey eq @p and kind eq @k and seq gt @s",
                parameters={"p": self.store.PARTITION, "k": "activity", "s": self.max_seq})]
        rows = sorted((r for r in rows if r["seq"] > self.max_seq), key=lambda r: r["seq"])
        if rows:
            self.events = (self.events + rows)[-400:]
            self.max_seq = self.events[-1]["seq"]

    def _names(self):
        return {p["id"]: p for p in self.store.rows("profile")}

    def _overlay(self):
        try:
            return json.loads(self.store.container.download_blob("live/current.json").readall())
        except ResourceNotFoundError:
            return None

    def _engine(self):
        try:
            beat = json.loads(self.store.container.download_blob("live/engine.json").readall())
        except ResourceNotFoundError:
            return None
        return {"online": time.time() - beat.get("at", 0) < 300, "at": beat.get("at"), "host": beat.get("host")}

    def snapshot(self):
        with self.lock:
            if self.cached is None or time.time() - self.cached_at > self.ttl:
                self._activity()
                profiles = self._names()
                now = time.time()
                presence = [{k: p.get(k) for k in ("name", "family", "model", "doing", "condition_id", "at")}
                            for p in self.store.rows("presence") if now - p["at"] < PRESENCE_TTL]
                events = []
                for e in self.events[-FEED_EVENTS:]:
                    prof = profiles.get(e.get("actor"), {"id": e.get("actor") or "atlas"})
                    events.append({"seq": e["seq"], "at": e["at"], "agent": display(prof), "family": prof.get("model_family"),
                                   "stage": e["stage"], "condition_id": e.get("condition_id"), "detail": e.get("detail")})
                self.cached = {"now": now, "events": events, "presence": sorted(presence, key=lambda p: -p["at"]),
                               "overlay": self._overlay(), "engine": self._engine(),
                               "notice": "Activity is operational status, not evidence."}
                self.cached_at = time.time()
            return self.cached

    def since(self, after):
        snap = self.snapshot()
        return {**snap, "events": [e for e in snap["events"] if e["seq"] > after]}

    def frontier(self):
        """Public subset of the engine's impact frontier: what needs work most, and why."""
        try:
            body = json.loads(self.store.container.download_blob("live/evidence-frontier.json").readall())
        except ResourceNotFoundError:
            return {"at": None, "conditions": []}
        return {"at": body["at"], "conditions": [{k: r[k] for k in ("condition_id", "name", "gene", "why", "focus", "requests")}
                                                 for r in body["conditions"][:60]]}

    def contributors(self):
        try:
            return json.loads(self.store.container.download_blob("live/contributors.json").readall())
        except ResourceNotFoundError:
            return {"at": None, "contributors": []}

    def history(self):
        try:
            return self.store.container.download_blob("live/history.json").readall()
        except ResourceNotFoundError:
            return b'{"at": null, "findings": [], "connections": []}'

    def salt(self):
        """Server-side secret for hashing visitors; created once, never leaves storage."""
        if not getattr(self, "_salt", None):
            import secrets
            def decide(seq):
                row = self.store.get("secret", "request-salt")
                return (row, []) if row else ({"salt": secrets.token_hex(16)}, [("secret", "request-salt", {"salt": secrets.token_hex(16)})])
            self.store.atomic(decide)
            self._salt = self.store.get("secret", "request-salt")["salt"]
        return self._salt

    def request(self, condition_id, client):
        import hashlib
        from .cloud_store import CloudIntake
        visitor = hashlib.sha256(f"{self.salt()}|{client}".encode()).hexdigest()[:16]
        return CloudIntake(self.store).request_condition(condition_id, visitor)

    def request_count(self, condition_id):
        from .cloud_store import CloudIntake
        return CloudIntake(self.store).request_count(condition_id)

    def variants_file(self, symbol):
        """Per-gene ClinVar summary written by pipeline/variants.py (public data)."""
        if not GENE_SYMBOL.fullmatch(symbol):
            return None
        try:
            return self.store.container.download_blob(f"variants/{symbol}.json").readall()
        except ResourceNotFoundError:
            return None

    def overlay_file(self, path):
        if not OVERLAY_PATH.fullmatch(path):
            return None
        try:
            return self.store.container.download_blob("live/v/" + path).readall()
        except ResourceNotFoundError:
            return None


def add_routes(mcp, feed):
    """Public GET routes on the MCP host. CORS is open: the data is public and read-only."""
    from starlette.responses import JSONResponse, Response

    headers = {"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"}

    @mcp.custom_route("/live/feed", methods=["GET"])
    async def live_feed(request):
        import anyio
        try:
            after = max(0, int(request.query_params.get("after", "0")))
        except ValueError:
            after = 0
        body = await anyio.to_thread.run_sync(feed.since, after)
        return JSONResponse(body, headers=headers)

    @mcp.custom_route("/live/data/{path:path}", methods=["GET"])
    async def live_data(request):
        import anyio
        raw = await anyio.to_thread.run_sync(feed.overlay_file, request.path_params["path"])
        if raw is None:
            return Response("Not found", status_code=404, headers=headers)
        return Response(raw, media_type="application/json",
                        headers={**headers, "Cache-Control": "public, max-age=31536000, immutable"})

    @mcp.custom_route("/live/frontier", methods=["GET"])
    async def live_frontier(request):
        import anyio
        body = await anyio.to_thread.run_sync(feed.frontier)
        return JSONResponse(body, headers={**headers, "Cache-Control": "public, max-age=120"})

    @mcp.custom_route("/live/contributors", methods=["GET"])
    async def live_contributors(request):
        import anyio
        body = await anyio.to_thread.run_sync(feed.contributors)
        return JSONResponse(body, headers={**headers, "Cache-Control": "public, max-age=120"})

    @mcp.custom_route("/live/history", methods=["GET"])
    async def live_history(request):
        import anyio
        raw = await anyio.to_thread.run_sync(feed.history)
        return Response(raw, media_type="application/json", headers={**headers, "Cache-Control": "public, max-age=300"})

    @mcp.custom_route("/live/request/{condition_id}", methods=["GET"])
    async def request_count(request):
        import anyio
        cid = request.path_params["condition_id"]
        if not CONDITION_ID.fullmatch(cid):
            return JSONResponse({"error": "Unknown condition"}, status_code=400, headers=headers)
        count = await anyio.to_thread.run_sync(feed.request_count, cid)
        return JSONResponse({"condition_id": cid, "requests": count}, headers=headers)

    @mcp.custom_route("/live/request", methods=["POST"])
    async def request_condition(request):
        """Anonymous "work on this next". Sent as text/plain JSON so browsers need no CORS preflight."""
        import anyio
        try:
            cid = json.loads((await request.body())[:500])["condition_id"]
        except (ValueError, KeyError, TypeError):
            cid = None
        if not isinstance(cid, str) or not CONDITION_ID.fullmatch(cid):
            return JSONResponse({"error": "Unknown condition"}, status_code=400, headers=headers)
        client = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
        try:
            result = await anyio.to_thread.run_sync(feed.request, cid, client)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=429, headers=headers)
        return JSONResponse({"condition_id": cid, "requests": result["count"], "counted": result["new"]}, headers=headers)

    @mcp.custom_route("/variants/{symbol}", methods=["GET"])
    async def variants(request):
        import anyio
        raw = await anyio.to_thread.run_sync(feed.variants_file, request.path_params["symbol"])
        if raw is None:
            return Response("Not found", status_code=404, headers=headers)
        return Response(raw, media_type="application/json", headers={**headers, "Cache-Control": "public, max-age=3600"})
