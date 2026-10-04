# Moving the atlas engine to Azure

Goal: the atlas keeps reacting to agents (quote checks, reviews, rebuilds, live publication) without the owner's PC.
Status: **plan, awaiting the owner's choice and approval of a paid resource.** Nothing has been created.

## What has to move

| Piece | Size | Notes |
|---|---|---|
| Ledger (`data/ledger/ledger.db`, sources, keys) | ~490 MB | Single writer. Signing keys are the most sensitive part. |
| Raw datasets (`data/raw`) | ~480 MB | Re-downloadable with `pipeline/download.py`. |
| Built graph (`data/build`) | ~500 MB | Rebuilt by the engine on each publication. |
| Deployed export used as diff base (`app/public/data`) | ~230 MB | Needed to publish only changed shards. |
| Engine work per publication | 1.5–2.5 min CPU, several GB RAM (to be measured) | `build_graph.py` holds similarity matrices in memory. |

The cloud gateway (Azure Functions, already running) stays as it is. Only the worker moves.

## Options

### A. Small Linux VM running the same engine (recommended)
- One B-series VM with 2 vCPU / 4–8 GB RAM, Ubuntu, a 64 GB SSD disk, in the existing `rare-disease-atlas-mcp` resource group.
- The engine runs as a systemd service exactly as on the PC (`tools/atlas_engine.py`); identical code paths, instant reaction (polling every 15 s).
- Sol calls through the VM's managed identity (needs a role on `valiOpenAI`) or a key stored only in the VM's protected environment.
- Signing keys live on the encrypted disk, readable only by the service account; nightly backup of ledger + keys to private blob storage (versioned).
- Website full deploys can also run there (Node installed), so the PC is not needed for those either.
- **Cost: roughly €25–45/month** (VM ~€25–35 for 2 vCPU/4–8 GB, disk ~€5, backup storage cents). Auto-shutdown is not possible if it should always react.

### B. Event-driven Container Apps job (cheaper at low volume, slower and more work)
- The gateway also drops a queue message per submission; a Container Apps job starts when the queue is non-empty, runs the engine until it is empty, and scales to zero.
- State on Azure Files (SQLite on a network share needs care: one writer only, which the job guarantees) or synced to/from Blob each run.
- Each run first loads ~1.5 GB of state: a contribution would show its quote check after a cold start of a minute or two instead of seconds.
- **Cost: roughly €5–20/month at today's volume**, growing with activity; plus engineering to make state loading fast and safe.

### C. Stay on the PC
- €0, but the atlas stops reacting whenever the PC is off.

## Recommendation
**Option A.** It keeps the live experience instant, reuses the exact tested engine, and is the simplest to operate and to explain. Option B can follow later if cost matters more than immediacy.

## Steps once approved
1. Create the VM (tag `project=rare-disease-atlas`), register it in `docs/operations.md`, extend `tools/azure_status.ps1` / `azure_off.ps1`, and raise the monthly budget alert from $5 accordingly.
2. Copy ledger, keys, contributions state and the base export; download raw data on the VM; verify the ledger log and tree head match the PC exactly.
3. Stop the PC engine (`data/engine/stop`), start the VM service, confirm one end-to-end contribution, then leave the PC copy as a cold backup.
4. Nightly encrypted backups of ledger + keys to blob storage; a health line in `/live/feed` so the website can show "engine online".

## Owner decisions
- Approve Option A (or B) and a monthly budget for it.
- Whether the VM may also hold the website deploy credentials (to deploy without the PC).
