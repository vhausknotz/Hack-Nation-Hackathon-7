# Task: ClinicalTrials.gov enrichment (genesis run, part 1)

Read [README.md](README.md) (rules for parallel agents) and [AGENTS.md](../../AGENTS.md) first.

## Goal

For every condition in the atlas, find the ClinicalTrials.gov studies that are actually about it and classify what each study offers a patient community:
- a registry
- a natural history study
- an interventional trial (with modality)
- a biomarker study
- an outcome-measure study
- or nothing relevant

Output **candidate claims** that the main agent loads into the ledger. Each claim says *condition `has_asset` NCT…*, with the study's type and a verbatim quote from the study record that shows its relevance.

Why it matters: this fills the "What already exists" answer for families. Keyword search alone is badly noisy: a "SNAP25" search returns Botox and Alzheimer's trials, and "NSF" returns the National Science Foundation. That's why each candidate needs a relevance judgment.

## Your folders (the only places you write)

- `enrich/trials/` for code, `NOTES.md` and a short `README.md`
- `data/enrichment/trials/` for outputs (gitignored; add the line to `.gitignore` in your branch)

## Setup in a separate worktree

- **Data:** gitignored data (`data/raw/`, `data/build/`) isn't in a fresh worktree. Either rebuild it with `pipeline/download.py` then `pipeline/build_graph.py`, or read it, strictly read-only, from the main checkout at `../Hack-Nation-Hackathon-7/data/`.
- **Python:** use the main checkout's environment, `../Hack-Nation-Hackathon-7/.venv/Scripts/python`.
- **Archived texts:** archive study texts into `data/enrichment/trials/archive/` (pass `root=` to `ledger.sources.archive`). The main agent copies them into the ledger archive on import.

## Inputs (read-only)

- `data/build/conditions.jsonl`: one condition per line. Use `id`, `name`, `also_known_as`, `gene.symbol`, `disease_name`, `synthetic`. Rebuild with `pipeline/build_graph.py` if missing.
- `pipeline/sources/clinicaltrials.py`: an API v2 client. Extend it in your own module rather than editing it; you'll need more fields, e.g. `whyStopped`, keywords, `briefSummary`.
- `pipeline/http_cache.py`: cached, throttled HTTP.
- `pipeline/llm.py`: cached model calls with token logging. Use `gpt-6-luna` for screening.
- `ledger/schema.py`: `make_claim`, predicate `has_asset`, qualifiers `asset_type` and `status`, evidence type `trial_record`.
- `ledger/sources.py` and `ledger/canonical.py`: archiving and quote helpers.

## Steps

1. **Candidate studies per condition.**
   - Query by gene symbol (`query.term=<SYMBOL>`) and by the condition's main names (`query.cond=<name>`).
   - Skip names shorter than 6 characters and generic names.
   - Deduplicate by NCT ID, and cache everything.
2. **Render each study as canonical text.** Write a deterministic renderer: "Title: … / Conditions: … / Keywords: … / Summary: … / Eligibility: … / Interventions: … / Status: … / Why stopped: …". Archive it with `ledger.sources.archive(raw=<rendered UTF-8 bytes>, url=<study URL>, media_type="text", license="ClinicalTrials.gov (public domain)", redistributable=True, root=data/enrichment/trials/archive)`. Write the returned `Source` records to `sources.jsonl`, so the main agent can register them.
3. **Screening with Luna:** one call per (condition, study) pair, or small batches. Return JSON with:
   - `relevance`: `direct` / `includes_this_condition` / `not_relevant`
   - `asset_type`: one of the schema's `asset_type` values
   - `modality` (for trials): small molecule, gene therapy, ASO, …
   - `quote`: a short verbatim passage from the rendered text that shows the relevance
   - `reason`

   Version the prompt (`trial-screen@1`). Ask the model to say `not_relevant` whenever the condition or gene is only mentioned incidentally.
4. **Check quotes mechanically** with `ledger.canonical.find_quote(text, quote)`. Drop any candidate whose quote isn't found, and count the drops.
5. **Write candidate claims** (relevant ones only) with `ledger.schema.make_claim(condition_id, "has_asset", nct_id, evidence=[{"type": "trial_record", "source_id", "quote", "start", "end"}], provenance={"contributor": "agent:trial-screener", "agent": "trial-screener", "model": "gpt-6-luna", "prompt": "trial-screen@1", "created": <ISO time>}, asset_type=…, status=<overall status>)`.

## Pilot first, then scale

- **Pilot:** run on the first campaign's genes:
  - STXBP1, SNAP25, STX1B, VAMP2, SYT1, CPLX1, UNC13A, NSF
  - SLC6A1, SYNGAP1, SCN2A, CACNA1A, STXBP2, GABRA1, GABRB3, GABRG2
- **Show a review sample:** write `data/enrichment/trials/pilot_review.md` with 30 random decisions (relevant and not), each with condition, study title, decision, quote and reason. This is checked before scaling.
- **Then all 7,328 conditions.** Report token usage and cost (`llm.usage_summary()`) after the pilot and at the end. **Budget for the full run: USD 20.** If the pilot's cost per condition projects above that, stop and report instead.

## Outputs (`data/enrichment/trials/`)

- `candidates.jsonl`: one candidate claim per line, in ledger claim format
- `sources.jsonl`: one archived `Source` record per study text
- `decisions.jsonl`: every screening decision, including `not_relevant`, with its reason (for auditing and measuring precision)
- `report.md`:
  - queries made, studies found, pairs screened
  - relevant, by asset type
  - quotes dropped
  - token usage and cost
  - known weaknesses

## Done when

- The pilot review sample exists and has been checked.
- The full run is complete within budget, and all outputs exist.
- `enrich/trials/README.md` says how to reproduce the run with one command.
- Everything is committed on branch `agent/trials` (code and the small `report.md` / `pilot_review.md` only; large outputs stay gitignored).
