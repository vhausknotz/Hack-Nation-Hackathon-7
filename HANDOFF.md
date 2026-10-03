# Handoff: where the work stands (2026-10-04)

## Lead-agent continuation (2026-10-04)

### Latest milestone

- The first Directions/globe release is **deployed** and pushed as `d233ee3`. The owner tried it and said it is clearer; continue in this direction. Keep the flat-map option.
- A second deployment (`af3755b`) now includes the reviewed v2 findings, 7,326 plain descriptions and the reviewed Simons organization profile. Static data URLs carry the build version so a normal refresh loads the new bundles. Local and live desktop/phone interaction checks passed; 101 regression tests passed.
- Deadline: **2026-10-04 15:00 Europe/Berlin**. The owner prioritizes a polished, reviewed family journey over exhaustive coverage.
- V2 trial import finished: 48 kernel-accepted, 44 supported by Sol (42 qualified), 4 rejected. Receipt: `data/campaigns/trials-trial-screen-2.json`. Newer rejected study claims must not expose an older accepted version; omitted v1 studies remain available.
- Plain descriptions: 7,326/7,328 produced, approximately USD 1.1087 in recorded Luna cost. Two use the factual fallback. The original final print failed on a blank log line after the output was already written; usage parsing now ignores blank lines and appends are serialized within a process.
- Simons Searchlight now has a kernel-checked, Sol-reviewed organization profile quoting its own explicit research-program description. At equal trust, the profile outranks condition leaf-page classifications, and its evidence is exported. Receipt: `community-profile-simons.json`.
- The original community scout **crashed on a Sol 429**, as the owner confirmed; it did not finish despite its launcher reporting zero. The repaired demo run is active again, checkpoints every condition, retries rate limits, records failures and returns nonzero if incomplete. Log: `data/build/community-resume.log`; incremental receipt: `data/campaigns/first-campaign-communities.json`. It remains the sole ledger writer while active.
- Owner approved the approximately USD 30 Luna background run. Collection and screening are running under a USD 30 configured-price cap in `data/enrichment/trials/full/`, separate from the ledger. Read `enrich/trials/README.md` for commands, logs, reservations and coverage limits. No full-run candidate is automatically accepted or published.
- The Luna deployment quota was reported by the owner as 1M TPM / 1,000 RPM; this is a ceiling, not a throughput guarantee. Use measured logs for any runtime discussion.
- Full-atlas community scouting, paid live infrastructure and broad Sol review remain separate budget decisions.

The owner has asked Codex to take over the main checkout and continue the plan, including deployment for visual feedback. The old parallel-only scope no longer applies to this lead role; `../atlas-trials` remains unchanged as the pilot archive.

- Main baseline verified: 70 ledger tests and app build passed before edits.
- Added six-stop Directions, reviewed group/study cards, eligibility and archived-source labels, conservative next-step templates, numbered map stops, an interactive night-lights globe and the original flat-map alternative.
- Added action types and optional plain summaries to export. Asset display now prefers newer reviewed evidence at equal trust, including restrictive v2 claims, without withdrawing omitted v1 findings.
- Export uses a read-only SQLite snapshot, so it can safely coexist with the scout. There must still be only one claim/review writer.
- Tests now include read-only snapshot and v1/v2 projection regressions. `tools/check_directions.py` exercises all six stops and both maps at 1440 and 390 pixels.
- The inherited scout exited before the v2 import. The repaired scout resumed only after both v2 import and Simons profile review finished. The completed plain-summary job used a separate usage log (`data/cache/plain_summary_usage.jsonl`).
- Plan sections 5 and 12 require curated or independently reviewed support for a specific next-step proposal. Single-AI-reviewed listings can be explored, but do not become recommendations to join. The fallback prepares a diagnosis-based question for the care team.
- The earlier checklist is preserved as context; completed interface items above supersede its unchecked boxes. The broad trial job and repaired demo scout remain in progress; inspect their logs and receipts before starting any replacement process.

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

## Owner feedback not yet implemented (checklist; don't lose any of it)

**The condition panel** (the owner: "very very hard to understand", "doesn't give me instructions"):
- [ ] Replace the current panel with the six-step **Directions** path above, in everyday language, with clear instructions at every step. Answer the brief's questions, not show data.
- [ ] Explain each relative in plain words: **"why this matters for you"**, not semi-technical sentences or bare scores.
- [ ] Devon's case from the brief: "here is the patient group for your exact diagnosis; if none exists, here are the closest related communities and how to help build the missing one".
- [ ] For every existing study or registry, say plainly whether it is usable: "includes your condition", "only some patients (restriction)" or "ask an expert".
- [ ] One concrete, sourced **next step this week**, and an honest **"what we don't know yet"** with what would change that.
- [ ] Never lose sight of what the family should get out of it. Technical depth belongs behind "Show the science".

**The Google Maps idea** (the owner proposed it; it fits the guided path):
- [ ] Directions drawn **on the map**: a glowing route from "you are here" through numbered stops to the next step.
- [ ] Other ideas the owner liked:
  - "Nearby" chips (communities, studies, researchers)
  - layers (symptoms vs. biology)
  - "reviews" (the evidence checks)
  - "Suggest an edit" (propose a claim)

**The map's look** (do this after the panel has real content):
- [ ] Wrap the map onto a **globe/sphere** that spins and zooms like Google Earth. Zooming into a region should feel like flying into a city.
- [ ] A **city-lights-at-night satellite look**. Each condition is a small warm light, dense clusters glow like cities, and regions read like countries with soft names.
- [ ] Fix the zoomed-out view. Today the dots are **too big, overlapping, and show no connections or structure**. Connections should arc like **flight paths**: faint everywhere, bright for the selected condition.
- [ ] Keep the zoomed-in view; the owner likes it.
- [ ] It must stay **super simple for literally anyone**, and the graph stays the focus. The 1-minute video is not a design driver.

**Data quality follow-ups from the owner's checks:**
- [ ] Simons Searchlight is classed `research_program` for one condition and `information_service` for another. The "newest classification wins" rule picks one, so confirm it's right (it's a research registry families join).
- [ ] Freshness (from the owner's other agent, now in PLAN.md section 2): recheck sources cheaply; mark claims reaffirmed, stale or superseded without overwriting history; show "last confirmed" dates.
- [ ] Archived organization pages must always read as historical, never as proof the group is active today.

**How to work with the owner:** clear briefings at each milestone (what, why, where we stand, what's next, open decisions). Keep to the agreed order, or say why you're changing it.

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
