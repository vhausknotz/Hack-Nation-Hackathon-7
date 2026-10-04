"""Fingerprint publication inputs, excluding operator prose and generated outputs.

Git HEAD alone misses ignored graph rebuilds and changes on every handoff edit.
Hash tracked runtime/configuration files plus the inputs export_app reads. The
ledger has its own signed revision. Add any new external build input here.
"""
import hashlib
from pathlib import Path
import subprocess


BUILD_INPUTS = ("conditions.jsonl", "neighbors.jsonl", "genes.jsonl", "phenotypes.jsonl",
                "mechanisms.jsonl", "groups.jsonl", "report.json", "map.json")
OPERATOR_DOCS = {"AGENTS.md", "HANDOFF.md", "PLAN.md", "README.md", "CHALLENGE_BRIEF.md"}


def runtime_path(path: str) -> bool:
    if path in OPERATOR_DOCS or path.startswith(("docs/", "data/campaigns/", "data/evaluations/")):
        return False
    # These directories' Markdown files are operator runbooks, not app content.
    if path.endswith(".md") and path.split("/")[0] in {"atlas_mcp", "enrich", "agents", "ledger", "pipeline", "infra"}:
        return False
    return True


def publication_fingerprint(root: Path, *, website: bool = True) -> str:
    root = Path(root)
    digest = hashlib.sha256(f"atlas-publication-inputs-v1:website={website}\0".encode())
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", "HEAD"], cwd=root)
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        _, path = entry.split(b"\t", 1)
        if runtime_path(path.decode("utf-8")):
            digest.update(entry + b"\0")  # Git blob hash, path and mode
    files = [(root / "data/build" / name, True) for name in (BUILD_INPUTS if website else ("conditions.jsonl",))]
    if website:
        files += [(root / "data/build/plain.jsonl", False), (root / "data/sources_manifest.json", True)]
    for path, required in files:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Missing publication input: {path.name}")
            digest.update(b"absent\0")
            continue
        before = path.stat()
        content = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                content.update(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Publication input changed while hashing: {path.name}")
        digest.update(b"present:" + content.digest() + b"\0")
    return "inputs-v1:" + digest.hexdigest()
