import asyncio
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from atlas_mcp.http_transport import EntraVerifier, build_http_server
from atlas_mcp.service import Atlas
from atlas_mcp.tests.test_contribution_loop import setup, TestRegistry, CID

TENANT = "11111111-2222-3333-4444-555555555555"
OID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee"
AUDIENCE = "atlas-test-api"


@pytest.fixture
def credentials(setup):
    atlas, *_ = setup
    other = atlas.intake.enroll("other-http", "other-model", "other-family")["id"]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    mapping = {OID: atlas.actor, OTHER: other}
    def resolve(principal):
        actor = mapping[principal.split("|")[1]]
        atlas.intake.profile(actor)
        return actor
    verifier = EntraVerifier(TENANT, AUDIENCE, resolve, signing_keys=keys)
    def token(**overrides):
        claims = {"iss": verifier.issuer, "aud": AUDIENCE, "tid": TENANT, "oid": OID,
                  "exp": int(time.time())+300, "nbf": int(time.time())-1, "iat": int(time.time())-1,
                  "scp": "Atlas.Contribute", **overrides}
        return jwt.encode(claims, key, algorithm="RS256")
    return atlas, other, verifier, token


def test_token_rejects_wrong_audience_issuer_expiry_scope_and_unenrolled(credentials):
    atlas, _, verifier, token = credentials
    async def run():
        assert (await verifier.verify_token(token())).client_id == atlas.actor
        assert (await verifier.verify_token(token(scp="", roles=["Atlas.Contribute.AsAgent"]))).client_id == atlas.actor
        for changes in ({"aud": "another-api"}, {"iss": "https://attacker.test"}, {"exp": 1},
                        {"scp": "read"}, {"oid": "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"}, {"tid": OTHER}):
            assert await verifier.verify_token(token(**changes)) is None
        assert await verifier.verify_token("not-a-token") is None
    asyncio.run(run())


def test_real_http_mcp_requires_auth_and_isolates_concurrent_callers(credentials):
    atlas, other, verifier, token = credentials
    factory = lambda actor: Atlas(atlas.intake.root, atlas.ledger_path, atlas.data_root, actor, TestRegistry())
    server = build_http_server(factory, verifier, "https://atlas.test/mcp")
    app = server.streamable_http_app()
    async def run():
        async with server.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://atlas.test") as unauth:
                assert (await unauth.post("/mcp", json={})).status_code == 401
                metadata = await unauth.get("/.well-known/oauth-protected-resource/mcp")
                assert metadata.status_code == 200
                assert metadata.json()["resource"] == "https://atlas.test/mcp"
            async def call(oid):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app), headers={"Authorization": "Bearer "+token(oid=oid)}) as client:
                    async with streamable_http_client("https://atlas.test/mcp", http_client=client) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            listing = await session.list_tools()
                            assert len(listing.tools) == 13
                            result = await session.call_tool("claim_task", {"task_id": "evidence:"+CID})
                            return result
            first, second = await asyncio.gather(call(OID), call(OTHER))
            assert not first.isError
            assert second.isError
            assert "another contributor" in second.content[0].text
            assert atlas.intake.owned_task("evidence:"+CID, atlas.actor)["actor"] == atlas.actor
    asyncio.run(run())
