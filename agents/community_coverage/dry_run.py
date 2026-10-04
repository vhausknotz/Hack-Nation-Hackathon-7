"""Run every staged candidate through the real kernel in a throwaway ledger, to prove it would be accepted.

    python -m agents.community_coverage.dry_run [--raw <dir with mondo.obo, hgnc_complete_set.txt, ...>]

Uses a temporary ledger and temporary signing keys, reading sources from the package's own archive. The production
ledger (data/ledger) is never opened. Acceptance here means the mechanical checks pass (schema, identifiers, archived
source hashes, verbatim quotes at the stated offsets, signature). It says nothing about whether the claim is true:
semantic review is the lead's separate step.
"""

import json
import sys
import tempfile
from pathlib import Path

from ledger import identity, registry
from ledger.api import Ledger, now
from ledger.sources import Source

from .stage import ARCHIVE, CONTRIBUTOR, PACKAGE, ROOT


def raw_dir(args: list[str]) -> Path:
    """The pinned ontology files (gitignored). In a worktree they usually live in the main checkout next to it."""
    if "--raw" in args:
        return Path(args[args.index("--raw") + 1])
    for candidate in (ROOT / "data" / "raw", ROOT.parent / "Hack-Nation-Hackathon-7" / "data" / "raw"):
        if (candidate / "mondo.obo").exists():
            return candidate
    raise SystemExit("pinned files not found; pass --raw <dir containing mondo.obo>")


def main(args: list[str]) -> int:
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    candidates = [json.loads(line) for line in (PACKAGE / "candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    failures = 0
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        ledger = Ledger(tmp / "ledger.db", registry_=registry.Registry(raw_dir(args)), keys_dir=tmp / "keys", source_root=ARCHIVE)
        signer = ledger.register(identity.load_or_create(CONTRIBUTOR, tmp / "keys"), kind="agent", manifest={"role": "dry-run of staged community candidates"})
        for entry in manifest["sources"].values():
            ledger.add_source(Source(**entry["source"]), signer)
        for c in candidates:
            claim = {"assertion": c["claim"]["assertion"], "evidence": [{k: v for k, v in e.items() if k != "supports"} for e in c["claim"]["evidence"]],
                     "provenance": {**c["claim"]["provenance_proposal"], "created": now()}}
            result = ledger.propose(claim, signer)
            bad = [ch for ch in result.checks if not ch["passed"]]
            failures += not result.accepted
            print(f"{'ACCEPT' if result.accepted else 'REJECT'} {c['candidate_id']}" + (f"  {bad}" if bad else ""))
        ledger.store.close()
    print(f"{len(candidates) - failures}/{len(candidates)} accepted by the kernel (throwaway ledger)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
