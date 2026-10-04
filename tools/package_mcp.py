"""Build a source-only Azure Functions package from an explicit allowlist. No keys/data."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def package(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for folder in ("atlas_mcp", "ledger"):
        files.extend(p for p in (ROOT/folder).glob("*.py"))
    files.extend(ROOT/p for p in ("enrich/trials/run.py", "pipeline/llm.py", "pipeline/http_cache.py"))
    requirements = (ROOT/"atlas_mcp/requirements-cloud.txt").read_text().replace("-r requirements.txt", (ROOT/"atlas_mcp/requirements.txt").read_text())
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for p in sorted(files):
            archive.write(p, p.relative_to(ROOT).as_posix())
        archive.write(ROOT/"infra/mcp/host.json", "host.json")
        archive.writestr("requirements.txt", requirements)
    return {"path": str(output), "files": len(files)+2, "bytes": output.stat().st_size,
            "contains_data_or_keys": False, "dependencies": "Install with Linux remote build before running"}


if __name__ == "__main__":
    print(json.dumps(package(ROOT/"data/build/mcp-function.zip"), indent=2))
