# Trial screening after the pilot

The owner authorized a background Luna run on 2026-10-04 with a **USD 30 screening cap**. Family-journey quality takes priority for the October 4, 15:00 Europe/Berlin submission. The old pilot remains intact in `../atlas-trials`; `run.py` and its tests here are a copy of the reviewed v2 implementation.

## Running jobs

```powershell
./.venv/Scripts/python -u -B -m enrich.trials.full_run collect
./.venv/Scripts/python -u -B -m enrich.trials.full_run screen --budget 30 --workers 24
```

These can run together. They use their own SQLite job database, **never the claims ledger**. They are resumable. OS file locks prevent a second collector or screener from duplicating work or sharing the same spending cap.

Artifacts and logs live in `data/enrichment/trials/full/` (gitignored): `jobs.db`, `collection.log`, `screening.log`, `manifest.json`, `candidates.jsonl`, source archives and decisions. Screening exports every 240 newly completed pairs and on a clean stop. For an explicit export when screening is stopped:

```powershell
./.venv/Scripts/python -m enrich.trials.full_run export
```

## Why this differs from the pilot

- Scan the registry in shared 1,000-record API pages, with selected protocol fields and one request at most every 1.25 seconds. Cache each page. No per-condition web/API query loop.
- Match all 7,328 conditions locally with a token trie. Keep gene/name boundaries, aliases such as SCA6, and punctuation variants such as Baker Gordon. Ordinary-word gene symbols such as WAS require uppercase spelling or a disease-name match.
- Prefer primary diagnosis/gene matches in titles and population fields, then eligibility, then background and alias-only matches. Schedule across conditions within each priority tier.
- Keep the v2 identity-only prompt, two-quote gate and explicit restrictions. Scheduling waves do not alter the screening prompt.
- Start with 24 workers, conservative 750,000-token/700-request minute admission below the owner's reported 1M TPM/1,000 RPM quota. Azure authentication is warmed and serialized; 429s back off. Non-rate-limit request failures stop with a durable cost reservation.

The first 48-pair operational check produced 23 mechanically valid candidates for approximately USD 0.026. This checks plumbing, **not semantic accuracy**. The local index recovered all 48 positive v2 pilot pairs. A bulk scan finds many broad-name and incidental matches; the earlier USD 30.13 linear pilot projection is not a guarantee of complete registry coverage. The job stops at its cap and records unfinished coverage.

## Cost and trust

The cap uses `pipeline/llm.py`'s configured Luna token prices, not a live Azure invoice. Before each wave, reserve conservative UTF-8 input bounds and both maximum output allowances. Release unused reservation only after all wave responses have logged complete token usage. A crash or uncertain request retains the reservation. Paid usage is in `full/cache/llm_usage.jsonl`.

This cap excludes earlier pilot costs, descriptions, community searches and **Sol semantic review**. The full-run candidates remain unreviewed and are not published automatically. Import useful reviewed batches through `agents.trials_import` only when no other ledger writer is active. Do not mistake deterministic absence of a name match for proof that no relevant study exists.

The initial parallel authentication attempt made no model requests; the recorded zero-usage reservation was explicitly reconciled before the successful operational check. Its logs remain for audit.

Tests: `python -m pytest enrich/trials ledger/tests pipeline/tests agents/tests`.
