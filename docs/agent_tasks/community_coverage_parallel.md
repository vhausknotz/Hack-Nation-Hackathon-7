# Parallel assignment: useful, source-backed community coverage

Status: READY for the owner's second coding agent, after delivery of family journey commit `2b2f5b3`. Codex remains lead and integrates/deploys both deliverables.

## Why this matters

The completed scout covered 62 conditions. Current reviewed data has patient groups for 44 of 7,328 atlas conditions (39 of the 62 scouted conditions). Most empty panels reflect missing research coverage, not proof that no community exists. The lead is integrating your family journey, correcting evidence/organization identity, and deploying MCP. Help fill real community gaps in parallel.

Read AGENTS.md, HANDOFF.md, PLAN.md and `docs/agent_tasks/community_data_audit.md`. Start from freshly fetched main in your own worktree/branch, retaining your delivered family commit. The lead has strengthened the community reviewer prompt and corrected Simons/STXBP1; do not restore the old prompt or duplicate that correction.

## Deliverable

1. Inspect the completed scout receipt and existing reviewed projection read-only. Choose up to 20 currently uncovered conditions, prioritizing recognizable diagnoses, gaps among the 62 scouted conditions, and a few underserved rare examples. Record why each was chosen. Do not assume a group exists for every condition.
2. Research official organization pages with the available browser/search tools. Distinguish patient organizations from research programs, information services, companies and professional networks. Find evidence of whom the organization serves; a gene mention alone is insufficient. A broader community is useful only when its actual remit covers this diagnosis and the scope is stated honestly. Do not infer ALS membership for UNC13A developmental disorders.
3. Save an importable candidate package under `data/community_candidates/coverage-v1/` and a report. Each candidate needs condition ID, proposed organization ID/name/type/scope, original and final official URL, UTC retrieval time, redirect history if available, a verbatim decision-carrying quote with character offsets, and the archived source bytes/text needed to reproduce the quote and content hash. Use existing `ledger.sources` conventions on an isolated staging directory where practical. Include a manifest mapping files to candidates and retain retrieval failures/gaps. Observe site terms/robots and avoid redistributing restricted full pages: locally archive them and commit only metadata/short excerpts when permitted; give the lead the local archive path.
4. Report useful ways the current discovery/quote selection misses groups, with specific examples and suggested fixes. Pure discovery helpers/tests may be added as NEW files under `agents/community_coverage/`; do not edit the active `agents/communities.py` or shared contracts. Tests should use saved fixtures/mocks, not paid APIs.

## Ownership and limits

- Own the new candidate package, `agents/community_coverage/` if needed, and `docs/agent_tasks/community_coverage_parallel_report.md` only. Do not change the previously delivered UI while the lead integrates it.
- Do not write to the production ledger, invoke existing campaigns, regenerate app data, run Azure models/paid search APIs, modify infrastructure/MCP/shared docs, or deploy. Existing web research tools are fine; no new spending commitment is authorized by this task.
- Candidate findings are proposals, not accepted evidence. The lead will import through the kernel and review before publishing. Do not label your own research independently reviewed.
- Preserve provenance and negative findings. Do not pad coverage with generic directories or invent a useful connection. Public organizational contacts only; no patient information.
- Commit scoped changes, then give the owner your absolute report path and commit hash to relay. Include local-only source archive paths and clear reproduction/import instructions. Do not merge into main yourself.

## Acceptance

The lead can locate every source, mechanically reproduce every quote/hash, tell why each group serves the stated condition, and distinguish promising candidates from unresolved gaps. Report conditions investigated, candidates found, source failures, and any ambiguity. A smaller strong package is preferable to 20 unsupported listings.
