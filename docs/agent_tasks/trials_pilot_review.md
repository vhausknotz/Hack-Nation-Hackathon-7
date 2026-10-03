# Main-agent review of the trials pilot (branch `agent/trials`)

Reviewed 2026-10-03 against `enrich/trials/pilot_review.md` and `NOTES.md`. The pilot is good work: careful scoping, honest budget stop, reproducible caching and tests.

## Verdicts on the 30-decision sample

- **Correct or acceptable: 28 of 30.** Acronym clashes (NSF = nephrogenic systemic fibrosis), Alzheimer's/SNAP25-biomarker trials and non-specific Lennox-Gastaut trials were rightly rejected. Valuable positives include: the PRAX-222 ASO trial (SCN2A), the phenylbutyrate trial, the terminated CAP-002 gene therapy, the STXBP1 gait outcome-measure study, and Simons Searchlight listing SNAP25.
- **#5 (NCT06314490, SCN2A ASO n-of-1): wrong. Should be `direct`, `trial`.** The rejection rested on the atlas context saying "loss of function". That label came from a gene-level ClinGen dosage score wrongly applied to this condition; the main agent is fixing that data. Regardless, the screener should not judge mechanism.
- **#14 (NCT06356233, STXBP1): asset type should be `biomarker`.** The title and primary outcomes are biomarkers.
- **#22 (GABRG2 febrile-seizure gene study): `biorepository` is doubtful.** It is a genetic cohort study; prefer `natural_history_study` unless samples are banked for reuse.
- **On #6, #24, #27 and the dropped CACNA1A familial hemiplegic migraine case:** the conservative handling of studies that require a movement disorder is right. Keep stating the phenotype restriction in the reason.

## Changes required before scaling

1. **Remove the variant effect (loss/gain of function) from the screening context.** Screening judges population and condition match only, never mechanism.
2. **Asset-type priority rule:** biomarker if the title or primary outcomes are biomarkers; outcome measure if the study validates an outcome measure; otherwise registry, natural history study or trial as now. Keep secondary uses in `decisions.jsonl`.
3. **Quotes must carry the decision, not just the name.** Up to two quotes per decision:
   - one that shows this condition or gene is in the eligible population
   - one that shows the study type

   Put any extra eligibility restriction (e.g. "requires a movement disorder") into an evidence field `restriction`, so the atlas never presents a gene-wide cohort as open to every condition of that gene. The main agent's GPT-6 Sol verifier will reject candidates whose quotes don't support the decision.
4. **Reduce cost before the full run.** Two levers:
   - a deterministic prefilter that drops pairs whose study text never mentions the gene symbol or any of the condition's names as whole words
   - truncated study text for screening (title, conditions, keywords, brief summary, first part of eligibility)

   Re-project the cost after these changes.

## Budget

The pilot projected USD 30 against a USD 20 cap. Whether to raise the cap or require the cost reductions first is the owner's decision. The main agent's recommendation: apply the changes above, re-project, and run if under USD 25.

## Integration

The main agent will import candidates through the ledger:
- archives into the ledger source archive
- claims signed by a registered `agent:trial-screener` identity whose manifest credits Codex
- a review by GPT-6 Sol for each claim

Pilot candidates may be imported before the full run, so families see results for the first-campaign genes early.

## Pilot import results (main agent, 2026-10-03)

The 59 pilot candidates were imported with `python -m agents.trials_import` (on `main`):
- the kernel accepted all 59 (every quote verbatim in its archived record)
- GPT-6 Sol reviewed each: 10 supports, 43 supports with qualification, 6 does not support

The 6 rejections:
- **5 wrong asset type; the population was right:**
  - NCT05161494: a gait feasibility study, not a validated outcome measure
  - NCT06356233: a biomarker study, as noted above
  - NCT01934998: a one-time imaging comparison
  - NCT00257985 and NCT00358839: GTN and CGRP migraine provocation studies, not treatment trials
- **1 wrong population:** NCT04048213, a Doose syndrome study that never mentions SLC6A1

**For v2:**
1. **Apply the asset-type priority rule strictly.** A study that is none of the schema's asset types (e.g. a provocation or one-off mechanistic study) should be dropped with a reason in `decisions.jsonl`, not forced into `trial` or `natural_history_study`.
2. **Keep the output format the importer reads.** It needs these files in one folder (or its parent):
   - `candidates.jsonl` with claim-shaped proposals, as `candidate_for` writes them
   - `sources.jsonl`
   - `archive/raw` and `archive/text`
   - `manifest.json` (its `model` and `prompt` go into the screener's manifest)

   The main agent will run `python -m agents.trials_import --from <folder>`.
3. **Do not import into or modify the ledger.** The importer signs, archives and reviews.
4. **Report back after v2.** Report the re-projected full-run cost and stop. The owner decides the budget before the full run.
