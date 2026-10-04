"""Prepare and submit two full-eligibility claims through the hosted MCP.

Read the inspect output before submitting. No model calls and no ledger writes.
The separate bounded operator cycle handles verification and publication.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from atlas_mcp.cycle import atomic_json
from tools.azure_mcp_operator import Operator

STATE = ROOT / "data/contributions/shared-study-proposal.json"
CONDITIONS = ["MONDO:0012812", "MONDO:0012960"]
RECORD = "NCT06555965"


def evidence_for(source):
    text = source["text"]
    def section(start, stop):
        return text[text.index(start):text.index(stop)].rstrip()
    eligibility = section("Eligibility:", "\nInterventions:")
    if not all(label in eligibility for label in ("Minimum age:", "Maximum age:", "Sex:", "Healthy volunteers:")):
        raise ValueError("Deploy the complete eligibility renderer before proposing")
    quotes = [section("Title:", "\nKeywords:"), section("Summary:", "\nStudy type:"),
              eligibility, section("Primary outcomes:", "\nStatus:"), section("Status:", "\nWhy stopped:")]
    return [{"type": "trial_record", "source_id": source["source_id"], "quote": q,
             "start": text.index(q), "end": text.index(q) + len(q),
             **({"restriction": eligibility} if q == eligibility else {})} for q in quotes]


async def main(command):
    operator = Operator()
    url = 'https://' + operator.host() + '/mcp'
    token = operator.credential.get_token('api://' + operator.config['apiAudience'] + '/.default').token
    async with httpx.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=60) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                async def call(name, args):
                    result = await session.call_tool(name, args)
                    if result.isError:
                        raise ValueError(f"MCP {name} rejected the request")
                    return json.loads(result.content[0].text)
                receipt = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"submissions": {}}
                if command == "inspect":
                    task = "evidence:" + CONDITIONS[0]
                    await call("list_frontier", {"condition_id": CONDITIONS[0]})
                    await call("claim_task", {"task_id": task})
                    fetched = await call("fetch_source", {"task_id": task, "provider": "clinicaltrials", "record_id": RECORD})
                    source = await call("get_source", {"source_id": fetched["source_id"], "limit": 20000})
                    if source["next_offset"] is not None:
                        raise ValueError("Read the entire record before proposing")
                    source["source_id"] = fetched["source_id"]
                    evidence_for(source)
                    receipt["source"] = source
                    atomic_json(STATE, receipt)
                    print(source["text"])
                    return
                source = receipt["source"]
                ev = evidence_for(source)
                status = next(line.removeprefix("Status: ") for line in source["text"].splitlines() if line.startswith("Status: "))
                for cid in CONDITIONS:
                    if cid in receipt["submissions"]:
                        continue
                    task = "evidence:" + cid
                    await call("list_frontier", {"condition_id": cid})
                    await call("claim_task", {"task_id": task})
                    result = await call("submit_claim", {"task_id": task,
                        "assertion": {"subject": cid, "predicate": "has_asset", "object": RECORD,
                                      "qualifiers": {"asset_type": "natural_history_study", "status": status}},
                        "evidence": ev, "prompt": "complete-shared-study-eligibility@1"})
                    if not result.get("submission_id"):
                        raise ValueError("MCP did not accept a queued submission")
                    receipt["submissions"][cid] = result
                    atomic_json(STATE, receipt)
                print(json.dumps({"record": RECORD, "submissions": receipt["submissions"], "model_calls": 0}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "submit"))
    asyncio.run(main(parser.parse_args().command))
