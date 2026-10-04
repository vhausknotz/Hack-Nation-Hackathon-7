# Independent reviewer readiness — 2026-10-04

## Verified deployment, not verified review quality

A read-only ARM deployment inventory of the existing `valiOpenAI` account confirmed:

| Deployment | Publisher/model | State | Configured rate limit |
|---|---|---|---|
| `Phi-4-mini-instruct` | Microsoft / Phi-4-mini-instruct, version 1 | Succeeded | 1,000,000 tokens and 1,000 requests per minute |
| `gpt-6-sol` | OpenAI / GPT-6 Sol | Succeeded | 500,000 tokens and 500 requests per minute |
| `gpt-6-luna` | OpenAI / GPT-6 Luna | Succeeded | 1,000,000 tokens and 1,000 requests per minute |

The earlier handoff's “Phi-4” shorthand was imprecise: the installed model is **Phi-4-mini-instruct**. Its deployment state does not prove inference access, output compatibility, cost, or semantic-review quality. The account also has a DeepSeek deployment; the owner's instruction excludes it. Nothing was changed, deployed or invoked during this inventory.

The Foundry skill's MCP connector was unavailable in this session. The fallback used the existing Az PowerShell credential and ARM GET requests, selecting only deployment metadata for this project's existing model account. No keys were requested or printed.

## Prepared offline challenge set

`data/evaluations/reviewer-readiness-v1/cases.json` contains six constructed review inputs against the archived public-domain NCT06555965 record. Its source hash was verified against the local archive. Cases cover:

- STXBP1 and SYNGAP1 natural-history listings with the complete source restrictions.
- STXBP2 versus STXBP1 gene-name confusion.
- Mistaking a natural-history study preparing for future trials for an actual treatment trial.
- Claiming a reusable sample bank without evidence that one exists.
- An inaccurate eligibility statement that erases the causative-variant requirement and medical exclusions.

This is an **unrun minimum regression gate**, not an expert-adjudicated benchmark or proof of biomedical competence. The coding lead authored its expectations. One source and six constructed examples cannot estimate general accuracy. The last case intentionally requires rejecting the inaccurate restriction instead of approving the listing and burying a correction in the reviewer's explanation.

## Before enabling a second reviewer

1. Choose a bounded evaluation allowance separately from Luna's $30 screening cap and the exhausted two-call Sol cycle. Confirm current endpoint/API and pricing for the exact deployment. No allowance or price was inferred from its quota.
2. Send only each case's input and source text to the model, never the expectations or another model's judgment. Keep a distinct cache, immutable source hash, model/version, prompt, token usage and maximum attempt count. Preserve reservations for ambiguous requests.
3. Require a valid verdict and source-grounded explanation for every case. Fail the minimum gate on any false acceptance of a negative case, erased restriction or invalid/missing response. Manually inspect explanations; keyword matches or agreement with Sol are not a sufficient quality measure.
4. Add representative difficult real cases: phenotype-restricted cohorts, broad syndrome names, n-of-1 trials, archived community pages, conflicting scope and no-mention controls. Seek independent expert adjudication where available. Test source-text instruction handling as well.
5. Only after reviewing those results, explicitly enroll the actual model family and authorize narrowly scoped attestations. The evaluation itself must not submit reviews, mutate the ledger, or upgrade trust labels. Independent family labels describe review provenance; they do not certify scientific truth.

For now, keep current listings accurately labeled single-AI-reviewed. Another Sol prompt, Luna, a router to the same family, or a coding agent's assistance does not establish an independent published review. The existing MCP/cycle demonstration remains valid without claiming this missing capability.
