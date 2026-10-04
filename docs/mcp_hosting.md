# MCP hosting decision — 2026-10-04

Status: **deployed and verified on Azure**, including authenticated SDK calls and a real sourced contribution through the kernel and separate Sol review. The owner approved Functions/storage and the dedicated server-side storage-key fallback after managed-identity role assignment was denied. No administrator is available. See [the cloud runbook](../atlas_mcp/CLOUD.md) for connection, credential scope, costs and tested stop/start controls. The ledger worker remains local; publication is explicit.

## Recommendation

Target **Azure Functions Flex Consumption, on demand, with no Always Ready instances**, for short MCP operations and queued work. Use one standard Azure Storage account for durable submission payloads, sources and task/status records. Keep the current free Static Web App. This changes the earlier tentative Container Apps preference because low idle cost and the absence of a container registry/always-on database matter more for this initial workload.

Functions supports an MCP extension with Streamable HTTP. Hosting a custom Python SDK server is also available but is documented as **public preview**, requires stateless Streamable HTTP and Flex Consumption. Validate the custom-handler route against our existing SDK in a deployment test; use the Functions MCP extension adapter if the preview route is unsuitable. Do not confuse stateless HTTP sessions with throwaway application state. [MCP bindings](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-mcp), [SDK hosting limitations](https://learn.microsoft.com/en-us/azure/azure-functions/self-hosted-mcp-servers).

Container Apps remains the fallback if long-running workers or the SDK hosting path require a container. It supports custom MCP servers and scale-to-zero, but does not eliminate storage, image distribution or authentication work. An always-on App Service plan, Kubernetes and a provisioned PostgreSQL instance are unnecessary for the first endpoint. [Microsoft hosting comparison](https://learn.microsoft.com/en-us/azure/container-apps/mcp-choosing-azure-service).

## Durable state and correctness before deployment

The current SQLite intake and ledger are **local development stores**, not files to share between autoscaled Functions instances. Before publishing a writable endpoint:

1. Bind authenticated remote principals to operator-approved contributor manifests and review permissions. A shared Functions key alone is not contributor identity. No tool may grant itself reviewer rights or claim a human identity. Keep keys and tokens out of logs and the website.
2. Implemented cloud intake: immutable signed payloads in Blob Storage and conditional same-partition Table transactions for leases, quota and status. The submission Table rows are themselves the durable outbox, replacing the originally proposed separate Queue and avoiding a dual-write failure gap. Concurrent-instance quota/lease tests pass in Azurite.
3. Run ledger commits through one sequencer. At first, a local worker can pull cloud submissions, but that depends on the owner's computer and must be labeled as such. To make the product continuously available, host that worker with durable ledger storage and a tested ownership/failover protocol. Queue batch size alone does not guarantee a single writer across scaled instances.
4. Keep published read projections separate from the write path. MCP search and read tools should use published indexes/claim records, not download the entire development database per request.
5. Test unauthorized access, duplicate delivery, concurrent leases, process loss, source integrity and a signed-log replay. Then connect trusted review and publication jobs separately. Contributor calls never launch owner-funded reviews.

This is not a lift-and-shift deployment of `atlas_mcp.server`. The same schema, trust rules, tool contract and kernel will carry forward.

## Cost controls

- No Always Ready instances and no Premium plan for this first service; accept cold starts.
- Start with one small deployment and strict per-contributor submission/source quotas. Bound payload size, runtime, model budgets and log retention.
- Avoid storing full source bodies or credentials in telemetry; use short status/correlation records and sampling.
- Static website hosting stays free. Database hosting is deferred until its workload justifies it; cloud storage still incurs charges.
- Azure lists a shared monthly Flex on-demand grant of 250,000 executions and 100,000 GB-s on eligible paid consumption subscriptions. Eligibility and other workloads on this subscription must be checked; this is **not a promise of a free bill**. Storage/networking are charged separately. [Functions pricing](https://azure.microsoft.com/en-us/pricing/details/functions/).
- Regional Functions/Blob rates and a light-use example are in the cloud runbook. A monthly allowance alert of 5 in billing currency is created for the MCP resource group; current spend has not yet returned a currency. Application quotas are enforced. Neither is a hard dollar cap.

The dedicated Function App, plan, storage and budget are registered in `docs/operations.md`. The website and shared model resource are separate.
