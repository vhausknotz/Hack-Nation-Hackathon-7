"""Self-service sign-in: dynamic client registration, GitHub identity, PKCE code exchange, token use."""
import asyncio
import os
import time

import pytest
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from atlas_mcp.oauth import AtlasOAuth, family_of
from atlas_mcp.tests.test_cloud_store import cloud  # noqa: F401

pytestmark = pytest.mark.skipif(os.getenv("ATLAS_TEST_AZURITE") != "1", reason="Local Azurite integration is opt-in")


class FakeGitHub:
    configured = True

    def authorize_url(self, redirect_uri, state):
        return f"https://github.example/authorize?state={state}"

    def user(self, code, redirect_uri):
        assert code == "gh-code"
        return {"id": 42, "login": "Valentin"}


def run(coro):
    return asyncio.run(coro)


def test_family_from_client_name():
    assert family_of("ChatGPT") == "openai" and family_of("Gemini CLI") == "google-gemini"
    assert family_of("Claude Code") == "anthropic-claude" and family_of(None) == "unspecified"


def test_client_signs_in_and_gets_its_own_contributor(cloud):  # noqa: F811
    oauth = AtlasOAuth(cloud, "https://atlas.example/mcp", github=FakeGitHub())
    client = OAuthClientInformationFull(client_id="c1", client_name="ChatGPT", redirect_uris=["https://chatgpt.example/cb"],
                                        token_endpoint_auth_method="none", grant_types=["authorization_code", "refresh_token"],
                                        response_types=["code"], scope="Atlas.Contribute")
    run(oauth.register_client(client))
    assert run(oauth.get_client("c1")).client_name == "ChatGPT"
    params = AuthorizationParams(state="s1", scopes=["Atlas.Contribute"], code_challenge="x" * 43,
                                 redirect_uri="https://chatgpt.example/cb", redirect_uri_provided_explicitly=True)
    url = run(oauth.authorize(client, params))
    state = url.split("state=")[1]
    kind, redirect = oauth.complete(state, "gh-code")
    assert kind == "redirect" and redirect.startswith("https://chatgpt.example/cb?") and "state=s1" in redirect
    code = redirect.split("code=")[1].split("&")[0]
    loaded = run(oauth.load_authorization_code(client, code))
    assert loaded.subject == "agent:mcp-valentin-chatgpt"
    token = run(oauth.exchange_authorization_code(client, loaded))
    with pytest.raises(Exception):
        run(oauth.exchange_authorization_code(client, loaded))  # codes are single use
    access = run(oauth.load_access_token(token.access_token))
    assert access.client_id == "agent:mcp-valentin-chatgpt"
    profile = cloud.profile(access.client_id)
    assert profile["model_family"] == "openai" and profile["display"] == "Valentin · ChatGPT" and not profile["allow_review"]
    # Refresh rotates the token; the old refresh token cannot be replayed.
    refresh = run(oauth.load_refresh_token(client, token.refresh_token))
    again = run(oauth.exchange_refresh_token(client, refresh, []))
    assert run(oauth.load_access_token(again.access_token)).client_id == access.client_id
    assert run(oauth.load_refresh_token(client, token.refresh_token)) is None
    # Same person, same client: same contributor. Expired or unknown links fail.
    url2 = run(oauth.authorize(client, params))
    kind, redirect2 = oauth.complete(url2.split("state=")[1], "gh-code")
    code2 = redirect2.split("code=")[1].split("&")[0]
    assert run(oauth.load_authorization_code(client, code2)).subject == access.client_id
    with pytest.raises(ValueError):
        oauth.complete("bogus", "gh-code")
    assert run(oauth.load_access_token("atl_unknown")) is None


def test_personal_token_for_header_clients(cloud):  # noqa: F811
    oauth = AtlasOAuth(cloud, "https://atlas.example/mcp", github=FakeGitHub())
    url = oauth.personal_start("Gemini CLI")
    kind, token, actor, expires = oauth.complete(url.split("state=")[1], "gh-code")
    assert kind == "token" and actor == "agent:mcp-valentin-gemini-cli" and expires > time.time()
    assert run(oauth.load_access_token(token)).client_id == actor
    assert cloud.profile(actor)["model_family"] == "google-gemini"


def test_http_discovery_and_registration(cloud):  # noqa: F811
    from starlette.testclient import TestClient
    from atlas_mcp.http_transport import EntraVerifier, build_http_server
    from atlas_mcp.oauth import add_routes
    verifier = EntraVerifier("00000000-0000-0000-0000-000000000000", "aud", lambda p: None, signing_keys=object())
    oauth = AtlasOAuth(cloud, "https://atlas.example/mcp", github=FakeGitHub(), entra=verifier)
    server = build_http_server(lambda actor: None, verifier, "https://atlas.example/mcp", oauth=oauth)
    add_routes(server, oauth, "https://site.example")
    with TestClient(server.streamable_http_app(), base_url="https://atlas.example") as http:
        meta = http.get("/.well-known/oauth-authorization-server").json()
        assert meta["registration_endpoint"] == "https://atlas.example/register"
        resource = http.get("/.well-known/oauth-protected-resource/mcp").json()
        assert resource["authorization_servers"] == ["https://atlas.example/"]
        reg = http.post("/register", json={"client_name": "Gemini CLI", "redirect_uris": ["http://localhost:7777/cb"],
                                           "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
                                           "response_types": ["code"]})
        assert reg.status_code == 201, reg.text
        cid = reg.json()["client_id"]
        r = http.get("/authorize", params={"client_id": cid, "response_type": "code", "redirect_uri": "http://localhost:7777/cb",
                                           "code_challenge": "x" * 43, "code_challenge_method": "S256", "state": "abc"},
                     follow_redirects=False)
        assert r.status_code == 302 and r.headers["location"].startswith("https://github.example/authorize")
        assert http.post("/mcp", json={}).status_code == 401
