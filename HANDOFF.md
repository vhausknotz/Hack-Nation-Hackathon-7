# Handoff: where the work stands (2026-10-04)

For the next agent picking up this repo. Read [AGENTS.md](AGENTS.md), [PLAN.md](PLAN.md) and [CHALLENGE_BRIEF.md](CHALLENGE_BRIEF.md) first. This file only covers the current state and what to do next.

## The goal, in one paragraph

A family types their diagnosis and the atlas guides them, in everyday words, through the brief's three questions:
- Who shares our characteristics?
- What useful work already exists?
- What should we do next?

The map is the product: "Google Maps for rare diseases". The owner's latest feedback is that the current side panel is very hard to understand and gives no instructions. It must become **Directions**, a guided path drawn on the map (PLAN.md section 9):
1. You are here
2. Find your people
3. You're not alone
4. What already exists
5. Your next step this week
6. What we don't know yet

Every stop is sourced. Where nothing is known, the panel says so honestly. The globe with a city-lights-at-night look comes after the panel has real content.

## Done in this session

- **Search ranking** (`app/src/lib/search.ts`, `pipeline/export_app.py`): well-documented conditions first, groups ranked lower and labeled "group of N". "progeria" now gives Hutchinson-Gilford progeria first. Pushed.
- **Trial import** (`agents/trials_import.py`): imports the trial screener's candidates (built by Codex on branch `agent/trials`) through the ledger.
  - It copies the archived ClinicalTrials.gov records, signs the claims as `agent:trial-screener`, and the kernel checks the quotes.
  - GPT-6 Sol (`agent:asset-verifier-sol`) then reviews population and asset type.
  - The v1 pilot is imported: 59 candidates, all kernel-accepted. Sol: 10 supports, 43 supports with qualification, 6 does not support (mostly wrong asset type).
- **Community scout** (`agents/communities.py`): patient organizations per condition.
  - Discovery: Luna with web search (`llm.search` in `pipeline/llm.py`, cached; the usage log counts searches). Fallbacks: Sol, then Sol from its own knowledge, because Azure sometimes refuses searches, e.g. for STXBP1. Discovery is never evidence.
  - Evidence: we fetch the organization's own page ourselves (robots.txt respected). When a site blocks bots, we use the latest Internet Archive snapshot, labeled `page_read: archived_snapshot` with its date. A snapshot is historical and does not prove the organization is active today.
  - The quote is picked deterministically, and the kernel verifies it.
  - Sol classifies the kind (`patient_organization`, `research_program`, `information_service`, `professional_network` or `company`) and the scope (`this_condition`, `this_gene` or `broader_group`). When Sol corrects the kind or scope, the scout re-proposes once with the correction. The reviewer never writes claims.
  - Schema: `represented_by` gained the qualifiers `org_type`, `scope`, `name` and `homepage` (`ledger/schema.py`). All 70 ledger tests pass.
  - Tested: SNAP25 Foundation; Progeria Research Foundation (archived snapshot); STXBP1 Foundation; ThinkGenetic correctly classed as an information service.
- **Family projection of the action layer** (`pipeline/project_actions.py`, **wired into `pipeline/export_app.py`**). `load_actions(conditions)` returns, per condition, the communities and assets the family policy accepts:
  - one kind per organization, from its newest reviewed classification (older, looser test claims lose)
  - gene-wide organizations shown on all conditions of that gene
  - each entry carries how and when its page was read
