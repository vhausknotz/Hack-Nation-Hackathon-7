# Report: family journey and research-question brief

Branch `agent/family-journey`, worktree `../atlas-family`, based on `3740d1f`. Scope as in `family_journey_parallel.md`. No data, ledger, pipeline, MCP, map or shared-doc files were edited. No model or search spending, no deployment.

## Owner decisions applied (relayed 2026-10-04)

1. Stop 5 is now **"Prepare your questions"**. Recorded listings are named only as things to verify ("Does this registry include this diagnosis, and is enrollment currently open?"). Each keeps its single-AI-review label and "Listed, not recommended". No suitability, benefit or enrollment recommendation.
2. The brief opens at **`?brief=1`** on the condition URL. Other query parameters are kept. Closing after opening from the panel uses history Back; closing a shared link removes only `brief` (replace). Browser Back and Escape also close it. No new route.
3. **Duplicates are not merged.** They are flagged below for Codex.
4. Study groups use **"Registry reports recruiting"**, "Registry reports not yet recruiting or by invitation", **"Recruitment status not recorded"** (kept separate) and "Registry reports not enrolling". Each card says the status is "as recorded" on the read date, and that recruiting does not mean eligibility.
5. Archived-source warnings are kept everywhere a listing appears (stop 2, questions, brief, gaps). Missing evidence reads "not yet found in the atlas", never that a resource does not exist.

## What changed

- `app/src/components/familyJourney.ts` (new): deterministic wording shared by the panel and the brief. It covers:
  - listing scope and caveats
  - study status groups and fit labels
  - eligibility-excerpt and treatment-trial notes
  - question templates
  - condition-specific gaps

  The on-screen brief and the copied text come from one model, so they cannot disagree.
- `app/src/components/DirectionsPanel.tsx`:
  - **Header:** a "Question brief" button.
  - **Stop 2:**
    - says whether a group focuses on this exact diagnosis or only serves the gene or a broader community (Devon's case)
    - labels gene-wide listings recorded on a sibling diagnosis (`via`) as unchecked for this one
    - keeps the archived warning
    - adds a "listings, not recommendations" line
  - **Stop 4:**
    - research programs, then studies grouped by registry-reported status
    - restrictions shown verbatim
    - flags when only part of the eligibility text was read
    - treatment trials say "being listed is not evidence that the treatment works or is suitable"
    - fit chip: "Record includes your condition" (was "Includes your condition", reworded to describe the record, not the family), "Only some patients" or "Ask an expert"
  - **Stop 5:** "Prepare your questions": the care-team question first, then questions for each listed group, program and study whose record doesn't report it closed. The panel shows 3; the rest are in the brief.
  - **Stop 6:** gaps specific to the condition, each with what would close it:
    - no group, or no group for this exact diagnosis
    - archived-only pages
    - no studies
    - partial eligibility excerpts
    - single-AI review only
    - no HPO symptoms, so connections rest on biology alone
    - no computed connections
    - uncurated variant effect
- `app/src/components/FamilyBrief.tsx` (new): a full-screen dialog, portalled to `body`. It contains:
  - the notice
  - the diagnosis (MONDO and HGNC links, inheritance, onset, the AI-labeled plain summary)
  - groups found
  - studies and programs found, grouped by status
  - questions, plus open questions for a group or researcher, only where the atlas found nothing
  - three computed related conditions, labeled as leads
  - gaps
  - the atlas URL and the data build date

  Copy produces plain text (clipboard API with an `execCommand` fallback). Print hides `#root` and prints the brief with URLs as text. The MONDO definition was deliberately left out: the plain summary plus the MONDO link is enough, and the long definitions buried the listings.
- `tools/check_family_brief.py` (new): the interaction and content check described below.

## How it was checked

- `npm run build` passes.
- `python tools/check_family_brief.py http://localhost:4180 <out>` passes at 1440 and 390 px for:
  - STXBP1 `MONDO:0012812` (15 listings)
  - SNAP25 `MONDO:0014590` (4)
  - HGPS `MONDO:0008310` (2, one archived)
  - sparse ARF3 `MONDO:0700366` (0 listings, 0 HPO symptoms, uncurated effect)

  For each it checks:
  - all six stops open, with no horizontal overflow on the page or in the brief
  - the copied brief contains every group's homepage, the exact source page and read date, the reviewer's reason and the archived label
  - every study's exact URL, read date, verbatim restriction and treatment note
  - "not yet found in the atlas" wording when groups or studies are missing
  - "one AI reviewer" labels
  - no banned wording (e.g. "open to join", "we recommend", "you are eligible", "does not exist")
  - print mode hides the app
  - the brief's Back button, browser Back and Escape all close it
  - a shared `?from=shared&brief=1` link keeps `from` when closed
- The existing `tools/check_directions.py` still passes at both widths (stop 5 keeps the "Prepare one question for your care team" card it asserts).
- Screenshots, copied briefs and a printed PDF were reviewed locally and not committed.

## For Codex: data issues (not changed here)

1. **Possible duplicate organization:**
   - "STXBP1 Disorders Foundation" (stxbp1disorders.org) and "STXBP1 Foundation" (stxbp1foundation.org) are two listings with the identical quote ("Welcome to the STXBP1 Foundation, a 501(c)3 …").
   - The UI shows both, and both get a question.
2. **Simons Searchlight attribution (STXBP1):**
   - The `represented_by` quote is the STXBP1 Foundation's text ("STXBP1 Foundation is dedicated to finding a cure …"), not Simons'.
   - The separate `kind_source` profile quote is Simons' own.
3. **Simons appears twice per condition:** once as a research program and once as the registry `NCT01238250`. These are possibly the same program; they are kept apart here.
4. **HGPS has no studies in the atlas.** The Progeria Research Foundation is only an archived read (2026-08-18). The UI states both as coverage gaps; worth a targeted trial/registry pass.
5. **`phase` is empty for all 60 exported assets**, so the UI doesn't show phase.

## Requests (outside my scope)

- Add `tools/check_family_brief.py` to the AGENTS.md and README command lists, next to `check_directions.py`.
- Optional export field: `via_name` (the sibling diagnosis' name) next to `via`, so the caveat can name the diagnosis the listing was recorded for.
- Before deployment, resolve items 1–2 above: the brief prints them as they are.

## Still weak

- Long lists for well-covered conditions. STXBP1 yields 11 questions, and with the duplicates above, several look alike. Grouping questions by recipient or collapsing study questions would help once identities are resolved.
- Questions repeat the full MONDO name, which is precise but heavy.
- "Registry reports …" headings assume a registry source. All current assets are ClinicalTrials.gov records, but a non-registry source would need its own wording.
- Print was checked in headless Chromium only, not in Safari or Firefox.
- On phones, opening a stop keeps the sheet's scroll position rather than scrolling to the stop's start. This is existing behaviour; I left it, since the sheet height belongs to `MapPage`.
- The atlas URL in the brief is `window.location.origin`, so local previews print `localhost`.
