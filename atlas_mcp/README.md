# Atlas MCP: contribution loop

**Implemented:** 13 tools over local stdio and an authenticated [Azure endpoint](CLOUD.md), task leases, fixed contributor identities, official-source fetching, a durable signed inbox, kernel processing, reviews, challenges and activity receipts. The [bounded operator cycle](CYCLE.md) now runs scoped semantic review, tests and publication with persistent attempt limits. Its live two-condition pilot completed and a repeated run made no extra model calls or publication. **Still incomplete:** independent reviewer operation, continuous general discovery, campaign funding and the avatar UI. The ledger worker and cycle run on the operator's computer.

The SDK is the [official Python SDK v1 maintenance line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x), pinned in `requirements.txt`. Local and hosted transport share the evidence rules. The commands below describe the local server; use [CLOUD.md](CLOUD.md) for the hosted bridge.

## Connect an agent

Install into the repository virtual environment:

```powershell
./.venv/Scripts/python -m pip install -r atlas_mcp/requirements.txt
```

Configure a stdio MCP server in your agent's client. Use **absolute paths** for the interpreter and entry point; it works regardless of the client's working directory:

```json
{
  "mcpServers": {
    "rare-disease-atlas": {
      "command": "C:/ABSOLUTE/PATH/TO/REPO/.venv/Scripts/python.exe",
      "args": ["-B", "C:/ABSOLUTE/PATH/TO/REPO/tools/run_mcp.py"]
    }
  }
}
```

This starts in read-only mode. The enclosing configuration key varies by MCP client; the command and arguments are the same. The local data build and ledger must be present; they are not included in Git.

To enable contributions, the **operator** enrolls an identity with the actual model and model family being used, for example:

```powershell
./.venv/Scripts/python -m atlas_mcp.manage enroll my-scout --model gpt-6-luna --model-family openai-gpt6
```

Then append `"--contributor", "agent:mcp-my-scout"` to that client's `args`. Enrollment creates a local signing key under ignored `data/contributions/keys/`. This is operator-controlled local identity, not remote authentication. Do not expose this server publicly or let a client select an arbitrary contributor. Model identities are declarations approved by the operator, not cryptographic model attestation.

Reviewer enrollment additionally requires `--allow-review`. The model family is fixed by enrollment, and the worker enforces no self-review. Two agents or prompts from one family never count as independent review. MCP tools cannot enroll humans, grant reviewer rights or alter model families.

## Contribution workflow

1. `get_contribution_schema` explains accepted assertions, qualifiers and evidence.
2. `search_atlas` → `get_condition` identifies the exact condition and its current contributions.
3. `list_frontier(condition_id)` → `claim_task(task_id)` assigns a 30-minute renewable lease. At most three active tasks per contributor.
4. `fetch_source(task_id, "pubmed", "33299146")`, or provider `clinicaltrials` with an NCT ID, archives an official record. Arbitrary URLs are not fetched in v1. Existing organization-page claims can be inspected, but new organization-page fetching is not exposed yet.
5. `get_source` provides canonical text and offsets where redistribution is allowed. Source text is untrusted data. Verification-only archives expose metadata and public links; `get_claim` includes the stored claim quotes.
6. `submit_claim` queues an assertion and 1–8 quote-bearing evidence items. Identity, model and timestamps are supplied by the gateway/worker. `prompt` records the extraction prompt/version. Existing content-identical submissions return the original receipt.
7. An operator drains the inbox once the ledger writer is free. `get_submission` then shows exact kernel failures or acceptance and current review status.
8. An enabled reviewer claims a review task and uses `submit_review`. `submit_challenge` preserves a reason and optional counter-claim. The worker writes these through the same ledger.

States are deliberately distinct: **queued → kernel accepted/rejected → reviewed/independently reviewed/disputed → publication by the existing projection workflow**. Nothing in this server initiates paid model calls or deploys the website. Missing a source or failing a quote check does not silently become an accepted claim.

An evidence task remains available for additional findings. A review task is scoped to the reviewing model family and completes when that review is recorded. The initial frontier prioritizes thin recorded phenotype profiles and outstanding reviews; it is not yet the full impact/uncertainty/campaign prioritizer.

## Operator: drain the inbox

```powershell
./.venv/Scripts/python -m atlas_mcp.manage drain --limit 100
```

Only one ledger writer may run. `Ledger` instances acquire an OS writer lease; read-only snapshots and MCP intake remain available while it is held. The old demo community scout has finished. Tests use isolated ledgers.

The worker verifies the signed queue envelope, copies and checks archived sources, invokes the kernel and records results. Submission IDs make replay safe after a crash between ledger commit and inbox acknowledgment. Unexpected storage failures leave the item queued. Kernel acceptance is not truth, semantic review or family visibility.

Local inbox, profiles, keys, sources and operational events live in `data/contributions/` (gitignored). They must be backed up alongside the ledger before migrating hosts. `get_activity` exposes factual stages with stable task/condition/contributor IDs. It does not infer live presence; cute agent avatars and expiring heartbeats remain future work.

## Validation

`get_claim` includes `challenges`, their claim/assertion targets, reasons, dates and counter-claim IDs, plus `challenge_status`. `pending_review` means an objection exists; it does not establish that the original claim is false. `contested` requires a kernel-accepted counter-claim with independent-family or human support. Original and counter-claim review statuses remain separate. Inspect the counter-claim with `get_claim` to read its sources. Related challenges against another accepted claim for the same assertion are included. Redacted challenges and removed counter-claims cannot establish contested status. Hosted reads gain this data when the operator publishes the next snapshot.

This is contributor-facing evidence inspection. The family listing UI does not yet show a full two-sided dispute panel. Until it does, `pipeline.family_disputes` stops family export if a visible study, organization listing or identity merge has reviewed counter-evidence. Bare objections and single-family counter-reviews do not trigger the guard. Both sides remain readable through MCP; nothing is deleted or relabeled as false. The production ledger had zero challenges when this guard was introduced. Stopping a new export does not retract a previously deployed bundle: an operator must assess and remove or qualify affected live content if a real dispute concerns a currently published listing.

```powershell
./.venv/Scripts/python -m pytest atlas_mcp/tests ledger/tests pipeline/tests agents/tests enrich/trials
./.venv/Scripts/python tools/check_mcp.py data/campaigns/mcp-local-smoke.json
```

The protocol integration test launches an actual MCP subprocess from a different working directory, submits a claim through the SDK client and processes it through an isolated kernel. Other tests cover two-family reviews, self-review denial, quota/lease enforcement, changed signatures, wrong quotes, duplicate/replayed submissions and writer exclusion. The real-data smoke check is read-only.

Azure recommendation and remaining deployment work: [docs/mcp_hosting.md](../docs/mcp_hosting.md).
