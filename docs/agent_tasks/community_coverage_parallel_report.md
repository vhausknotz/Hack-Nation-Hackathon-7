# Report: community coverage candidates (coverage-v1)

Branch `agent/community-coverage`, worktree `../atlas-community`, based on `86062c9` plus the delivered family commit `2b2f5b3` (merge `42f269e`). Scope as in `community_coverage_parallel.md`. Nothing here touched the production ledger, `agents/communities.py`, the app, shared docs, infrastructure or any paid API. Research used web search and direct reading of each organization's own page.

**Everything below is a proposal.** I chose the quotes and made the scope calls myself; no candidate has been reviewed by anyone else, and none is labeled independently reviewed.

## Result in one view

| | |
|---|---|
| Conditions investigated | 20 (10 recognizable diagnoses not among the 62 scouted; 10 gaps among the 62 scouted) |
| Candidates staged | **14**, across 14 conditions, from **12 distinct organizations** (DEEP covers three conditions) |
| Unresolved gaps | 6 (CNKSR2, EA5, STX1B, BANF1 progeria, CACNA1B, UNC13A), each with what was searched and why it stopped |
| Source failures | 0 among the 12 pages staged. Failed or unusable pages met while researching are listed under "Retrieval problems" |
| Mechanical proof | all 14 pass the **real kernel** in a throwaway ledger; every hash and quote offset reproduces from the local archive |
| Tests | 8 offline tests (`python -m pytest agents/community_coverage`) |

Before choosing, I checked all 20 conditions against the current ledger projection (44 conditions with a patient organization) and the scout receipt: none of the 20 is covered, and the ten "scouted" ones are exactly those the receipt lists with no surviving patient group.

## Candidates

Tier A: the organization's own page says it works for people with this condition, and the quote carries that. Tier B: a real remit, but the scope needs a reviewer's judgment (named in the caveat).

| Tier | Condition | Organization | Kind / scope | What the page shows | Caveat |
|---|---|---|---|---|---|
| A | MECP2-related Rett syndrome `MONDO:0010726` | International Rett Syndrome Foundation, rettsyndrome.org | patient_organization / this_condition | Calls itself the research, family support and advocacy organization for Rett syndrome; names MECP2 as the cause | none significant |
| A | DMD-related Duchenne muscular dystrophy `MONDO:0010679` | Parent Project Muscular Dystrophy, parentprojectmd.org | patient_organization / this_condition | "demand optimal care for every single family" in the fight "to end Duchenne" | Its Duchenne Registry is a separate research listing |
| A | FMR1-related fragile X syndrome `MONDO:0010383` | National Fragile X Foundation, fragilex.org | patient_organization / this_condition | "Empowering families living with Fragile X" | Page also covers FXTAS and FXPOI |
| A | TSC1-related tuberous sclerosis `MONDO:0008612` | TSC Alliance, tscalliance.org | patient_organization / this_condition | Mission for "everyone affected by tuberous sclerosis complex" | Names the complex, not TSC1. TSC2 (`MONDO:0013199`) has the same remit and was not staged separately |
| A | Phelan-McDermid syndrome due to SHANK3 mutation `MONDO:0971069` | Phelan-McDermid Syndrome Foundation, pmsf.org | patient_organization / this_condition | "everyone living with Phelan-McDermid syndrome"; "Families supporting families is the driving force" | Names the syndrome, not the SHANK3 subtype |
| A | PURA-related intellectual disability `MONDO:0014512` | PURA Syndrome Foundation, purasyndrome.org | patient_organization / this_gene | Mission to "connect, educate, serve, and empower families impacted by PURA Syndrome" | The atlas has a second PURA condition (`MONDO:0017811`) the same listing would serve |
| A | ATP7A-related Menkes disease `MONDO:0010651` | The Menkes Foundation, themenkesfoundation.org | patient_organization / this_condition | Run by a family; offers "comfort and support to families with a child" with Menkes | Mission page is undated, postal address only: activity unconfirmed |
| A | FXN-related Friedreich ataxia `MONDO:0100340` | Friedreich's Ataxia Research Alliance, curefa.org | patient_organization / this_condition | "The FA Community is an active and supportive one"; funds research on FA | Frames itself as a research funder; a reviewer may prefer another kind |
| B | Angelman syndrome due to a point mutation `MONDO:0018461` | Angelman Syndrome Foundation, angelman.org | patient_organization / this_condition | "committed to supporting families" for Angelman syndrome | The atlas condition is the UBE3A point-mutation form; the page never names UBE3A, so scope may be better stated as broader |
| B | Neurofibromatosis type 1 `MONDO:0018208` | Children's Tumor Foundation, ctf.org | patient_organization / broader_group | Names NF1 within the NF conditions it serves; runs a clinic network and an NF registry | Remit is all NF; strong drug-discovery framing; registry is separate |
| B | SYNE1-related AMC `MONDO:0017892` | AMC Strong, amcsupport.org | patient_organization / broader_group | Supports families affected by arthrogryposis multiplex congenita, "over 500 known variations" | Never names SYNE1; the link is that this condition is AMC |
| B | DEE 62 (SCN3A) `MONDO:0033371`; DEE 103 (KCNC2) `MONDO:0030957`; DEE 63 (CPLX1) `MONDO:0033372` | DEEP, dee-p.org | patient_organization / broader_group | A patient advocacy organization for developmental epileptic encephalopathies, "serving Families" | Never names these genes; the remit is DEEs as a class. The page also covers SNIs, outside these conditions. The quote is the page title line plus one sentence, the weakest evidence in the package |

