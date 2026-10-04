"""Public routes for the family navigation assistant. The gateway only queues questions and returns answers;
the answering (a paid model call) happens on the engine VM under the owner's switch and hard caps (tools/assistant.py).

    GET  /assistant/status          {"enabled", "available"} from live/assistant.json
    POST /assistant/ask             text/plain JSON {"condition_id", "question"} -> {"id"}; 20 questions per visitor per day
    GET  /assistant/answer/{id}     {"state": queued | answered | unavailable | failed, "answer", "sections"}
"""
import hashlib
import json
import re
import secrets
import time

from azure.core.exceptions import ResourceNotFoundError

CONDITION_ID = re.compile(r"MONDO:\d{7}(-HGNC:\d{1,6})?")
QUESTION_ID = re.compile(r"q_[A-Za-z0-9_-]{16,40}")
PER_DAY = 20


def add_routes(mcp, feed):
    from starlette.responses import JSONResponse
    headers = {"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"}
    store = feed.store

    def status():
        try:
            body = json.loads(store.container.download_blob("live/assistant.json").readall())
        except ResourceNotFoundError:
            return {"enabled": False, "available": False}
        fresh = time.time() - body.get("at", 0) < 300  # the VM process is alive
        return {"enabled": bool(body.get("enabled")) and fresh, "available": bool(body.get("available")) and fresh}

    def ask(cid, question, client):
        if not status()["available"]:
            raise PermissionError("The assistant is not available right now")
        visitor = hashlib.sha256(f"{feed.salt()}|assistant|{client}".encode()).hexdigest()[:16]
        day = time.strftime("%Y-%m-%d", time.gmtime())
        qid = "q_" + secrets.token_urlsafe(18)

        def decide(seq):
            limit = store.get("asker", visitor) or {}
            limit = limit if limit.get("day") == day else {"day": day, "n": 0}
            if limit["n"] >= PER_DAY:
                raise ValueError("You've reached today's question limit")
            limit["n"] += 1
            return qid, [("asker", visitor, limit), ("question", qid, {"id": qid, "condition_id": cid, "question": question,
                                                                       "at": time.time(), "state": "queued"})]
        return store.atomic(decide)

    def answer(qid):
        row = store.get("question", qid)
        if not row:
            return None
        return {k: row.get(k) for k in ("state", "answer", "sections")}

    @mcp.custom_route("/assistant/status", methods=["GET"])
    async def assistant_status(request):
        import anyio
        return JSONResponse(await anyio.to_thread.run_sync(status), headers=headers)

    @mcp.custom_route("/assistant/ask", methods=["POST"])
    async def assistant_ask(request):
        import anyio
        try:
            body = json.loads((await request.body())[:2000])
            cid, question = body["condition_id"], " ".join(str(body["question"]).split())
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "Send a condition and a question"}, status_code=400, headers=headers)
        if not isinstance(cid, str) or not CONDITION_ID.fullmatch(cid) or not 3 <= len(question) <= 500:
            return JSONResponse({"error": "Ask a question of up to 500 characters about one condition"}, status_code=400, headers=headers)
        client = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
        try:
            qid = await anyio.to_thread.run_sync(ask, cid, question, client)
        except PermissionError as error:
            return JSONResponse({"error": str(error)}, status_code=503, headers=headers)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=429, headers=headers)
        return JSONResponse({"id": qid}, headers=headers)

    @mcp.custom_route("/assistant/answer/{qid}", methods=["GET"])
    async def assistant_answer(request):
        import anyio
        qid = request.path_params["qid"]
        if not QUESTION_ID.fullmatch(qid):
            return JSONResponse({"error": "Unknown question"}, status_code=404, headers=headers)
        row = await anyio.to_thread.run_sync(answer, qid)
        if row is None:
            return JSONResponse({"error": "Unknown question"}, status_code=404, headers=headers)
        return JSONResponse(row, headers=headers)
