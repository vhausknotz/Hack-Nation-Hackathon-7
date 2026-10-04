# Parallel agent assignment: make the family journey more useful

Status: READY for the second coding agent the owner plans to start. Codex remains lead.

Read AGENTS.md, the latest HANDOFF.md and PLAN.md. The live app already has the globe and six-stop Directions. This is a bounded frontend task while the lead owns MCP hosting, ledger operations and Luna throughput.

## Deliverable

Improve the existing family journey using only the already-exported, reviewed data. Walk through STXBP1, SNAP25, progeria and a sparse-data condition. Make each stop understandable and actionable without implying eligibility, treatment transfer or independent review we do not have. Add a printable/copyable research-question brief if it improves the journey: diagnosis, relevant existing group/study links, restrictions, source dates and the unanswered questions to take to a group or researcher. It must distinguish a listing from a recommendation. Do not invent people, studies, evidence or a supported collaboration.

The owner prefers a genuinely useful product over a video-driven demo. Keep the map central and mobile usable. Cute live agent avatars and an AI navigation assistant are explicitly future work.

## Ownership and coordination

- Work in your own Git worktree/branch from current main. Do not edit the lead's active checkout.
- Own `app/src/components/DirectionsPanel.tsx`, new family-brief components alongside it, and a dedicated `tools/check_family_brief.py` if needed. Existing app types may be read; request changes in your handoff rather than editing shared pipeline contracts.
- Do not edit `atlas_mcp/`, `ledger/`, `pipeline/`, `agents/`, `enrich/`, infrastructure, shared PLAN/HANDOFF/AGENTS, or the globe/map layout components. Do not run data campaigns, write the ledger, incur model/search costs, or deploy.
- Use existing data read-only from the main checkout if ignored bundles are absent. Do not regenerate them. Install/build local app dependencies as needed.
- Record questions and decisions in `docs/agent_tasks/family_journey_parallel_report.md` in your worktree. A file in an isolated worktree is not automatically visible to the lead: give the owner its absolute path and commit hash to relay.
- Commit your scoped work. Lead will review, integrate, push main and deploy. Do not merge to main yourself. Flag any overlap before changing ownership.

## Acceptance

Build succeeds. Desktop and phone interaction checks show no overflow. Brief content preserves exact source URLs and restrictions; missing evidence stays explicit; no unsupported next-step recommendations. Document what changed, how it was checked and what is still weak. Screenshots should be local artifacts, not committed build output.
