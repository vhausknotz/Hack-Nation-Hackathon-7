# Bounded review and publication cycle

**Live pilot completed:** both STXBP1/SYNGAP1 corrections were kernel-accepted,
Sol-supported and published to the MCP and website. All desktop/phone and live
checks passed. An unchanged rerun retained two reservations and made no new model
call or publication. Receipt: `data/campaigns/mcp-shared-study-result.json`.
The initial oversized quotes were rejected before any paid review and remain in
history. The corrected review calls used 4,587 input and 370 output tokens total.
The two-attempt allowance is now exhausted; do not reset it to authorize more work.

The authenticated MCP gateway accepts contributions but never calls paid models.
`tools/run_contribution_cycle.py` is a separate, explicitly started local operator
runner. One invocation drains up to 25 signed submissions, reviews only approved
study claims, and publishes the resulting read views after checks. It does not
automatically discover evidence or run a broad campaign. The computer and local
preview on port 4173 must be running for website checks.

## Pilot plan and commands

`data/campaigns/mcp-study-cycle-plan.json` allows only the enrolled lead contributor,
two named STXBP1/SYNGAP1 condition-study pairs, and **two lifetime Sol attempts**.
The operator approves the plan locally; public callers cannot select it or change
its allowance. Other submissions can pass through the deterministic kernel but
do not trigger paid review. No external reviewer independence is claimed.

```powershell
# Source inspection is read-only with respect to the evidence ledger.
./.venv/Scripts/python tools/mcp_complete_shared_study.py inspect
# After inspecting its actual official record, submit the two scoped claims.
./.venv/Scripts/python tools/mcp_complete_shared_study.py submit
# Commit tested code before running publication; a dirty repo blocks publication.
./.venv/Scripts/python tools/run_contribution_cycle.py --plan data/campaigns/mcp-study-cycle-plan.json --state data/contributions/shared-study-cycle
```

Run the exact same cycle command to resume after interruption. Do not delete its
state directory, duplicate it, or change the plan to reset spending. Its receipt
is `data/contributions/shared-study-cycle/receipt.json`; it records reservations,
judgments, attestation progress and each publication stage. Keep it with the
local ledger and intake state. A separate OS lease prevents duplicate cycles;
the ledger writer lease excludes concurrent imports, drains and reviews. During
publication that writer lease keeps the exported view and cloud snapshot on one
ledger revision. Intake remains available.

## Cost and failure behavior

- Only kernel-accepted, still-unreviewed, explicitly allowed MCP `has_asset`
  claims from one exact official ClinicalTrials.gov source are eligible.
- Archive hashes are rechecked. Oversized source records are deferred, never
  truncated to fit review. The source limit is 32 KB, serialized model input
  limit 40 KB and output limit 4,000 tokens per attempt.
- Sol responses use the normal on-disk cache and token log. SDK retries are
  disabled. A timeout, malformed response or interruption retains its allowance;
  the next invocation does not silently send another paid request.
- A saved judgment can be attested after a crash without calling Sol again.
  Recorded reviews are not overwritten or repeated. Rejections stay visible to
  contributors and are excluded by the normal family projection.
- Two calls with fixed input/output bounds are a usage bound, **not a dollar
  spending cap**. Sol pricing is not configured in the older shared token logger;
  do not label its missing dollar estimate as free. This narrow pilot uses the
  owner's existing bounded-review approval; broader plans require another budget.
- Publication checkpoints export, frontend build, browser checks, cloud snapshot,
  website deployment and live checks. A failure leaves its stage pending; retry
  resumes there. Network side effects may be repeated if their successful reply
  was lost. Cloud snapshots use an atomic pointer and website deployment is
  replayable. A new signed ledger revision, tracked runtime/configuration change or changed generated graph input restarts publication checks. Operator documentation/checkpoint edits alone do not.

No recurring operator service is installed by this command. The lead can invoke
it from the already-authorized temporary continuation workflow. Stopping the
runner stops further paid attempts; hosted intake continues. Cloud status/off
commands remain `powershell -File tools/azure_mcp.ps1 status` and `stop`.

## Remaining work

This proves a bounded contribution-to-publication cycle, not an unattended
general research organization. Independent model-family review, funding/admission
for other contributors, continuous discovery and freshness scheduling still need
their own policies and evaluation. The website's shared-study cards are questions
to investigate, not independently reviewed partnership recommendations.

## Publication input fingerprint

The revision now combines the signed ledger head with `atlas_mcp/publication_inputs.py`'s content fingerprint. It includes tracked runtime/configuration files and the exact generated input files read by the app exporter (including the optional plain descriptions and source manifest). Cloud-only publication needs only the conditions input. Operator Markdown and documentation/checkpoint/evaluation folders are excluded; app content stays included. A missing required input or a file changing while it is hashed stops the cycle. The existing dirty-repository gate remains.

This avoids uploading another full cloud snapshot for a handoff edit, and detects ignored graph rebuilds even when Git HEAD is unchanged. The first run after switching from the old HEAD-only revision will perform a fresh checked publication. Never edit a receipt to pretend that publication has already happened. Add newly introduced external build inputs to the fingerprint list. Generated inputs must stay stable through publication; the ledger writer lease does not lock a separately launched graph-builder process.
