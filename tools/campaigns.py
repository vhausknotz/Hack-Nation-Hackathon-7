"""Campaigns: focused, public efforts on a condition or a small neighborhood of conditions (owner decisions).

    python tools/campaigns.py list
    python tools/campaigns.py create <slug> --title "..." --goal "..." --conditions MONDO:0012812 MONDO:0014590 \
        [--sponsor "Org name" --sponsor-url https://...] [--budget-usd 5]
    python tools/campaigns.py fund <slug> --budget-usd 10       # owner received funding outside the atlas
    python tools/campaigns.py close <slug>

Rules (PLAN.md section 10, shown on /campaigns): money buys attention, never acceptance; no pay-to-rank of evidence;
contradictions are never suppressed; no outcomes are promised to families. A campaign moves its conditions up every
agent's task list (pipeline/frontier.py). A funded budget (budget_usd > 0) additionally lets the atlas's Luna scouts
spend on its conditions, tracked against the campaign (tools/luna_scout.py), on top of their base cap; the owner sets it
only after receiving the funding. There is no payment processing in the atlas.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.azure_mcp_operator import Operator  # noqa: E402
from atlas_mcp.cloud_store import CloudIntake  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("list", "create", "fund", "close"))
    parser.add_argument("slug", nargs="?")
    parser.add_argument("--title", default="")
    parser.add_argument("--goal", default="")
    parser.add_argument("--conditions", nargs="*", default=[])
    parser.add_argument("--sponsor", default="")
    parser.add_argument("--sponsor-url", default="")
    parser.add_argument("--budget-usd", type=float, default=0.0)
    args = parser.parse_args()
    store = Operator().store()
    if args.command == "list":
        for c in store.rows("campaign"):
            print(f"{c['id']:28s} {c['status']:7s} {len(c['conditions'])} conditions  budget ${c['budget_usd']:.2f} spent ${c.get('spent_usd', 0):.2f}  {c['title']}")
        return
    if not args.slug or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", args.slug):
        parser.error("Give a lowercase slug, e.g. snare-neighborhood")

    def decide(seq):
        row = store.get("campaign", args.slug)
        if args.command == "create":
            if row:
                raise ValueError("Campaign exists")
            if not args.title or len(args.goal) < 20 or not args.conditions:
                raise ValueError("--title, a --goal of a sentence or more and --conditions are required")
            if not all(re.fullmatch(r"MONDO:\d{7}(-HGNC:\d+)?", c) for c in args.conditions):
                raise ValueError("Conditions must be atlas condition IDs")
            row = {"id": args.slug, "title": args.title.strip(), "goal": args.goal.strip(), "conditions": args.conditions,
                   "sponsor": {"name": args.sponsor.strip(), "url": args.sponsor_url.strip() or None} if args.sponsor.strip() else None,
                   "budget_usd": max(0.0, args.budget_usd), "spent_usd": 0.0, "status": "open", "created": time.time()}
            stage = "campaign_started"
        elif not row:
            raise ValueError("No such campaign")
        elif args.command == "fund":
            row["budget_usd"] = round(row["budget_usd"] + max(0.0, args.budget_usd), 2)
            stage = "campaign_funded"
        else:
            row["status"], row["closed"] = "closed", time.time()
            stage = "campaign_closed"
        detail = {"campaign": row["id"], "title": row["title"], "budget_usd": row["budget_usd"]}
        return row, [("campaign", row["id"], row), CloudIntake.event(seq, "agent:atlas-campaigns", {"id": None, "condition_id": row["conditions"][0]}, stage, None, detail)]
    print(json.dumps(store.atomic(decide), indent=1))


if __name__ == "__main__":
    main()