Full rationale, caveats and the exact quotes with offsets are in `candidates.jsonl`.

## Unresolved gaps and what was found

| Condition | Searched | Finding |
|---|---|---|
| CNKSR2-related ID with epilepsy `MONDO:0030909` | two web searches; cnksr2.org (does not resolve); the Rareshare CNKSR2 page | A 2021 cohort paper (PMC8281706) thanks an "international CNKSR2 Family Support Group", so a group very likely exists, but I found no official site. Rareshare is a platform forum, and humandiseasegenes.nl is an information service; both rejected. **Best lead for a human:** ask the paper's authors. |
| Episodic ataxia type 5 `MONDO:0013464` | two web searches; ataxia.org | The National Ataxia Foundation very likely serves it, but its episodic ataxia page redirects to a **PDF** that lists EA1 to EA8. Our archive handles HTML only. Promising but unproven. |
| STX1B-related GEFS+ `MONDO:0014517` | one web search | Literature only (49 patients, 23 families). The engine suggested the STXBP1 Foundation, which is a different gene. |
| BANF1-related Nestor-Guillermo progeria `MONDO:0013523` | one web search | Reference pages only (NORD, GARD, Orphanet). The Progeria Research Foundation's live site returns 403 to automated visitors, so I did not read it for any mention of progeroid syndromes. Worth one question to the foundation. |
| CACNA1B-related disorder `MONDO:0032784` | one web search | Literature only; a handful of families reported. |
| UNC13A-related disorder with epilepsy `MONDO:0980940` | one web search | About 50 patients reported in a 2025 paper; no family organization found. ALS organizations were deliberately **not** used: they serve ALS, a different condition. The sibling `MONDO:0980941` was not separately searched; the same reasoning applies. |

Rejected during search, kept so they are not rediscovered: FamilieSCN2A Foundation and International SCN8A Alliance (wrong gene for SCN3A), KCNA2 Epilepsy (wrong gene for KCNC2), STXBP1 Foundation (wrong gene for STX1B), Rareshare, Human Disease Genes, ALS/MND organizations (for UNC13A).

## Reproduce and import

Everything is under `data/community_candidates/coverage-v1/`:

- `spec.json`: my research input (conditions, why chosen, searched, rejected, candidates, chosen quotes)
- `candidates.jsonl`: 14 candidates, each a `represented_by` assertion with evidence carrying source id, verbatim quote, offsets and URLs, plus rationale and caveats
- `retrievals.jsonl`: each page read: requested URL, redirect hops, final URL, UTC time, status
- `manifest.json`: candidate to source, source to file paths and hashes, per-condition outcome, failures
- `archive/`: **local only, gitignored** (verification-only copies of organization pages). Absolute path: `C:\Users\valen\Documents\ETH Zürich\Random Coding stuff\Hack-Nation Hackathon 7\atlas-community\data\community_candidates\coverage-v1\archive` (24 files). It holds exactly the pages the manifest names, in the ledger layout (`raw/<sha>.bin`, `text/<sha>.txt`).

```
# from the worktree root, with the main checkout's .venv
python -m agents.community_coverage.stage --verify   # recompute every hash and re-check every quote offset
python -m agents.community_coverage.dry_run          # the real kernel in a throwaway ledger: 14/14 accepted
python -m agents.community_coverage.stage            # re-fetch and rebuild (live pages may have changed; the archive is the record)
```

To import, in this order:
1. Copy `archive/raw/*` and `archive/text/*` into the ledger's `data/ledger/sources/raw` and `text` (same layout, content-addressed).
2. For each entry in `manifest.json["sources"]`: `ledger.add_source(Source(**entry["source"]), signer)`.
3. For each candidate: build `claim = {assertion, evidence, provenance}` from the file, with provenance from `provenance_proposal` plus `created`. Signing as `agent:coverage-research-claude` is only a proposal; use whichever identity you enroll. `evidence` items carry `url`, `page_read` (live) and `page_date` as the existing scout does, and an extra `supports` tag you can drop. Then `ledger.propose(...)` and send for review.
4. Only one ledger writer at a time (see AGENTS.md); the dry run never opens `data/ledger`.

Sources are organization websites kept for verification (`redistributable=false`); only metadata and short quotes are committed.

## How the current scout misses groups