- **The export** now adds `communities` and `assets` to each condition bundle. Each neighbor row also gets `community` (its best patient organization's name), `asset_count`, `mech_known` and `sym_known`. The export has **not been re-run or deployed** since, and `app/src/lib/types.ts` doesn't have these fields yet.
- **Reviews record their prompt version:** `Ledger.review(..., prompt=)` adds it to the event payload, and all three agents pass it. Earlier reviews don't have it, and the verifier manifests still show the first prompt version, because registration is first-write-wins.
- **Plain summaries** (`pipeline/plain_summaries.py`): written and tested on 6 conditions, with good results. Examples:
  - Cystic fibrosis: "…often causes repeated lung infections and salty-tasting skin…"
  - SNAP25: "…may involve seizures, delayed speech and walking…"

  **Not yet run on all conditions**, and the export does not read `data/build/plain.jsonl` yet.
- **PLAN.md**: freshness events (reaffirmed, stale, superseded; section 2), a stale-evidence frontier task (section 7), the Directions panel (section 9), and build-order status (phase 5).

## In progress when this was written (still running at handoff)

- **Community scout run on the demo set** (background):
  - Command: `python -m agents.communities first-campaign-communities <25 pilot conditions + MONDO:0008310> --neighbors 3`
  - Receipt: `data/campaigns/first-campaign-communities.json`, written at the end.
  - If it died, re-run the same command. Everything is cached or content-addressed, so a re-run is cheap and safe.
  - The pilot condition IDs are in `../atlas-trials/data/enrichment/trials/conditions.jsonl`.
- **Do not run two ledger writers at the same time** (SQLite plus one Merkle log).

## Next steps, in order

1. **Import Codex's v2 trial candidates**, once the scout has finished: `python -m agents.trials_import --from ../atlas-trials/data/enrichment/trials/v2`.
   - These are 48 improved candidates: the SCN2A trial is recovered and the biomarker type fixed.
   - Read `../atlas-trials/enrich/trials/NOTES.md` and `comparison.md` first. The exact-name prefilter loses some broader registries.
2. **Extend `app/src/lib/types.ts`** with `communities`, `assets` and the new neighbor fields. The export side is done; see `pipeline/project_actions.py` for the entry shapes.
3. **Run `python pipeline/plain_summaries.py`** (about USD 1, Luna, 8 threads, cached). Then make `export_app.py` read `data/build/plain.jsonl` into `bundle["plain"]`. Label it in the UI as "summary written by AI from MONDO and HPO data".
4. **Directions panel** (`app/src/pages/MapPage.tsx`, `ConditionPanel`). Rules:
   - Only `patient_organization` counts as "your people".
   - `research_program` entries are listed as studies families can join. `information_service` is never shown as a community.
   - Archived pages read "archived copy from <date>; check their site for current activity".
   - Show each study's restriction ("only some patients") and Sol's one-line reason.
   - No group found: say so, show the nearest relatives that have a patient organization, and offer "help start one".
   - Keep "Show the science" for depth.
5. **Route on the map** (`app/src/components/StarMap.tsx`): a glowing path from the condition through the stops (relatives that have communities or studies), with numbered pins.
6. **Next step this week:** deterministic templates from reviewed claims, following PLAN.md section 12 (questions to ask, never medical advice). Examples:
   - "Contact <org>: ask whether their registry includes <condition>"
   - "<Study> is recruiting people with <condition>: ask your doctor whether you qualify"
7. **Docs:**
   - README and AGENTS repo layout: add `agents/communities.py`, `agents/trials_import.py`, `pipeline/project_actions.py`.
   - operations.md: web search is billed per call, roughly USD 10–35 per 1,000.
8. **Globe and night-lights redesign** of the map (see PLAN.md section 9 and the owner's notes: zoomed-out dots are ugly, huge and overlapping).
9. Later: freshness rechecks, researchers (`studied_by`), the live service and MCP (paid: ask the owner first).

After each step: `python pipeline/export_app.py`, then `cd app && npm run build`. Check the result with `tools/screenshot.py` (see AGENTS.md), then commit, push and deploy (docs/operations.md).

## Decisions waiting for the owner

- **Codex full trials run:** projected USD 30.13 against a USD 20 cap. The earlier recommendation was to run it if under USD 25.
  - Options: raise the cap to about USD 30, or run only the conditions most likely to have studies (genes with any ClinicalTrials.gov hit).
  - Codex has stopped and is waiting.
- **Community scout for all conditions:** web search is billed per call. Measure the cost on the demo set (see the receipt's `web_searches`) and ask before a full run.

## Practical notes

- **Environment:** Windows, Git Bash. Use `MSYS_NO_PATHCONV=1` for arguments starting with `/`. Long inline Python heredocs break on quotes, so write scripts to a file. Python is 3.11, so no same-type quotes nested inside f-strings.
- **Local-only data:** `data/ledger/` (the ledger, including all contributed claims and archived sources), `data/build/` and `app/public/data/` are gitignored. Campaign receipts in `data/campaigns/` are committed. Rebuilding the projection needs the local ledger.
- **Codex** works in the worktree `../atlas-trials` (branch `agent/trials`). Never modify it. Read it with `git -c safe.directory=* -C ../atlas-trials ...`.
- **Azure:** the Static Web App is on the Free tier, and Azure OpenAI is pay-per-token. `tools/azure_status.ps1` shows what is running; `tools/azure_off.ps1` switches it off.
- **The owner's preferences** (also in AGENTS.md):
  - no time estimates
  - push regularly
  - keep docs current
  - no DeepSeek
  - full ambition, not "hackathon-sized" versions
  - brief the owner clearly on what is happening and why
