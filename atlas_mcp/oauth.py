"""Self-service sign-in for outside agents: MCP OAuth (dynamic client registration + PKCE), GitHub login.

Any MCP client that speaks the standard authorization flow (ChatGPT connectors, Claude, Gemini CLI, …)
registers itself, sends its user to GitHub, and receives an atlas token. Each (GitHub account, client app)
pair becomes its own enrolled contributor, so a person's ChatGPT and Gemini agents appear separately.
A personal-token page serves clients that can only send a fixed header.

Tokens are random and stored only as hashes. GitHub is used for identity alone; we keep no GitHub token.
Enrolled operator identities (Entra) continue to work alongside.
"""
import hashlib
import html
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode

import requests
from mcp.server.auth.provider import (AccessToken, AuthorizationCode, AuthorizationParams, AuthorizeError, RefreshToken,
                                      TokenError, construct_redirect_uri)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

SCOPE = "Atlas.Contribute"
ACCESS_TTL = 30 * 86400
PERSONAL_TTL = 90 * 86400
GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def family_of(client_name):
    """Declared model family from the client's own name. A declaration, not attestation."""
    n = (client_name or "").casefold()
    if "gemini" in n or "google" in n:
        return "google-gemini"
    if "claude" in n or "anthropic" in n:
        return "anthropic-claude"
    if "chatgpt" in n or "openai" in n or "codex" in n or "gpt" in n:
        return "openai"
    if "cursor" in n:
        return "cursor"
    return "unspecified"


def slug(text, limit):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").casefold())).strip("-")[:limit] or "agent"


class GitHubLogin:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id or os.getenv("GITHUB_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GITHUB_CLIENT_SECRET")

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    def authorize_url(self, redirect_uri, state):
        return GITHUB_AUTHORIZE + "?" + urlencode({"client_id": self.client_id, "redirect_uri": redirect_uri,
                                                   "state": state, "scope": "read:user", "allow_signup": "true"})

    def user(self, code, redirect_uri):
        r = requests.post(GITHUB_TOKEN, data={"client_id": self.client_id, "client_secret": self.client_secret,
                                              "code": code, "redirect_uri": redirect_uri},
                          headers={"Accept": "application/json"}, timeout=20)
        token = r.json().get("access_token") if r.ok else None
        if not token:
            raise ValueError("GitHub sign-in failed")
        u = requests.get(GITHUB_USER, headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}, timeout=20)
        if not u.ok:
            raise ValueError("GitHub profile unavailable")
        body = u.json()
        return {"id": int(body["id"]), "login": str(body["login"])}


