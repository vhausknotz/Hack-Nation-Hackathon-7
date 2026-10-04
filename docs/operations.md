# Operations: what runs in Azure, what it costs, how to switch it off

## Check what is on

```powershell
powershell -File tools/azure_status.ps1
```

This lists every project resource (everything is tagged `project=rare-disease-atlas`) with its pricing tier, and the shared model resource.

## Switch it off

```powershell
powershell -File tools/azure_off.ps1
```

It asks for confirmation, then deletes the project's resource groups. The shared Azure OpenAI resource (`valiOpenAI`) is not touched. It is pay-per-use and costs nothing while idle.

You can also switch everything off in the Azure portal: Resource groups → `rare-disease-atlas` → Delete resource group.

## Resource register

Every resource created for this project must be listed here, tagged, and approved by the owner if it isn't free.

| Resource | Type | Tier / cost | Resource group | Created | Purpose |
|---|---|---|---|---|---|
| `rare-disease-atlas` | Static Web App | **Free** ($0) | `rare-disease-atlas` (West Europe) | 2026-10-03 | Hosts the website: https://salmon-island-04aa8f603.1.azurestaticapps.net |
| `valiOpenAI` (pre-existing, shared) | Azure AI Services | Pay per token | (owner's existing group) | — | GPT-6 Luna/Sol and embeddings for the pipeline and agents |
| `rare-atlas-mcp-1180fc` / `rare-atlas-mcp-1180fc-plan` | Function App / Flex Consumption plan | On demand, 512 MB; no Always Ready | `rare-disease-atlas-mcp` (Sweden Central) | 2026-10-04 | Authenticated MCP intake; no model calls |
| `rareatlas1180fcebe2` | Storage account | Standard LRS, private Blob/Table (a few hundred MB incl. ClinVar per-gene files, cents/month) | `rare-disease-atlas-mcp` | 2026-10-04 | Durable MCP inbox, sources, read snapshots, live overlay, `variants/<GENE>.json` (weekly ClinVar), frontier/track-record/expert-queue JSON, request counts, expert grants and sessions |
| `mcp-monthly-allowance` | Budget alert | **39/month** (raised 2026-10-04 for the engine VM), alerts at 50/80/100% actual and 100% forecast; not a hard cap | `rare-disease-atlas-mcp` | 2026-10-04 | Owner ceiling: 60 USD/month for the whole project (raised from 45 on 2026-10-04) = hosting ~37 + Sol referee cap 12 + Luna scouts cap 5 |
| `atlas-engine` (+ `-nsg`, `-vnet`, `-ip`, `-nic`, OS disk) | Linux VM B2als_v2 (2 vCPU, 4 GB), Standard SSD 32 GB, Standard static IP | ~28.40 + ~3.65 + ~2.40 USD/month while running; `stop` (deallocate) leaves ~6/month | `rare-disease-atlas-mcp` (Sweden Central) | 2026-10-04 | Always-running engine (`tools/atlas_engine.py` as systemd service), nightly backup to private blob `backups/engine/`. No inbound access (NSG denies Internet). Also runs the Luna scouts (`atlas-scouts`), the weekly ClinVar refresh (`atlas-variants.timer`, no model calls) and the family navigation assistant (`atlas-assistant`, OFF by default; when enabled hard caps $0.15/day, $3/month of Luna). Operate with `tools/azure_engine_vm.py status/stop/start/logs/update/scouts/variants/site`. |

Dedicated MCP status/off: `powershell -File tools/azure_mcp.ps1 status` and `powershell -File tools/azure_mcp.ps1 stop`. Stop leaves billable storage. `remove -ConfirmRemove` permanently deletes only the MCP group after the operator has backed up wanted contributions. It leaves the website/shared models untouched. [MCP connection and operator runbook](../atlas_mcp/CLOUD.md).

## What can cost money

- **Model calls** (Luna, Sol, embeddings) are billed per token, only while the pipeline or agents run. Every call is cached and its token usage logged, so reruns are free and spend is measurable.
- **Web search** is billed separately from tokens. The earlier planning range was USD 10–35 per 1,000 searches; confirm current pricing before scaling. Campaign receipts count searches. Do not interpret `usd_tokens_known_prices` as the total bill: it excludes search fees and models without configured prices.
- The full plain-summary run uses `data/cache/plain_summary_usage.jsonl` so it does not contaminate the concurrent community scout's usage delta.
- **MCP:** the owner approved the dedicated Functions/storage resources and, separately, the server-side storage-key fallback after Azure denied managed-identity role assignment. It is deployed; the ledger worker stays local. Application quotas and budget alerts limit/flag use but cannot guarantee a hard dollar cap. See [the cloud runbook](../atlas_mcp/CLOUD.md). Never deploy local SQLite evidence stores onto ephemeral Functions storage.
- **Public MCP submissions** must never trigger model calls paid from this account. Reviews of outside submissions run only for prioritized or funded work (see PLAN.md, section 11).

## Deploying the website

```powershell
./.venv/Scripts/python pipeline/export_app.py   # if data changed
cd app; npm run build
# then deploy dist/ with the SWA CLI using the deployment token from Azure
```

## Ledger content redaction

`Ledger.redact` is an operator action for the exceptional categories in PLAN, never a way to hide scientific disagreement. It clears the event payload, removes the corresponding claim/review/challenge projection and preserves the original leaf hash plus a tombstone. Review/challenge readers also suppress legacy projection rows whose event was already redacted; a removed review no longer counts toward trust. This behavior is covered by synthetic regression tests. The production ledger had no redacted events when checked on 2026-10-04.

This is logical removal from active ledger reads, not a claim of complete physical erasure. Previously published immutable cloud snapshots, website bundles, backups and SQLite free pages may retain earlier copies. An actual privacy incident requires stopping affected publication/access, identifying and removing those copies under the applicable retention obligations, then rebuilding the active view. Do not treat another publish alone as removal of old blobs, or put the sensitive content in an incident report. No such deletion or production redaction was performed during this repair.
