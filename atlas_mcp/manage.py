"""Operator controls, deliberately not MCP tools: enrollment and the sole ledger writer."""
import argparse
import json
from pathlib import Path

from .intake import Intake
from .service import DEFAULT_LEDGER, DEFAULT_STATE
from .worker import drain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="command", required=True)
    enroll = sub.add_parser("enroll")
    enroll.add_argument("name")
    enroll.add_argument("--model", required=True)
    enroll.add_argument("--model-family", required=True)
    enroll.add_argument("--allow-review", action="store_true")
    enroll.add_argument("--daily-quota", type=int, default=100)
    worker = sub.add_parser("drain")
    worker.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    worker.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.command == "enroll":
        result = Intake(args.state).enroll(args.name, args.model, args.model_family, args.allow_review, args.daily_quota)
    else:
        if not 1 <= args.limit <= 1000:
            parser.error("Drain limit must be 1–1000")
        result = drain(args.state, args.ledger, limit=args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
