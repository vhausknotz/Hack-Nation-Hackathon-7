"""End-to-end smoke test of the live loop through the hosted MCP, as the enrolled lead identity.

    ./.venv/Scripts/python tools/smoke_live_contribution.py MONDO:0800037 HP:0000407 40715324 "sensorineural hearing loss"

Claims a task, archives the PubMed abstract through MCP, finds the first sentence containing the phrase
and submits one has_symptom claim with that verbatim sentence. The engine then checks, reviews and publishes.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_cloud_mcp import ENDPOINT, EntraAuth  # noqa: E402


async def call(session, name, **args):
    result = await session.call_tool(name, args)
    text = result.content[0].text if result.content else "{}"
    if result.isError:
        raise RuntimeError(f"{name}: {text}")
    return json.loads(text)


async def main(condition, hpo, pmid, phrase):
    async with httpx.AsyncClient(auth=EntraAuth(), timeout=90) as client:
        async with streamable_http_client(ENDPOINT, http_client=client) as (read, write, _):
            async with ClientSession(read, write) as s:
                await s.initialize()
                task = f"evidence:{condition}"
                await call(s, "list_frontier", condition_id=condition, limit=5)
                await call(s, "claim_task", task_id=task)
                src = await call(s, "fetch_source", task_id=task, provider="pubmed", record_id=pmid)
                text = (await call(s, "get_source", source_id=src["source_id"]))["text"]
                sentence = next((m.group(0).strip() for m in re.finditer(r"[^.]*\.", text) if phrase.lower() in m.group(0).lower()), None)
                if not sentence:
                    raise SystemExit(f"Phrase not found in PMID {pmid}")
                print("quote:", sentence)
                receipt = await call(s, "submit_claim", task_id=task, prompt="smoke-live@1",
                                     assertion={"subject": condition, "predicate": "has_symptom", "object": hpo,
                                                "qualifiers": {"evidence_level": "clinical", "certainty": "asserted"}},
                                     evidence=[{"type": "publication_text", "source_id": src["source_id"], "quote": sentence, "pmid": pmid}])
                print(json.dumps(receipt, indent=1))


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:5]))