I ran the existing scout's own deterministic helpers (`term_patterns`, `find_quote`) offline over the 12 archived pages. Nothing from `agents/communities.py` was edited.

1. **A bug silently drops pages that do name the condition.** In `find_quote`, `best_score` starts at `-1`, but a line's score is `10 × organization-words − |length − 160| / 40`. A matching line with no organization word and length more than about 40 characters from 160 scores below `-1` and is never chosen. Example: the Children's Tumor Foundation page (`MONDO:0018208`) has a matching line "NF refers to a group of genetic conditions … NF1 …" of 387 characters; the scout returns no quote and counts it as `dropped_page_does_not_name_condition`, though the page names NF1 three times. Starting at `float("-inf")` recovers it. This affects any page whose best sentence is descriptive rather than mission-like.
2. **The chosen quote is often not decision-carrying.** Scoring rewards words like "foundation", "families" and "research", not statements about whom the group serves. Run on these pages it would quote:
   - Angelman: a press-release headline, "Simplicity's Protected Tomorrows® and Angelman Syndrome Foundation Partner to Support Families with Compassionate Planning"
   - Fragile X: a family story, "Ilana and Adam are dedicated to advocacy as they champion for their teenage son…"
   - Duchenne: a fundraising event description ("Race to End Duchenne is … signature program that raises funds…")

   The reviewer then judges a quote that never says who the group serves. Suggested fix: prefer sentences in which the organization is the grammatical subject of a serve/support/represent verb, and demote news and testimonial blocks.
3. **Class-level remits are dropped.** DEEP (three DEE conditions) and AMC Strong (SYNE1-related AMC) are legitimate broader communities, but their pages never name the gene or the MONDO name, so `term_patterns` finds nothing and the page is dropped before review. Suggested fix: when the condition belongs to a named class (DEE, AMC, NF), let discovery propose the class term as an additional pattern and mark the scope `broader_group` for reviewer judgment, never inferred silently.
4. **Alias normalization.** Friedreich ataxia is missed because the page says "Friedreich’s ataxia" (possessive, curly apostrophe) while the atlas names are "Friedreich ataxia 1" / "FRDA1"; the gene symbol FXN is not on the page. Suggested fix: normalize possessives and apostrophes, and also try names with trailing type numbers removed.
5. **Look-alike symbols in search results.** Searches for KCNC2 returned KCNA2 Epilepsy, STX1B returned the STXBP1 Foundation, and SCN3A returned SCN2A and SCN8A groups. The word-boundary gene pattern would reject those pages at the quote step, but each costs a fetch and review slot. Suggested fix: tell the discovery prompt to return only exact symbol matches, and drop candidates whose page text lacks the exact symbol before fetching more.
6. **Coverage is mostly a scouting-order gap, not a discovery failure.** The scout expanded around the SNARE neighborhood and nearest relatives. All 10 diagnoses I tried outside it (PURA is the least recognizable) had an official organization whose own page names them. This is biased: I picked diagnoses I expected to have one. Still, scouting by recognizability and phenotype count before neighbor expansion looks like the cheapest coverage gain.

## Retrieval problems met while researching

- **PDF only:** NAF's episodic ataxia page (see EA5). The scout and my fetcher archive HTML only.
- **Bot-blocked (HTTP 403):** progeriaresearch.org and cff.org. The existing Internet Archive fallback exists for this; I did not use it, to keep this package to live reads.
- **Empty after text extraction:** rarex.org returned a 200 page with no extractable text (script-rendered), so it could not be quoted. RARE-X already appears in the ledger from earlier campaign pages.
- **Does not resolve:** cnksr2.org, deepconnections.org, decodingdevelopmentalepilepsies.org.
- **Redirects recorded:** www.angelman.org to angelman.org, www.amcsupport.org to amcsupport.org. Domain aliases such as the two STXBP1 foundations are not detectable from the host-based `org_id`; my fetcher records the final URL and redirect hops so the lead can build alias evidence, but it does not read `rel=canonical`.

## What is still weak

- One AI chose every quote and scope. A second pair of eyes on the Tier B scope calls matters most.
- Evidence is mostly homepages, which are decision-carrying but change; the archive is the record, and each retrieval time is in `retrievals.jsonl` (all 2026-10-04, between 01:25:00 and 01:25:24 UTC).
- Activity is unconfirmed beyond the page being live; the Menkes Foundation in particular looks small and undated.
- DEEP's evidence is a title line and a one-sentence statement. A leaf page describing its remit in prose would be better.
- Only 20 conditions, one search pass each for the gaps. The negatives mean "not found by this pass", never "does not exist".

## Requests for the lead (outside my scope)

- Decide whether to fix the `find_quote` initial score and the quote-selection preference above in `agents/communities.py`; I did not touch it.
- Add `agents/community_coverage/` and its test command to AGENTS.md and the README test line if you keep it.
- Consider PDF support in `ledger.sources` (media type `pdf_text`) so documents like the NAF page can be archived with offsets.
