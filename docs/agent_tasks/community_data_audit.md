# Lead follow-up: family-agent data findings

Status: investigated against the local ledger on 2026-10-04; **not yet corrected or deployed**. The family UI agent should preserve attribution and report duplicates, not merge them.

## STXBP1 organization identity

- `org:stxbp1disorders-org` and `org:stxbp1foundation-org` have different homepage domains but the identical canonical archived source hash `src:sha256:27016c51df6fb288bdf52a96f2d441b6b97e18929a6f0ab4d1954c80c261dd8d`.
- Claims `claim:sha256:5175c2fc4dedd888dff29b9f72407fc39816a6ad6c4ba9f6180c40ffb0126b28` and `claim:sha256:325951d42c8595ea7c3037565bbf6fa997c285c53e4e30fcd5f59c2fdc9d98f5` both quote the Foundation welcome text. Domain-based IDs created two entries.
- This strongly suggests an alias, but identical content alone is not an identity policy. Check official redirects/canonical links, record the evidence and resolve the entity through an explicit audited mapping/claim. Preserve both old claims/history.

## Simons Searchlight STXBP1 quote

- Claim `claim:sha256:cf79bfc3dac323f6cc17e49a12a00076dc9c4f5ba06ae9181b08d851de8623c9` targets Simons but its primary quote describes **STXBP1 Foundation**. The quotation exists on Simons' gene guide; word matching is correct, organizational attribution is not.
- Source: `src:sha256:d02e92f18cf110e5563db262b0f40b44ba37b9b775ae0d617c9272d6ee1323b3`, https://www.simonssearchlight.org/gene-guide/stxbp1/.
- The same archived page separately describes Simons as an international research program and links its STXBP1 research page/community. Its general organization profile is already reviewed, but that does not repair this condition-specific quote.
- Root cause: deterministic quote scoring favors organization words without matching the target organization, while semantic review sees page context beyond the quoted evidence. Require decision-carrying evidence about the claimed organization; reject a passage about a different group. Re-propose with appropriate verbatim evidence and re-review, retaining history. Do not just relabel the UI quote.

## Program versus registry

Simons' organization/program listing and `NCT01238250` are different record types. A confirmed `operates`/`registry-of` relationship could connect them; a name-based UI merge would hide source and eligibility distinctions. Keep separate until that link is sourced.

## Family-agent decisions relayed through owner

Proceed with “Prepare your questions,” named listings as questions to verify (not suitability/recommendations), `?brief=1` preserving other parameters/back navigation, flags rather than guessed merges, “Registry reports recruiting” rather than “Open to join,” and explicit atlas coverage gaps. Base `3740d1f` is acceptable; lead integrates the scoped UI commit.
