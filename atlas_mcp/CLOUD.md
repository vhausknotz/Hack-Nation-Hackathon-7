# Hosted MCP preparation

**Implemented and tested locally; not deployed.** The source-only deployment package is built by `python tools/package_mcp.py`. `infra/mcp/main.bicep` compiles; a real Functions deployment/connection test is still required. No paid resources have been created.

## Implemented contract

The same 13 tools run over stateless Streamable HTTP at `/mcp`. Every tool request requires an Entra v2 access token for the configured tenant and API audience, with `Atlas.Contribute` delegated scope or application role. Signature, issuer, audience, expiry, not-before and enrolled issuer/object-ID identity are checked. An authenticated but unenrolled principal cannot contribute. Operator enrollment fixes model family and review permission. Separate agents needing distinct reviewer identities require distinct enrolled principals; a shared user token does not make independent agents.

The gateway supplies OAuth protected-resource metadata. It does **not** register clients or implement an OAuth authorization server. Entra application/API registration, exposed scope, client permission/consent and a real client sign-in must be configured before announcing a connectable endpoint. This first version is for enrolled contributors, not anonymous public signup.

Table Storage holds task leases, daily quotas, profiles, signed submission references and factual activity. Conditional guard updates and same-partition transactions prevent conflicting claims or quota races. Immutable Blob payloads are written first, then made discoverable in an atomic Table transaction. The Table submission rows **are the durable outbox**; there is no separate Queue write that could be lost. Content written before a failed transaction can be orphaned but never accepted as a submission. Polling is explicit and bounded. This small single-partition design favors correctness and low initial cost; archive/index activity before scaling to a large public service.

Contributor signing keys are held privately by the service and operator worker, as in local enrollment. Signatures establish the gateway-bound enrolled identity; this is not client-held-key attestation. Private blobs never appear in tool results. Managed identity accesses storage; there is no model API credential or model invocation in gateway tools.

The local bridge is bound to one persistent worker state directory and uses OS locks. It verifies signatures/source bytes, calls the existing kernel, records signed ledger receipts, then acknowledges cloud rows. A crash after ledger commit but before acknowledgement replays safely. Switching computers requires explicit recovery; this is **not** distributed ledger failover. When this computer is off, submissions remain queued in Azure.

Publication produces a versioned MCP read snapshot, then atomically changes its pointer. Reads expose contributed claims and archived text only when redistribution is permitted. The website remains a separately reviewed build/deployment. Kernel acceptance, MCP snapshot publication and website publication are distinct.

## Local verification

```powershell
./.venv/Scripts/python -m pip install -r atlas_mcp/requirements-cloud.txt
npx azurite --silent --location data/build/azurite --skipApiVersionCheck
# In another shell:
$env:ATLAS_TEST_AZURITE='1'
./.venv/Scripts/python -m pytest ledger/tests pipeline/tests agents/tests enrich/trials atlas_mcp/tests
```

120 tests passed, including real SDK HTTP authentication/caller isolation, real Azure Storage SDK transactions against Azurite, quota/task races, immutable source/payload storage and kernel commit followed by lost-acknowledgement recovery. No public source fetch, paid model call or Azure cloud resource was needed for those integration tests.

## Provisioning and onboarding checklist

1. Obtain owner approval for the reviewed resource plan, as required by AGENTS.md. One Flex Consumption app/plan, one Standard LRS account; no Always Ready, registry, VM, private endpoint or telemetry workspace. Bicep currently targets Sweden Central, 512 MB, HTTP concurrency 4 and maximum 40 instances (Flex's minimum permitted maximum, not reserved capacity).
2. Validate regional availability, API registration and deployment permissions. Register a single-tenant Entra API with v2 tokens, scope/application permission `Atlas.Contribute`; pre-authorize only intended clients. `apiAudience` is the audience in the API's access tokens, not an ID token or Microsoft Graph token.
3. Deploy `infra/mcp/main.bicep` with unique app/storage names, API audience and operator object ID. Tag/register the resource group as `project=rare-disease-atlas` too. Verify the resulting hostname and set `ATLAS_PUBLIC_URL` to its canonical HTTPS `/mcp` URL if it differs from the configured predictable hostname.
4. Deploy `data/build/mcp-function.zip` with Linux remote dependency build. `host.json` uses Microsoft's MCP custom-handler preview; real platform compatibility remains to be tested. The Functions proxy is configured anonymous because the SDK authenticates the MCP route; that does **not** make the tool route anonymous.
5. Grant the operator/function managed identity only the template's scoped Blob/Table data roles. Allow role propagation, then initialize/publish/enroll using the commands below. Never send the service's managed-identity storage token to an MCP client.
6. Test actual client sign-in, unauthenticated 401, two distinct contributor identities and an isolated fixture contribution through cloud intake to a local test ledger before exposing real task writes. Record the endpoint, costs and shutdown procedure in `docs/operations.md`.

Environment variables: `ATLAS_STORAGE_ACCOUNT`, `ATLAS_TENANT_ID`, `ATLAS_API_AUDIENCE`, `ATLAS_PUBLIC_URL`. Optional `ATLAS_TABLE` (default `atlasintake`), `ATLAS_CONTAINER` (default `atlas-mcp`). `ATLAS_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true` is for local emulator tests; production shared-key access is disabled.

```powershell
./.venv/Scripts/python -m atlas_mcp.cloud initialize
./.venv/Scripts/python -m atlas_mcp.cloud publish
./.venv/Scripts/python -m atlas_mcp.cloud enroll scout-name --model actual-model --family actual-family --principal 'https://login.microsoftonline.com/TENANT/v2.0|OBJECT-ID'
# Only enable --allow-review for an approved reviewer.
./.venv/Scripts/python -m atlas_mcp.cloud drain --limit 25
./.venv/Scripts/python -m atlas_mcp.cloud publish
```

Neither drain nor publish spends on models or deploys the website. No scheduled background bridge is installed. Protect and back up the original ledger, source archive, signing keys and `data/contributions/cloud-bridge/` together. Older immutable read snapshots need a retention job before sustained public use; do not repeatedly publish the full atlas on every tool call.

Regional retail lookup (2026-10-04, Sweden Central, USD) succeeded for Functions and Blob after an initial HTTP 429: Flex on-demand $0.000026/GB-second and $0.40/million executions before grants; Hot LRS General Block Blob v2 starts at $0.0184/GB-month, $0.05/10,000 writes and $0.004/10,000 reads. Table's separate price lookup was rate-limited and is still unverified. Receipts are in `data/build/mcp-*-retail.json`; the public source is the [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices).

Illustrative light workload, **not a forecast or hard cap**: 10,000 invocations at 512 MB averaging 2 seconds costs approximately $0.264 in Functions compute/executions before any grant. Keeping 1 GB of blobs plus 20,000 writes and 100,000 reads adds approximately $0.1584. Table operations, bandwidth, taxes and deployment/cold-start overhead are additional. Source downloads may take longer than 2 seconds. Eligible grants are shared across the subscription, so do not assume they remain available. A $5 monthly planning allowance is ample relative to this example, but metered Azure charges have no automatic hard cap in this template.
