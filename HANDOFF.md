# Lead handoff — 2026-10-04, 04:00 UTC

**Owner: Codex. No transfer to Claude.** The user is napping and authorized continued work, tests, commits, pushes and existing deployments. Read [nap continuation](docs/agent_tasks/nap_continuation.md) for the temporary heartbeat, usage thresholds and conditional Claude handoff. Deadline: **2026-10-04 15:00 Europe/Berlin**. The challenge's primary persona is a patient-group organizer; caregiver usefulness also matters. Broad coverage is secondary to one useful journey and a real evidence contribution loop.

This file supersedes the contradictory historical checkpoints preserved in [the archive](docs/history/HANDOFF-before-bounded-cycle.md). Read AGENTS.md and PLAN.md as well.

## Working and live

**Focused-copy release df95ff4 is live and verified:** Shared-research cards now copy a focused study-team question with both diagnoses' exact restrictions, review labels/reasons, source dates, evidence IDs and a full-brief link. It sends nothing. A denied clipboard exposes selectable text; the existing brief copy also handles both clipboard failures safely and restores focus. Build `index-BGIIQd2o.js`; four-condition 1440/390 px checks and the denied-clipboard phone check passed. Live STXBP1 desktop and SNAP25/SYNGAP1 phone checks passed, including the exact copied sources/restrictions and evidence histories.

- Website: https://salmon-island-04aa8f603.1.azurestaticapps.net. Globe/flat map, search, 7,328 conditions, plain descriptions, six-stop Directions, reviewed groups/studies, restrictions and printable/copyable question brief (`?brief=1`). Sparse data says not found, never nonexistent.
- Shared research in step 5 connects identical reviewed non-treatment records across different genes. SNAP25 → STXBP1 through NCT01238250; STXBP1 → SYNGAP1 through NCT06555965. Both diagnoses' evidence and restrictions stay attached. Questions about protocols, questionnaires and data definitions are descriptive leads, not independently reviewed partnership recommendations.
- **Website release df95ff4 is live and verified**, JS `index-BGIIQd2o.js`. Step 6 shows actual listing-check history; the brief includes recorded review dates/models; About correctly explains the single-family review boundary. Live STXBP1 desktop and SNAP25/SYNGAP1 phone checks matched data and expanded history.
- Family agent commit 2b2f5b3 and community agent f382cf4 are integrated. Community candidates: 13 Sol-supported, Angelman unresolved. 57 conditions have patient groups and 77 have any listing. STXBP1 organization alias and Simons profile/source issues were corrected through reviewed claims.
- MCP: https://rare-atlas-mcp-1180fc.azurewebsites.net/mcp. All 13 authenticated tools verified with the official SDK. Entra-enrolled contributors, fixed official sources, durable private storage, quotas, signed submissions, explicit local ledger worker. `tools/run_cloud_mcp.py` is the tested stdio bridge. Gateway intake never invokes paid models.

## Real contribution cycle completed

Read [atlas_mcp/CYCLE.md](atlas_mcp/CYCLE.md) and `data/campaigns/mcp-shared-study-result.json`.

The official STXBP1/SYNGAP1 natural-history record NCT06555965 was fetched through hosted MCP. Two oversized purpose quotes were rejected by the kernel before any paid review. Corrected submissions preserved all eligibility restrictions, passed the kernel and used **two Sol calls (4,587 input / 370 output tokens)**. STXBP1 was supported with qualification; SYNGAP1 supported. Export, frontend build, desktop/phone checks, MCP snapshot, website deployment and live checks all completed in one operator invocation. Both cloud statuses confirm published review. A real unchanged restart made zero additional calls and skipped publication.

- Latest signed ledger head: size **1704**, root `7f65eb1e6b7dad7835944c670f90c1ff975d392890abe6911be1b0101c865884`.
- Cloud snapshot: `published/661ccc94192247418bf3d4a2dc82eebd`.
- Runner: `tools/run_contribution_cycle.py --plan data/campaigns/mcp-study-cycle-plan.json --state data/contributions/shared-study-cycle` (invoke with repo Python).
- **The pinned two-attempt lifetime allowance is exhausted. Do not reset state or clone a plan to obtain more calls.** Missing Sol dollar pricing is not zero cost.
- One OS writer lease covers review and publication; a separate cycle lease prevents duplicate runners. Ambiguous model calls keep reservations; saved judgments resume without repayment. A dirty repo blocks publication. A changed Git revision currently causes publication again, including doc-only commits.
- This is a proven bounded, explicitly started local cycle, not continuous autonomous discovery or a cloud ledger. The computer and preview on port 4173 must remain running for its browser checks.
- The canonical CTG renderer now preserves structured age/sex/healthy-volunteer fields. Hosted MCP cache is versioned accordingly. Old source archives and the already-running Luna process retain their earlier rendering; do not call their eligibility complete retroactively.

