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

## What can cost money

- **Model calls** (Luna, Sol, embeddings) are billed per token, only while the pipeline or agents run. Every call is cached and its token usage logged, so reruns are free and spend is measurable.
- **Web search** is billed separately from tokens. The earlier planning range was USD 10–35 per 1,000 searches; confirm current pricing before scaling. Campaign receipts count searches. Do not interpret `usd_tokens_known_prices` as the total bill: it excludes search fees and models without configured prices.
- The full plain-summary run uses `data/cache/plain_summary_usage.jsonl` so it does not contaminate the concurrent community scout's usage delta.
- **Future live service** (database, API + MCP server): not created yet. These will be paid resources and need the owner's approval first.
- **Local MCP:** implemented in `atlas_mcp/`, with no additional Azure resources or automatic model spending. The low-idle-cost hosting recommendation and unimplemented cloud prerequisites are in [mcp_hosting.md](mcp_hosting.md). Do not deploy the local SQLite stores onto ephemeral Functions storage.
- **Public MCP submissions** must never trigger model calls paid from this account. Reviews of outside submissions run only for prioritized or funded work (see PLAN.md, section 11).

## Deploying the website

```powershell
./.venv/Scripts/python pipeline/export_app.py   # if data changed
cd app; npm run build
# then deploy dist/ with the SWA CLI using the deployment token from Azure
```
