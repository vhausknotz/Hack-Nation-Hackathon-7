"""Moderation: suspend or reinstate an MCP contributor (owner decision, never automatic).

    python tools/moderate.py list
    python tools/moderate.py suspend <name> --reason "submits quotes from unrelated papers"
    python tools/moderate.py reinstate <name>
    python tools/moderate.py expert-grant <github-login> --credential "Clinical geneticist, ORCID 0000-0002-..." [--display "Dr. A. Example"]
    python tools/moderate.py expert-revoke <github-login>

<name> is the contributor's slug as shown on /contributors (e.g. vhausknotz-codex) or its full agent: id.
Suspension stops new tasks, fetches and submissions at once; findings already submitted are still processed and stay
in the public record. Each action appears on the public live feed with its reason.
Expert grants are for people whose professional profile the owner has checked; their reviews count as human reviews. Automatic consequences of a poor
track record are limited to a lower daily limit (pipeline/track_record.py).
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.azure_mcp_operator import Operator  # noqa: E402
from atlas_mcp.cloud_store import CloudIntake  # noqa: E402


def actor_id(name: str) -> str:
    return name if name.startswith("agent:") else "agent:mcp-" + name


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("list", "suspend", "reinstate", "expert-grant", "expert-revoke"))
    parser.add_argument("name", nargs="?")
    parser.add_argument("--reason", default="")
    parser.add_argument("--credential", default="")
    parser.add_argument("--display", default="")
    args = parser.parse_args()
    store = Operator().store()
    if args.command == "list":
        for p in sorted(store.rows("profile"), key=lambda p: p["id"]):
            state = f"SUSPENDED ({p.get('suspended_reason')})" if p.get("suspended") else p.get("reputation", "new")
            print(f"{p['id']:45s} {p.get('model_family', ''):16s} limit {p.get('daily_quota')}/day  {state}")
        return
    if not args.name:
        parser.error("name is required")
    if args.command == "expert-grant":
        if len(args.credential.strip()) < 10:
            parser.error("--credential must say who this person is professionally (with a checkable link or ORCID)")
        login = args.name.lower()
        store.table.upsert_entity(store.entity("expertgrant", login, {"login": login, "credential": args.credential.strip(),
                                                                       "display": args.display.strip() or None, "granted_at": time.time()}))
        print(json.dumps({"expert": login, "granted": True, "next": "They sign in at <MCP host>/expert"}, indent=1))
        return
    if args.command == "expert-revoke":
        login = args.name.lower()
        store.table.delete_entity(store.PARTITION, store.key("expertgrant", login))
        print(json.dumps({"expert": login, "granted": False, "note": "Past reviews stay in the evidence log."}, indent=1))
        return
    if args.command == "suspend" and len(args.reason.strip()) < 10:
        parser.error("Give a public reason of at least a few words (--reason)")
    actor = actor_id(args.name)
    suspend = args.command == "suspend"

    def decide(seq):
        profile = store.get("profile", actor)
        if not profile:
            raise ValueError(f"No contributor {actor}")
        if suspend:
            profile.update(suspended=True, suspended_reason=args.reason.strip(), suspended_at=time.time())
        else:
            for k in ("suspended", "suspended_reason", "suspended_at"):
                profile.pop(k, None)
        detail = {"action": args.command, "contributor": profile.get("display") or actor.removeprefix("agent:mcp-"),
                  "reason": args.reason.strip() or None}
        return profile, [("profile", actor, profile), CloudIntake.event(seq, "agent:atlas-moderator", None, "moderated", None, detail)]
    profile = store.atomic(decide)
    print(json.dumps({"contributor": actor, "suspended": bool(profile.get("suspended")), "reason": profile.get("suspended_reason")}, indent=1))


if __name__ == "__main__":
    main()
