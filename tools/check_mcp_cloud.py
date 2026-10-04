"""Read-only live protocol/auth smoke; access tokens are never printed or saved."""
import asyncio
import json
import sys
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.azure_mcp_operator import Operator


async def main():
    operator = Operator()
    url = 'https://' + operator.host() + '/mcp'
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, json={})
        assert response.status_code == 401, response.status_code
        metadata = await client.get(url.replace('/mcp', '/.well-known/oauth-protected-resource/mcp'))
        assert metadata.status_code == 200 and metadata.json()['resource'] == url
    token = operator.credential.get_token('api://' + operator.config['apiAudience'] + '/.default').token
    async with httpx.AsyncClient(headers={'Authorization': 'Bearer ' + token}, timeout=45) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 13
                result = await session.call_tool('search_atlas', {'query': 'SNAP25'})
                assert not result.isError, result.content
                search = json.loads(result.content[0].text)
                assert any(m['id'] == 'MONDO:0014590' for m in search['matches'])
                result = await session.call_tool('get_condition', {'condition_id': 'MONDO:0014590'})
                assert not result.isError
    receipt = {'endpoint': url, 'unauthenticated_http': 401, 'metadata': 'passed', 'authenticated_initialization': 'passed',
               'tool_count': len(tools.tools), 'snap25_search_and_read': 'passed', 'writes': 0}
    (ROOT/'data/campaigns/mcp-cloud-read-smoke.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
