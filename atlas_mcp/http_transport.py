"""Stateless authenticated MCP transport; no shared mutable current-contributor state.

Entra v2 access tokens are verified for a fixed tenant, audience, expiry and
scope. An operator binds issuer + object ID to a contributor. A token cannot
choose a model, family, reviewer role, storage path or signing key.
"""
import re
from urllib.parse import urlsplit

import anyio
import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings

from .server import build_server


class EntraVerifier:
    def __init__(self, tenant, audience, resolve_principal, scope="Atlas.Contribute", signing_keys=None):
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", tenant) or not audience or not scope:
            raise ValueError("A fixed tenant UUID, API audience and permission are required")
        self.tenant, self.audience, self.scope = tenant, audience, scope
        self.issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
        self.resolve_principal = resolve_principal
        # Never use token-supplied URLs or accept arbitrary issuers/algorithms.
        self.signing_keys = signing_keys or jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys", cache_jwk_set=True, lifespan=300, timeout=10)

    def verify(self, token):
        key = self.signing_keys.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer,
                            options={"require": ["exp", "iat", "nbf", "iss", "aud", "tid", "oid"]})
        if claims["tid"] != self.tenant or not re.fullmatch(r"[0-9a-fA-F-]{36}", claims["oid"]):
            return None
        # Delegated OAuth scope, or an explicitly assigned application permission.
        permissions = claims.get("scp", "").split()
        if self.scope not in permissions and self.scope+".AsAgent" not in claims.get("roles", []):
            return None
        principal = self.issuer + "|" + claims["oid"]
        actor = self.resolve_principal(principal)
        return AccessToken(token=token, client_id=actor, scopes=[self.scope], expires_at=int(claims["exp"]), subject=principal)

    async def verify_token(self, token):
        if len(token) > 16000:
            return None
        try:
            return await anyio.to_thread.run_sync(self.verify, token)
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            return None


class RequestAtlas:
    """Resolve identity inside each tool's request context, including threadpool calls."""
    def __init__(self, factory):
        self.factory = factory

    def __getattr__(self, name):
        token = get_access_token()
        if token is None:
            raise ValueError("An authenticated enrolled contributor is required")
        return getattr(self.factory(token.client_id), name)


def build_http_server(factory, verifier, public_url):
    url = urlsplit(public_url)
    if url.scheme != "https" or not url.hostname or url.path != "/mcp" or url.query or url.fragment or url.username:
        raise ValueError("Use the canonical HTTPS /mcp endpoint")
    origin = f"https://{url.netloc}"
    return build_server(RequestAtlas(factory), stateless_http=True, json_response=True,
        max_request_body_size=65536, host="0.0.0.0", token_verifier=verifier,
        auth=AuthSettings(issuer_url=verifier.issuer, resource_server_url=public_url,
                          required_scopes=[verifier.scope], validate_token_resource=False),
        # Audience is checked by EntraVerifier, since Entra uses the API application
        # audience rather than the HTTP resource URL as its access-token aud.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
            allowed_hosts=[url.netloc], allowed_origins=[origin]))
