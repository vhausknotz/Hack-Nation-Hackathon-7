"""Cloud gateway and explicit operator commands. Configuration is environment-only."""
import argparse
import json
import os
import threading
import time
from pathlib import Path

from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient

from .cloud_store import CloudStore, CloudIntake


def configured_store():
    table = os.getenv("ATLAS_TABLE", "atlasintake")
    container = os.getenv("ATLAS_CONTAINER", "atlas-mcp")
    if connection := os.getenv("ATLAS_STORAGE_CONNECTION_STRING"):
        return CloudStore(TableClient.from_connection_string(connection, table), ContainerClient.from_connection_string(connection, container))
    account = os.environ["ATLAS_STORAGE_ACCOUNT"]
    import re
    if not re.fullmatch(r"[a-z0-9]{3,24}", account):
        raise ValueError("Invalid Azure Storage account name")
    credential = DefaultAzureCredential()
    return CloudStore(TableClient(f"https://{account}.table.core.windows.net", table, credential=credential),
                      ContainerClient(f"https://{account}.blob.core.windows.net", container, credential=credential))


def serve(store):
    from .cloud_service import CloudAtlas, Projection
    from .http_transport import EntraVerifier, build_http_server
    from .live import Feed, Presence, add_routes
    intake = CloudIntake(store)
    verifier = EntraVerifier(os.environ["ATLAS_TENANT_ID"], os.environ["ATLAS_API_AUDIENCE"], intake.principal_actor)
    lock = threading.Lock()
    current, refreshed = None, 0
    def factory(actor):
        nonlocal current, refreshed
        intake.admit_call(actor)
        with lock:
            if current is None or time.monotonic()-refreshed > 30:
                current = Projection(store.container)
                refreshed = time.monotonic()
            projection = current
        return Presence(CloudAtlas(intake, projection, actor), store, actor)
    from .oauth import AtlasOAuth, add_routes as add_oauth_routes
    oauth = AtlasOAuth(intake, os.environ["ATLAS_PUBLIC_URL"], entra=verifier)
    server = build_http_server(factory, verifier, os.environ["ATLAS_PUBLIC_URL"], loopback_proxy=True, oauth=oauth)
    add_routes(server, Feed(store))
    add_oauth_routes(server, oauth, os.getenv("ATLAS_SITE_URL", "https://salmon-island-04aa8f603.1.azurestaticapps.net"))
    server.run(transport="streamable-http")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    sub.add_parser("initialize", help="Create private container/table in an existing approved account")
    enroll = sub.add_parser("enroll")
    enroll.add_argument("name")
    enroll.add_argument("--model", required=True)
    enroll.add_argument("--family", required=True)
    enroll.add_argument("--principal", required=True, help="Verified Entra issuer URL|object UUID")
    enroll.add_argument("--allow-review", action="store_true")
    enroll.add_argument("--quota", type=int, default=100)
    for command in ("publish", "drain"):
        p = sub.add_parser(command)
        p.add_argument("--ledger", type=Path, default=Path("data/ledger/ledger.db"))
        if command == "publish":
            p.add_argument("--data", type=Path, default=Path("data/build"))
        else:
            p.add_argument("--state", type=Path, default=Path("data/contributions/cloud-bridge"))
            p.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    store = configured_store()
    intake = CloudIntake(store)
    if args.command == "serve":
        return serve(store)
    if args.command == "initialize":
        store.initialize()
        result = {"initialized": True, "public_blob_access": False}
    elif args.command == "enroll":
        profile = intake.enroll(args.name, args.model, args.family, args.principal, args.allow_review, args.quota)
        result = {k: profile[k] for k in ("id", "public_key", "model", "model_family", "allow_review", "daily_quota")}
    elif args.command == "publish":
        from .cloud_publish import publish
        result = publish(store, args.ledger, args.data)
    else:
        from .cloud_worker import pull_and_drain
        if not 1 <= args.limit <= 1000:
            parser.error("Limit must be 1–1000")
        result = pull_and_drain(intake, args.state, args.ledger, limit=args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
