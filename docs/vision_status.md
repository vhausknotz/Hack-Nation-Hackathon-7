# Whole-product status and remaining vision

Checked 2026-10-04 06:10 UTC against PLAN.md, CHALLENGE_BRIEF.md, HANDOFF.md and MCP implementation notes. This is the implementation-status companion to PLAN.md. Planned architecture must not be read as already implemented.

The owner has returned and requested this overview and a manual Claude Code handoff, **not more implementation yet**. Codex has stopped implementation; the nap automation is paused. Claude has not been contacted. Resume on the owner's instruction and record ownership in HANDOFF.md.

## What the finished vision means

A patient-group leader moves from an exact diagnosis to an explained biological connection, useful existing work, a responsible collaborator and a source-backed next research step. Families find community and understand uncertainty. Underneath, enrolled outside agents discover missing evidence, contribute, review and challenge it, and improve the published atlas under explicit trust and spending rules. It keeps working as sources change, beyond rehearsed examples.

The challenge asks for one complete defensible journey, not every long-term platform feature. The owner nevertheless wants continued progress toward the ambitious product, not a declaration that a demo is the finished vision. Breadth remains secondary to usefulness and a sound contribution loop.

## Built versus missing

| Area | Built and verified | Remaining to reach the vision |
|---|---|---|
| Understand a diagnosis | 7,328-condition graph; search; globe/flat map; explained neighbors, look-alikes, summaries and science pages | Richer variant-specific evidence and context; stronger validation of mechanistic connections. Many conditions lack symptoms or variant-effect data. Computed neighbors are not validated reusable research routes. |
| Find community | Reviewed groups, scope/archived-source labels; 57 conditions with groups; exact/gene/broader distinctions | Useful evidence-qualified fallback routes when no exact group exists; help establishing a missing community; current activity, language, geography and contacts where useful. Broad coverage remains unfinished. |
| Find reusable work | Registries/studies with restrictions; shared-record routes SNAP25/STXBP1 and STXBP1/SYNGAP1; 77 conditions with listings | Richer models, assays, biomarkers, outcome measures, biobanks, protocols and funded programs. Sharing a study ID does not prove that a design transfers between diseases. |
| Find collaborators and act | Focused study-team questions with both diagnoses' evidence; copy/print brief | Named investigators/institutions, verified public professional contact routes, what can actually be reused, what differs and the next validation step. Researcher discovery and reviewed proposal generation remain incomplete. Current questions are descriptive leads, not independently reviewed partnership recommendations. No outreach or partnership confirmed. |
| Independent review | Kernel, Sol review, contributor/model identities and tested independence policies | Actual qualified second-family or human review. Current semantic reviews all use Azure Sol; Luna and Sol share a family. Phi-4-mini-instruct is deployed but untested. Six offline test cases are prepared, not run, and insufficient alone for general validation. Evaluation/additional reviews need bounded approval. |
| Contradictions/corrections | Evidence history, MCP challenges/counter-claims; redaction repair; family export guard | Family UI showing both sides and review status, excluding contested action leads; handling already-deployed disputed content. Guard blocks new exports, not old live content. Production has zero challenges; test with synthetic fixtures, never fake production disputes. |
| Outside-agent contribution | Hosted authenticated MCP, 13 tools, enrolled identities, signed durable intake, task leases/quotas, validation/reviews/challenges and receipts | Smooth onboarding/fresh-client walkthrough; more sources and contribution types. MCP fetch currently supports official PubMed and ClinicalTrials.gov records, not arbitrary sites or new organization-page fetching. Endpoint availability alone does not enable every research task. |
| Automated improvement | Real contribution -> kernel -> Sol -> export/build/tests -> cloud/site publication; lifetime reservations and retry protection | Continuous discovery/review scheduling and unattended operation beyond pinned plans. Worker is local. Full impact/uncertainty/feasibility/campaign frontier ranking is unfinished; initial frontier covers thin phenotypes and reviews. Recovery, backup/restore, migration and monitoring need operational hardening. No cloud ledger worker or PostgreSQL service exists. |
| Freshness | Archived sources/hashes, dates and historical labels | Scheduled change detection and reaffirmed/stale/superseded events through publication/UI; retraction checks and stale-evidence handling. Dates alone do not keep evidence current. |
| Researcher/contributor UI | Science pages, MCP histories, task/activity APIs | Full task board/dashboard, track record, evidence/trust filters, convenient export/replay views. Listing histories exist; site-wide live feed and map replay do not. |
| Sustainable platform | Enrollment, quotas, no-self-review, bounded review budgets; gateway cannot start paid model calls | Outcome-based reputation, earned quotas, moderation/appeals, reviewer community, funded review allocation, campaign sponsorship/payments and public receipts as a complete product. Declared model identity is not cryptographic attestation. |
| Future UX | Night-lights globe and real activity IDs | Cute role-specific agents, expiring presence/subtle pings and accepted-work links; family navigation assistant grounded in reviewed evidence. These remain planned; never simulate research activity. |
| Real-world validation | Desktop/phone/source-fidelity/copy/print/motion checks; 171 backend/storage tests | Patient-leader/researcher usability feedback, expert assessment of reuse, broader browser/accessibility checks and measured usefulness. No measured 10x or clinical acceleration. |
| Submission | Live prototype, README, reproducible checks, silent 55-second demo and narration draft | Owner walkthrough, narration/team introduction/final video, judge access to private repository, actual form requirements and submission confirmation. Nothing submitted. |