## Active jobs and limits

- Luna screening is running with `--budget 30 --workers 96 --max-workers 384 --continuous`. Last observed 03:35 UTC: about **$21.25 actual**, plus retained/reserved amounts, ~555k actual TPM / 397 RPM, no errors in the measured minute. Inspect `data/enrichment/trials/full/throughput.json` and `screening-continuous.log` for current facts. It does not write the ledger or publish findings.
- Quota verified: 1M TPM / 1,000 RPM. Admission targets 950k; actual billing tokens are lower because of output reservations. Do not casually restart, duplicate or raise the $30 cap. To drain safely, create `data/enrichment/trials/full/stop-screening`.
- Community scout finished all 62 requested conditions. No production ledger writer remains active after the cycle. Preview port 4173 and local Azurite ports 10000–10002 were running at checkpoint.
- Latest full backend suite: **154 passed**, including Azurite tests. Four-condition desktop/phone brief checks and both map modes passed. Live STXBP1 desktop and SNAP25/SYNGAP1 phone checks matched exact exported evidence/restrictions. The new history and brief passed all four conditions at 1440/390 px, including archive labels, event-backed review reasons, source links and empty states.
- Codex account usage at checkpoint: 50% used / 50% remaining in reported weekly window. Check with the app usage tool at milestones. At 10% checkpoint; at 5% attempt the already-authorized Claude transfer, then stop Codex implementation only after verified transfer (or leave a recoverable handoff if access fails).

## Azure status, cost and shutdown

MCP dedicated group `rare-disease-atlas-mcp`, app `rare-atlas-mcp-1180fc`, storage `rareatlas1180fcebe2`. Functions Flex, 512 MB, no Always Ready; private Standard LRS storage. The owner explicitly approved a dedicated storage key after managed-identity role assignment was denied. Keep it only in protected server settings/transient operator memory. Never print or commit it. FTP/SCM password publishing is disabled.

`powershell -File tools/azure_mcp.ps1 status|stop|start` reports/controls MCP. `remove -ConfirmRemove` removes only its dedicated tagged group. Stop retains storage costs; removal does not affect the separate free website or shared model resource. Stop/start was tested and the service left Running. A $5 monthly Azure budget has alerts at 50/80/100%; **alerts are not a hard dollar cap**. App quotas also do not cap rejected HTTP or storage charges. See docs/operations.md and atlas_mcp/CLOUD.md.

Website deployment uses `./.venv/Scripts/python tools/deploy_website.py`, credentials held only in subprocess environment. Cloud MCP operator uses the existing Az PowerShell login; Azure CLI is absent. `npm`, network tests/deploys and Git push may require sandbox escalation. Do not create new paid resources or increase budgets while the user is away.

## Next work, in order

1. When Luna stops, run the updated offline full-run export before importing anything. A source-renderer compatibility fix preserves original quote offsets and marks omitted structured eligibility; it was checked read-only against all 10,235 then-positive candidates. Fix committed/pushed as 12a8950. The current running process remains unchanged. Do not bulk-import or start a broad paid review campaign.
2. Use [docs/demo_walkthrough.md](docs/demo_walkthrough.md) for the patient-leader story and genuine contribution/rejection/retry. Check challenge coverage and any remaining usability problems.
3. Keep background Luna within its cap, and leave a clean, recoverable repo. Its candidates still require review before family publication.
4. Independent-review readiness is documented in [docs/independent_review_readiness.md](docs/independent_review_readiness.md). Read-only Azure inventory confirmed the existing non-OpenAI option is **Phi-4-mini-instruct**, not full Phi-4. Six constructed, source-hash-verified offline challenge cases are prepared; no evaluation or model call was run, no reviewer was enrolled, and no trust label changed. A bounded evaluation allowance and representative quality assessment are still needed. All current semantic review uses Azure GPT-6 Sol; Luna screening is Azure too. Both are one model family. Different prompts or external coding assistance do not make the published claims independently reviewed.

Still missing: independently reviewed collaboration recommendations, broader professional collaborator/contact evidence, continuous funded discovery/review operations, contributor governance and systematic freshness scheduling. Cute agent presence and a family navigation assistant remain later enhancements. Broad coverage can grow through the loop, but still requires bounded spending and meaningful review; more agents alone do not establish truth.