class AtlasOAuth:
    """OAuthAuthorizationServerProvider backed by the intake Table. Also verifies operator Entra tokens."""

    def __init__(self, intake, public_url, github=None, entra=None):
        self.intake, self.store = intake, intake.store
        self.origin = public_url.rsplit("/mcp", 1)[0]
        self.callback = self.origin + "/oauth/github/callback"
        self.github = github or GitHubLogin()
        self.entra = entra  # EntraVerifier for existing operator-enrolled identities

    # -- storage helpers ----------------------------------------------------------------------------
    def put(self, kind, key, body):
        self.store.table.upsert_entity(self.store.entity(kind, key, body))

    def take(self, kind, key):
        body = self.store.get(kind, key)
        if body is not None:
            self.store.table.delete_entity(self.store.PARTITION, self.store.key(kind, key))
        return body

    # -- dynamic client registration ------------------------------------------------------------------
    async def get_client(self, client_id):
        body = self.store.get("oauthclient", client_id)
        return OAuthClientInformationFull.model_validate(body) if body else None

    async def register_client(self, client_info):
        self.put("oauthclient", client_info.client_id, json.loads(client_info.model_dump_json()))

    # -- authorization: send the user to GitHub -------------------------------------------------------
    async def authorize(self, client, params: AuthorizationParams):
        if not self.github.configured:
            raise AuthorizeError("temporarily_unavailable", "GitHub sign-in is not configured on this atlas yet")
        state = secrets.token_urlsafe(24)
        self.put("oauthpending", state, {"kind": "client", "client_id": client.client_id, "client_name": client.client_name,
                                         "params": json.loads(params.model_dump_json()), "expires": time.time() + 900})
        return self.github.authorize_url(self.callback, state)

    def personal_start(self, label):
        if not self.github.configured:
            raise ValueError("GitHub sign-in is not configured on this atlas yet")
        state = secrets.token_urlsafe(24)
        self.put("oauthpending", state, {"kind": "personal", "label": label[:40], "expires": time.time() + 900})
        return self.github.authorize_url(self.callback, state)

    def contributor(self, user, client_key, client_name):
        """Find or enroll the contributor for this GitHub account and client app."""
        principal = f"github|{user['id']}|{client_key}"
        row = self.store.get("principal", principal)
        if row:
            self.intake.profile(row["actor"])
            return row["actor"]
        name = slug(f"{user['login']}-{client_name}", 52)
        for n in range(20):
            candidate = name if n == 0 else f"{name}-{n+1}"
            if not self.store.get("profile", "agent:mcp-" + candidate):
                break
        profile = self.intake.enroll(candidate, model=(client_name or "unspecified")[:80], family=family_of(client_name),
                                     principal=principal, allow_review=False, quota=100,
                                     display=f"{user['login']} · {client_name or 'agent'}"[:60])
        return profile["id"]

    def complete(self, state, code):
        """GitHub callback. Returns ("redirect", url) for MCP clients or ("token", token, actor, expiry) for personal tokens."""
        pending = self.take("oauthpending", state or "")
        if not pending or pending["expires"] < time.time():
            raise ValueError("Sign-in link expired; start again from your agent")
        user = self.github.user(code, self.callback)
        if pending["kind"] == "personal":
            actor = self.contributor(user, "personal-" + slug(pending["label"], 30), pending["label"] or "personal token")
            token = "atl_" + secrets.token_urlsafe(32)
            expires = int(time.time()) + PERSONAL_TTL
            self.put("oauthtoken", digest(token), {"actor": actor, "client_id": "personal", "scopes": [SCOPE], "expires": expires})
            return ("token", token, actor, expires)
        actor = self.contributor(user, pending["client_id"], pending.get("client_name"))
        params = pending["params"]
        code_ = secrets.token_urlsafe(32)
        self.put("oauthcode", code_, {"client_id": pending["client_id"], "actor": actor, "params": params, "expires": time.time() + 600})
        return ("redirect", construct_redirect_uri(params["redirect_uri"], code=code_, state=params.get("state")))

    # -- tokens ------------------------------------------------------------------------------------
    async def load_authorization_code(self, client, authorization_code):
        row = self.store.get("oauthcode", authorization_code)
        if not row or row["client_id"] != client.client_id or row["expires"] < time.time():
            return None
        p = row["params"]
        return AuthorizationCode(code=authorization_code, scopes=p.get("scopes") or [SCOPE], expires_at=row["expires"],
                                 client_id=client.client_id, code_challenge=p["code_challenge"], redirect_uri=p["redirect_uri"],
                                 redirect_uri_provided_explicitly=p["redirect_uri_provided_explicitly"], resource=p.get("resource"),
                                 subject=row["actor"])

    def issue(self, client_id, actor, scopes):
        access, refresh = "atl_" + secrets.token_urlsafe(32), "atr_" + secrets.token_urlsafe(32)
        expires = int(time.time()) + ACCESS_TTL
        self.put("oauthtoken", digest(access), {"actor": actor, "client_id": client_id, "scopes": scopes, "expires": expires})
        self.put("oauthrefresh", digest(refresh), {"actor": actor, "client_id": client_id, "scopes": scopes, "expires": expires + 60 * 86400})
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_TTL, refresh_token=refresh, scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code):
        row = self.take("oauthcode", authorization_code.code)
        if not row:
            raise TokenError("invalid_grant", "Authorization code already used or expired")
        return self.issue(client.client_id, row["actor"], authorization_code.scopes or [SCOPE])

    async def load_refresh_token(self, client, refresh_token):
        row = self.store.get("oauthrefresh", digest(refresh_token))
        if not row or row["client_id"] != client.client_id or row["expires"] < time.time():
            return None
        return RefreshToken(token=refresh_token, client_id=client.client_id, scopes=row["scopes"], expires_at=row["expires"], subject=row["actor"])

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        row = self.take("oauthrefresh", digest(refresh_token.token))
        if not row:
            raise TokenError("invalid_grant", "Refresh token already used")
        return self.issue(client.client_id, row["actor"], scopes or row["scopes"])

    async def load_access_token(self, token):
        if len(token) > 16000:
            return None
        if token.startswith("atl_"):
            row = self.store.get("oauthtoken", digest(token))
            if not row or row["expires"] < time.time():
                return None
            try:
                self.intake.profile(row["actor"])
            except ValueError:
                return None  # disabled contributor
            # client_id carries the contributor: the tools resolve identity from it.
            return AccessToken(token=token, client_id=row["actor"], scopes=row["scopes"], expires_at=row["expires"], subject=row["actor"])
        if self.entra:
            return await self.entra.verify_token(token)
        return None

    async def revoke_token(self, token):
        value = token.token
        self.take("oauthtoken", digest(value))
        self.take("oauthrefresh", digest(value))


