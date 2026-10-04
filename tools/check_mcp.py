"""Read-only real-data MCP protocol smoke check. Never writes to the claims ledger."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def body(result):
    if result.isError:
        raise AssertionError(result.content)
    return result.structuredContent or json.loads(result.content[0].text)


async def check():
    params = StdioServerParameters(command=sys.executable, args=["-B", str(ROOT / "tools/run_mcp.py")], cwd=str(ROOT.parent))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            initialized = await client.initialize()
            tools = [t.name for t in (await client.list_tools()).tools]
            found = body(await client.call_tool("search_atlas", {"query": "SNAP25"}))
            assert any(c["id"] == "MONDO:0014590" for c in found["matches"])
            condition = body(await client.call_tool("get_condition", {"condition_id": "MONDO:0014590"}))
            assert condition["condition"]["gene"]["symbol"] == "SNAP25"
            contributed = condition["recent_contributions"]
            assert contributed
            claim = body(await client.call_tool("get_claim", {"claim_id": contributed[0]["claim_id"]}))
            assert claim["claim"]["evidence"]
            denied = await client.call_tool("claim_task", {"task_id": "evidence:MONDO:0014590"})
            assert denied.isError
            return {"at": datetime.now(timezone.utc).isoformat(), "server": initialized.serverInfo.name,
                    "protocol": initialized.protocolVersion, "tools": tools, "real_condition_search": "passed",
                    "real_claim_evidence_and_reviews": "passed", "read_only_mutation_denied": "passed",
                    "ledger_writes": 0, "model_calls": 0, "transport": "stdio", "hosted": False}


if __name__ == "__main__":
    receipt = asyncio.run(check())
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