## Recommended next order when the owner resumes implementation

1. **Complete the human collaboration path.** In one supported neighborhood, name the responsible organization/investigator and verified professional contact route. Show the shared asset, unproven reuse assumptions and a focused question/validation step. Preserve sources and restrictions. This directly advances the challenge.
2. **Finish the family dispute view.** Keep the guard until synthetic end-to-end tests show both sides, distinguish pending objections from reviewed disputes and exclude contested ordinary action leads. Do not let edge-case work displace all patient-facing progress.
3. **Make an outside agent's workflow reproducible.** Fresh-client enrollment, task claiming, supported-source fetch, rejection/retry, explicit review/publication and receipts. Do not bypass enrollment or permit public submissions to spend the owner's money.
4. **Evaluate independent review if a bounded allowance is approved.** Representative positive/negative cases; do not enroll an unreliable reviewer to obtain the label. No DeepSeek. Human review is another route.
5. **Add bounded freshness and unattended scheduling**, with approval for any additional operating costs/resources. Reuse leases, reservations and signed snapshots rather than duplicate jobs.
6. **Expand useful assets/contact coverage and visibility of real agent work.** Prioritize saved candidates; campaigns/governance UI and navigation assistant remain separate later milestones.

Submission preparation can proceed alongside improvements. This does not mean the product is finished. No task duration estimates are implied. Deadline: 2026-10-04 15:00 Europe/Berlin.

## Operating facts to preserve

- Website `280649f`; cloud snapshot `published/ca91ebc00e9b434fa4545d46477be2a7`. Commands/receipts in HANDOFF.md. Docs do not require deployment.
- Luna stopped on a non-transient BadRequestError: 93,203 decisions, 11,926 unreviewed candidates across 1,800 conditions. Configured-price accounting: $26.776087 measured + $0.7106966 uncertain reservation under $30. Mechanical audit is not semantic review. Diagnose before resume; no blind retry/reset.
- Contribution cycle's two review attempts are exhausted. Never clone/reset state to obtain more. Additional paid review needs bounded approval; existing resource authorization does not authorize new resources/campaign expansion.
- No active screening/ledger writer at checkpoint; recheck before starting. One writer only. Preserve ignored ledger, keys, archives, reservations and receipts; a Git clone alone does not restore them.
- MCP uses the expressly approved dedicated storage key/private storage. Never print keys. $5/month Azure alerts are not a hard cap. Status/stop/start and retained storage costs are documented in HANDOFF.md and docs/operations.md.
- Demo is local-only: `data/build/demo/20261004-050141/atlas-walkthrough-silent.webm`.
- Repo remains private. Owner decides judge access; this handoff does not authorize visibility changes.

## Manual handoff prompt

> Read AGENTS.md, HANDOFF.md, docs/vision_status.md, PLAN.md and CHALLENGE_BRIEF.md in Hack-Nation-Hackathon-7. Codex stopped implementation and paused its nap automation; I am manually handing lead work to you. Confirm repo state, local ignored data, active jobs and ownership. Preserve the working family UI, evidence rules, one-writer lease and budgets. The full vision and next-order proposal are in docs/vision_status.md; distinguish implemented infrastructure from planned features. Do not restart Luna or exceed bounded spending approvals. Continue the work I authorize, commit/push verified milestones and keep the handoff current.