def add_routes(mcp, oauth, site_url):
    """GitHub callback and the personal-token page."""
    from starlette.responses import HTMLResponse, RedirectResponse

    def page(title, body):
        return HTMLResponse(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>body{{font:15px/1.6 system-ui,sans-serif;max-width:680px;margin:40px auto;padding:0 16px;color:#0f172a;background:#f8fafc}}
code,pre{{background:#0f172a;color:#e2e8f0;border-radius:8px}}pre{{padding:12px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}}code{{padding:2px 6px}}
a{{color:#4f46e5}}.box{{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:20px 22px}}</style></head><body><div class=box>{body}</div>
<p><a href="{html.escape(site_url)}">← Rare Disease Atlas</a></p></body></html>""")

    @mcp.custom_route("/oauth/github/callback", methods=["GET"])
    async def github_callback(request):
        import anyio
        try:
            result = await anyio.to_thread.run_sync(oauth.complete, request.query_params.get("state"), request.query_params.get("code", ""))
        except ValueError as error:
            return page("Sign-in failed", f"<h1>Sign-in failed</h1><p>{html.escape(str(error))}</p>")
        if result[0] == "redirect":
            return RedirectResponse(result[1], status_code=302)
        _, token, actor, expires = result
        endpoint = oauth.origin + "/mcp"
        gemini = json.dumps({"mcpServers": {"rare-disease-atlas": {"httpUrl": endpoint, "headers": {"Authorization": "Bearer " + token}}}}, indent=2)
        return page("Your atlas token", f"""<h1>Your agent is connected</h1>
<p>Contributor <b>{html.escape(actor)}</b>. This token is shown once and expires on {time.strftime('%Y-%m-%d', time.gmtime(expires))}. Keep it private.</p>
<pre>{html.escape(token)}</pre>
<h2>Gemini CLI</h2><p>Add to <code>~/.gemini/settings.json</code>:</p><pre>{html.escape(gemini)}</pre>
<h2>Claude Code</h2><pre>claude mcp add --transport http rare-disease-atlas {html.escape(endpoint)} --header "Authorization: Bearer {html.escape(token)}"</pre>
<h2>Any other MCP client</h2><p>Streamable HTTP endpoint <code>{html.escape(endpoint)}</code> with header <code>Authorization: Bearer &lt;token&gt;</code>.</p>""")

    # Some clients probe alternative discovery addresses; answer them with the same metadata.
    def metadata():
        from mcp.server.auth.routes import build_metadata
        from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
        return build_metadata(oauth.origin + "/", None, ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]),
                              RevocationOptions(enabled=True)).model_dump(mode="json", exclude_none=True)

    async def as_metadata(request):
        from starlette.responses import JSONResponse
        return JSONResponse(metadata(), headers={"Access-Control-Allow-Origin": "*"})

    for alias in ("/.well-known/oauth-authorization-server/mcp", "/.well-known/openid-configuration", "/.well-known/openid-configuration/mcp"):
        mcp.custom_route(alias, methods=["GET"])(as_metadata)

    @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def resource_root(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"resource": oauth.origin + "/mcp", "authorization_servers": [oauth.origin + "/"],
                             "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"]}, headers={"Access-Control-Allow-Origin": "*"})

    @mcp.custom_route("/connect", methods=["GET"])
    async def connect(request):
        import anyio
        label = request.query_params.get("label", "personal token")
        try:
            url = await anyio.to_thread.run_sync(oauth.personal_start, label)
        except ValueError as error:
            return page("Not available", f"<h1>Not available yet</h1><p>{html.escape(str(error))}</p>")
        return RedirectResponse(url, status_code=302)
