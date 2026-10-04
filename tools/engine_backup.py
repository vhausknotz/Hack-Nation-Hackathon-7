"""Nightly backup of the engine's irreplaceable state to private blob storage (kept 14 days).

Ledger (claims, reviews, Merkle log, sources, signing keys), contribution intake state and engine bookkeeping.
Rebuildable data (raw datasets, built graph, exports) is not backed up. Runs on the cloud engine VM via
atlas-backup.timer; needs ATLAS_STORAGE_CONNECTION_STRING.
"""
import io
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
KEEP_DAYS = 14


def main():
    from atlas_mcp.cloud import configured_store
    container = configured_store().container
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        # A consistent copy of the live SQLite ledger, even while the engine writes.
        snapshot = Path(tmp) / "ledger.db"
        with sqlite3.connect(ROOT / "data/ledger/ledger.db") as src, sqlite3.connect(snapshot) as dst:
            src.backup(dst)
        tar.add(snapshot, arcname="data/ledger/ledger.db")
        for rel in ("data/ledger", "data/contributions", "data/engine"):
            for path in (ROOT / rel).rglob("*"):
                name = path.relative_to(ROOT).as_posix()
                if path.is_file() and not name.startswith(("data/ledger/ledger.db", "data/engine/export/")) and not name.endswith(".lock"):
                    tar.add(path, arcname=name)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    container.upload_blob(f"backups/engine/{stamp}.tar.gz", buffer.getvalue(), overwrite=True)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for blob in container.list_blobs(name_starts_with="backups/engine/"):
        if blob.name.split("/")[-1][:10] < cutoff:
            container.delete_blob(blob.name)
    print(f"backup {stamp}: {len(buffer.getvalue()) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
