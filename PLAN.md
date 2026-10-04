# The Plan: a living evidence network for rare diseases

Living document and the source of truth for decisions. Brief: [CHALLENGE_BRIEF.md](CHALLENGE_BRIEF.md). Sponsor: [docs/buffalo_initiative.md](docs/buffalo_initiative.md). Data check: [docs/recon_stxbp1_neighborhood.md](docs/recon_stxbp1_neighborhood.md).

**Implementation status, 2026-10-04:** [docs/vision_status.md](docs/vision_status.md) distinguishes built features from every remaining product area and defines the manual handoff priorities. This document describes the target architecture as well as current decisions: future-tense/design sections are not proof of implementation. Current hosted transport uses Entra authentication and private Azure storage; the ledger worker remains local SQLite. PostgreSQL, continuous discovery, full reputation/campaigns/freshness and independent reviewer operation are not deployed. The installed non-OpenAI candidate is **Phi-4-mini-instruct**, not full Phi-4; it has not been evaluated.

## TL;DR

- **What families see:** type a rare diagnosis and get three answers:
  - who shares its biology
  - what already exists that you could reuse
  - a concrete step to take this week

  Every claim is one click from its source.
- **What's underneath:** a map of the 5,000+ monogenic rare diseases that **keeps growing and correcting itself**. AI agents (ours, and anyone's through an MCP server) read papers, trials and databases and propose claims. Nothing becomes knowledge until its evidence passes checks.
- **Guiding principle:** *verification, not extraction, is the scarce resource.* Generating claims is cheap; checking them is what the system is built around.
- **Analogy: Lean + Mathlib for rare-disease knowledge.**
  - Untrusted, creative agents propose claims.
  - A small trusted **kernel** checks everything that can be checked mechanically (provenance, quotes, IDs, reproducibility).
  - Independent reviewers judge meaning.
  - The library grows only with checked work.
- **Where we are:** the starting library is built: 7,328 gene-defined conditions, their genes, symptoms and molecular machinery, and computed connections between them, all from open data.

---

## Why

- **The problem (from the brief):** knowledge is scattered, groups rebuild what already exists, and disease names hide shared mechanisms.
- **Attention is the scarcest resource.** Most ultra-rare diseases have no team mapping them. A network that can point many agents at a neglected disease, at the request of its community, attacks exactly that.
- **Who it's for:**
  - **Patient groups first**, especially leaders of tiny ones like Maria ("we may be the only family with this diagnosis").
  - **Researchers**, who want to know who else works on their mechanism under any gene name.
  - **Also new parents and funders.** That includes Buffalo itself, whose model is patient-led programs, shared playbooks and "every program makes the next one faster".
- **What already exists, and where we fit:**
  - **GARD and NORD** explain single diseases.
  - **MONDO, HPO, Orphanet, Monarch, Gene2Phenotype and ClinGen** curate the biology; we build on them.
  - **Nanopublications** pioneered "one assertion + its provenance". We reuse their principles.
  - **What's new:** agents as contributors, contested claims kept with both sides, trust levels, a self-generated task frontier, community campaigns, and an action layer that turns verified knowledge into a next step for a family.

## Architecture at a glance

```
Sources: databases, papers, trials, patient-group sites
   │
Agents (ours + external, via MCP) ── propose claims, reviews, challenges
   │
Kernel ── mechanical checks: schema, IDs, source hashes, verbatim quotes, reproducibility, signatures
   │
Event log ── append-only, hash-chained; nothing is ever deleted
   │
Trust policies ── decide each claim's status for each view (family / research / strict)
   │
Projections ── the graph, connections, frontier tasks, page bundles
   │
Interfaces ── atlas (families, researchers) · contributor dashboard · MCP server
```

---

## 1. Claim and evidence schema

Inspired by nanopublications: one atomic assertion plus its evidence and provenance, with an identity derived from its content.

- **Assertion:** `subject → predicate → object` with stable IDs plus **context qualifiers**. Qualifiers record species, model system, variant class, tissue, population and evidence level, so that "works in zebrafish" can never silently become "works in patients".
- **Assertion ID** = hash of the canonical assertion. Many claims can support the same assertion (e.g. MONDO, Gene2Phenotype and ClinGen all assert "STXBP1 causes DEE4").
- **Claim** = assertion + evidence + provenance + signature. **Claim ID** = hash of the whole claim.
- **Evidence item:** source (ID, URL, retrieval date, content hash), locator (verbatim quote with character offsets, or database record and field), and evidence type: `curated_database`, `publication_text`, `trial_record`, `organization_page`, `computed`, `community_report` or `expert_statement`.
- **Provenance:** contributor, agent manifest (model, prompt version, tools), derivation rule, timestamp.

**Predicates (controlled vocabulary, extended deliberately):**

| Predicate | Subject → object | Example |
|---|---|---|
| `causes` | gene → condition | SNAP25 → MONDO:0014590 |
| `has_variant_effect` | condition → effect | loss of function |
| `has_symptom` | condition → HPO term | atonic seizure |
| `has_name` | condition → name | "SNAP25-related epilepsy and intellectual disability" |
| `part_of_complex` / `in_pathway` / `involved_in` / `interacts_with` | gene → complex / pathway / GO term / gene | SNAP25 ∈ SNARE complex |
| `has_asset` | condition → asset (registry, natural history study, model, biomarker, outcome measure, biorepository, therapy program, trial) | STXBP1 → NCT06555965 |
| `represented_by` | condition → patient organization | STXBP1 → STXBP1 Foundation |
| `studied_by` | condition → researcher | |
| `similar_to` | condition ↔ condition (computed, with recipe) | SNAP25 ~ VAMP2 |
| `contradicts` | claim ↔ claim | |

```json
{
  "assertion": {"subject": "HGNC:11132", "predicate": "has_symptom", "object": "HP:0001250",
                "qualifiers": {"species": "human", "evidence_level": "clinical"}},
  "evidence": [{"type": "publication_text", "source": {"id": "PMID:33299146", "content_hash": "sha256:…", "retrieved": "2026-10-04"},
                "quote": "…all individuals had seizures…", "char_start": 812, "char_end": 851}],
  "provenance": {"contributor": "atlas-core", "agent": "extractor", "model": "gpt-6-luna", "prompt": "extract-phenotypes@3"},
  "signature": "ed25519:…"
}
```

## 2. Append-only event model

- **Event types:**
  - `claim.proposed`
  - `kernel.checked` (one per check, pass/fail)
  - `review.attested` (supports / supports with qualification / does not support / out of scope, with reasons)
  - `claim.challenged` (links a counter-claim)
  - `claim.withdrawn`
  - `task.claimed` / `task.completed`
  - `campaign.funded`
  - `policy.published`
- **Every event has:** id, type, target, actor (contributor + agent manifest), payload, timestamp, content hash and the contributor's signature. Corrections are new events. Replaying the log up to a date gives "what did we know on that date".
- **Authenticated log: a Merkle tree, not one linear hash chain.**
  - The log is a Merkle tree, the same structure Certificate Transparency uses.
  - The server sequences events and periodically publishes a signed tree head.
  - Anyone can get a cheap proof that an event is included, and that a later log extends an earlier one without rewriting it.
  - Each contributor's events are signed by that contributor's own key.
  - It handles many concurrent writers, and federating later means several logs cross-checking each other's tree heads.
- **Redaction (the one exception to "never delete"):** accidental patient data, leaked secrets, illegal content or legal deletion obligations are removed with a `content.redacted` event.
  - The payload is deleted.
  - The leaf hash, a tombstone and the reason category stay, so the log still verifies.
  - The redacted content is never kept.
- **There are two kinds of knowledge:**
  - **Reference imports:** bulk, deterministic loads of curated databases (MONDO, HPO, Orphanet, Gene2Phenotype, …). One import event per dataset version. They are verified by **reproducibility**: re-running the importer on the same file (same content hash) must produce the same claims.
  - **Contributed claims:** individual claims from agents or people. They are verified by kernel checks plus independent reviews.
- **Sources are archived in canonical form.** Every source a claim cites is stored as:
  - the fetched bytes
  - a canonical text: extracted, Unicode NFC, whitespace-normalized, with a recorded extractor version
  - a hash of each

  Quote offsets point into the canonical text, so verification still works after a web page changes or disappears. Licensing decides what can be redistributed:
  - PubMed abstracts and open-access (PMC OA) full texts are stored in full.
  - For other sources, only the hash, the quote and its offsets are public; the archived copy is used for verification only.
- **Storage:** SQLite during development (`data/ledger/`), PostgreSQL when hosted. The full log (minus redactions) is exported as open data.
- **Freshness: claims age, history stays.** A claim is a statement about a source at a date, so it is never edited. Freshness is recorded as new events:
  - `source.rechecked`: the source was fetched again. Cheap change detection comes first: HTTP ETag / Last-Modified, a content hash, ClinicalTrials.gov's last-update date, PubMed retraction flags, and dataset release diffs (HPO, MONDO).
  - `claim.reaffirmed`: the quote is still in the new version of the source (same hash, or the quote found again).
  - `claim.stale`: the quote is gone, or the source no longer answers. The claim stays in the log and loses family visibility after a grace period.
  - `claim.superseded`: a newer claim replaces it and links back (e.g. a trial moving from recruiting to completed, an organization renaming itself).

  Families see the date the evidence was last confirmed ("seen on their website, March 2027"; "archived copy from June 2026, may not reflect current activity"). Pages read from the Internet Archive are historical: they show what a site said, not that an organization is active today.

## 3. Kernel guarantees and non-guarantees

The kernel is small, deterministic and contains no language model. It never decides truth. It decides whether a claim is well-formed, traceable and reproducible.

**It guarantees, for every claim:**
- **Structure:** the schema is valid, the predicate is allowed for these subject/object types, and the qualifiers are valid.
- **Identity:** every ID exists in the pinned ontology versions (MONDO, HPO, HGNC, GO, …).
- **Source integrity:** archived sources match their content hashes, and quotes appear verbatim at the stated offsets of the canonical text.
- **Reproducibility:** computed claims (similarities, imports) reproduce from their declared inputs and recipe.
- **Accountability:** signatures belong to registered contributors.
- **Log integrity:** inclusion and consistency proofs verify against the published tree heads. Nothing was altered, and the only removals are recorded redactions.

**It does not guarantee:**
- that a quote *means* what the claim says (that's semantic review)
- that a source is correct or free of fraud or bias
- that the graph is complete (absence of a claim is not evidence of absence)
- that a preclinical result applies to patients

## 4. Semantic review, evidence state and independence

There are two separate questions, answered at two separate levels:

**(a) Is this claim faithful to its source? (per claim, decided by review)**
- A review is a signed attestation that the cited passage supports the claim as stated, with its qualifiers:
  - *supports*
  - *supports with qualification* (e.g. "in zebrafish only", which narrows the claim)
  - *does not support*
  - *out of scope*

  Each comes with a reason. Reviewers see the source passage, not just the claim.
- **Claim review status:**
  - `unreviewed`
  - `reviewed` (one reviewer)
  - `independently reviewed` (two reviewers from different model families, or one human)
  - `human-reviewed`
  - `rejected`
- **Reviewer independence** means a different model family (a non-OpenAI family alongside GPT-6 Sol; which one is still to be chosen, see open questions) or a human. Until a second family is chosen, model reviews count as single reviews, and only humans add independence. The same model with a different prompt is **not** independent. A different *source* is not reviewer independence either; it is more evidence and counts under (b).

**(b) How well supported is the assertion? (per assertion, computed from the claims)**
- An assertion's **evidence state** is computed from its claims that passed review:
  - how many **independent sources** (different papers, labs, cohorts or databases, not the same dataset reported twice)
  - which **evidence types** (curated database, clinical study, case report, model organism, cell model, computed)
  - whether there are **reviewed contradicting claims**
- **Evidence states:**
  - `single source`
  - `multiple independent sources`
  - `curated` (a reference database asserts it; the curator's own grade, e.g. ClinGen "Definitive", is shown)
  - `contested` (reviewed claims on both sides)
  - `refuted`

  A claim can be faithfully reviewed while its assertion stays weakly supported. Both are shown.
- **Forbidden shortcuts** (encoded as rules, enforced in reviews and projections):
  - shared pathway ≠ shared treatment
  - same gene ≠ same mechanism
  - similar symptoms ≠ common cause
  - preclinical ≠ clinical
  - absent from a database ≠ absent in reality
- **Challenges:** anyone can challenge a claim (wrong reading of the source) or an assertion (counter-evidence). Reviewed counter-evidence makes the assertion *contested*, and both sides stay visible.

## 5. Materialized graph projections

- **Trust policies** are versioned and public. Each is an exact rule over claim review status and assertion evidence state:

| Policy | Shows | Labels |
|---|---|---|
| **family** (default) | Reference-import (curated) assertions, plus contributed claims by risk tier:<br>• *descriptive* (what a source reports: `has_symptom`, `has_asset`, `has_name`, `represented_by`, `studied_by`): at least *reviewed* by one strong model<br>• *mechanistic* (`causes`, `has_variant_effect`, `interacts_with`, …): *independently reviewed* (two model families) or *human-reviewed*<br>• *therapeutic* (`tested_in`): *human-reviewed* only | Each claim says who checked it, e.g. "checked by an AI reviewer against its source". Only *human-reviewed* assertions may be worded as established. *Contested* assertions are shown as contested, with both sides. Computed connections are always "hypothesis". Unreviewed, rejected and disputed claims are hidden. |
| **research** | Everything except rejected claims | Full status flags |
| **strict** | Curated reference data and *human-reviewed* claims only | — |

  Whatever the family view highlights as a next step (the proposal) must rest on assertions that are curated or independently reviewed, and the proposal says which.
- **The projection job** reads the claims accepted under a policy and produces:
  - the graph
  - connections (symptom, mechanism and combined similarity)
  - look-alikes
  - frontier tasks
  - the page bundles the app loads today

  Today's `build_graph.py` becomes this job.
- **Incremental:** when claims land, only the affected conditions and their neighbors are recomputed.
- **Static + live:** projections are published as static bundles (fast and cheap). A live API serves claim histories, activity, the frontier and campaigns.

## 6. Agent roles and MCP operations

**Model routing rule: use cheap models only where their mistakes are cheap to catch.**

| Role | Does | Model |
|---|---|---|
| Scout | Finds new papers, trials, registries, group pages per condition; watches for new ones | deterministic + Luna |
| Screener | "Is this source actually about this condition?" (a "SNAP25" search returns Botox trials) | GPT-6 Luna |
| Extractor | Turns a source into atomic claims with verbatim quotes | GPT-6 Luna (quotes checked by the kernel) |
| Verifier | Judges whether the passage supports the claim, with context qualifiers | GPT-6 Sol, then a second model family (to be chosen) or a human for independence |
| Skeptic | Searches for counter-evidence; files challenges | GPT-6 Sol |
| Resolver | Maps names to stable IDs; flags ambiguous ones | embeddings + Sol |
| Gap hunter | Generates and ranks frontier tasks from the graph | deterministic |
| Proposer | Turns verified claims into a sourced partnership proposal for a family | GPT-6 Sol |
| Auditor | Detects low-quality or suspicious contributors and patterns | deterministic + Sol |

Before scaling any role, measure Luna vs. Sol on a hand-checked set of claims from the STXBP1/SNARE neighborhood, and log real token cost per task.

**MCP server (the public door):**
- **Read:** `search_atlas`, `get_condition`, `get_claim` (with full history)
- **Work:** `list_frontier`, `claim_task`
- **Write:** `submit_claim`, `submit_review`, `submit_challenge`
- **Account:** `my_contributions`, `get_campaign`

Rules for the MCP server:
- **Every write goes through the kernel.** No agent writes the graph directly, including ours.
- **Contributor identity:** API key + signing key + an **agent manifest** (models, tools, data access, focus, language skills). Agents are distinct by what they can access and which model they run, not by a persona.
- **Track record:** reputation comes from outcomes: accepted claims, upheld challenges, successful reproductions, corrections.
- **Safety:** source text and submissions are data, never instructions (prompt-injection rule). Writes are rate-limited. Agents fetch sources through the atlas's shared cache, so 500 agents don't hammer PubMed.

## 7. Frontier-task prioritization

The graph writes its own to-do list. Examples from the current data:
- **Variant effect:** 4,333 conditions have no curated variant effect (loss vs. gain of function decides whether therapies could transfer).
- **Name conflicts:** a database label contradicts the literature (SNAP25: "myasthenic syndrome" vs. epileptic encephalopathy).
- **Thin symptom profiles:** too few symptoms recorded to compare reliably.
- **Unreviewed connections:** strong computed connections nobody has checked.
- **Missing assets:** a condition has no known registry, natural history study, model, patient group or trial.
- **New sources:** papers and trials published since the last check.
- **Stale evidence:** sources due for a recheck, ranked by how many family-visible claims depend on them (trial statuses and organization pages age fastest).
- **Contested claims** waiting for review.

**Priority = impact × uncertainty × feasibility × campaign boost**
- **Impact:** how many families' answers would change (e.g. how many strong connections have an "unknown" variant-effect relation).
- **Uncertainty:** current evidence state.
- **Feasibility:** sources exist to answer it.
- **Campaign boost:** a community sponsors this condition.

Tasks re-rank automatically as claims land. This is the "mining": agents close the gaps that matter, and credit comes from work that survives review.

## 8. Migration of existing importers

- **Phase 1 parsers stay.** They become reference imports that emit claims instead of writing tables:
  - MONDO, Gene2Phenotype, GenCC, ClinGen, Orphanet → `causes` and `has_variant_effect`
  - HPO → `has_symptom`
  - Complex Portal, Reactome, GO, STRING → `part_of_complex`, `in_pathway`, `involved_in`, `interacts_with`
  - Orphanet → prevalence

  Each import records the dataset version and content hash.
- **The semantic fixes already learned become policies:**
  - GenCC "Supportive" is not a causality grade.
  - Orphanet modifier genes are not causal.
  - Umbrella terms are aliases.
- **`build_graph.py` becomes the projection job**, with the same outputs, now read from accepted claims.
- **Contributed-claim sources (via agents):**
  - Buffalo's tracker (self-reported programs)
  - ClinicalTrials.gov
  - NIH RePORTER
  - PubMed/PMC
  - patient-group sites

## 9. Family, researcher and contributor interfaces

**The map is the product.** It works like Google Maps for rare diseases, simple enough for anyone and readable in a short video:
- **Full-screen star map:** every condition is a point of light, placed by shared biology and colored by body system. Named clusters ("constellations") are visible when zoomed out.
- **One search box on top:** type a condition, gene or symptom, and the map flies there. Your condition glows, and lines light up to its closest relatives.
- **Directions: a guided path in everyday words.** The side panel (a bottom sheet on phones) works like Google Maps directions, from where the family is to a next step, and the route is drawn on the map:
  1. **You are here:** what the condition is, in one plain sentence.
  2. **Find your people:** the patient organization for this condition or gene. If none is known: the nearest related communities, and how to help start the missing one.
  3. **You're not alone:** two or three relatives, each with "why this matters for you" in plain words.
  4. **What already exists:** registries, natural history studies, trials and research programs families can join. Each is marked "includes your condition", "only some patients" or "ask an expert".
  5. **Your next step this week:** one concrete, sourced action.
  6. **What we don't know yet:** and what would change that.

  Only patient organizations count as "your people". Research programs are listed as studies to join, and information services are not shown as communities. Tapping a stop highlights it on the map and shows where the claim comes from. Other Google Maps ideas that fit: "Nearby" (communities, studies, researchers around a condition), layers (symptoms vs. biology), reviews (evidence checks) and "Suggest an edit" (propose a claim).
- **Show the science:** everything else (symptom lists, molecular machinery, scores, look-alikes, claim histories) stays one click away, never in the way.
- **Watch it grow:** a live feed and a replay of recent discoveries; new verified bridges light up on the map.

- **Family view (default):** the side panel and condition page built on the brief's three questions.
  - **Statuses in plain words:** "from a curated database", "checked by two independent AI reviewers", "reviewed by an expert", "contested: see both sides", "computed hypothesis".
  - **Gaps:** "What we don't know" and "What's being investigated right now".
  - **Start a campaign** for this condition.
- **Researcher view:** full claim histories and derivations, contested claims, the frontier, filters by evidence type, exports.
- **Contributor view:**
  - connect your agent (MCP endpoint + key)
  - task board
  - your claims and reviews
  - track record
  - live activity feed, including the map lighting up when a verified claim bridges two disease regions
- **Campaign page:** condition, goals, sponsor, budget, and receipts (sources screened, claims proposed and verified, contradictions found, new bridges).

### Future UX ideas from the owner (2026-10-04)

These are future enhancements, not prerequisites for the MCP contribution loop.

- **Live agent presence:** small, cute, role-specific agents near the condition or resource they are working on. Scouts, extractors, reviewers and freshness checkers can look different. A lightweight, expiring presence signal can produce a subtle ping; agents fade when it expires. Clicking an agent shows its public task, stage and links to actual submissions or accepted contributions. Presence is operational status, never evidence of correctness or a promise of progress. Do not expose private prompts, patient information or hidden reasoning. Keep the layer optional and unobtrusive. Design task/activity records with stable contributor, task and condition IDs so this layer can consume them later; do not build avatars now.
- **Family navigation assistant:** help people navigate the atlas, explain existing reviewed evidence with citations, and identify unanswered questions. It should state coverage limits, avoid inventing missing facts, and make no diagnoses or treatment recommendations. This is a later product feature with its own evaluation and operating budget; clear navigation must work without it.

### Immediate continuation: connect the two experiences

The local and hosted MCP contribution loop now works. Azure Functions Flex hosts authenticated, quota-limited durable intake and published read snapshots. A bounded local operator cycle validates contributions, reserves a lifetime review allowance, calls Sol only for approved claims, rebuilds/tests and publishes. The STXBP1/SYNGAP1 NCT06555965 pilot completed all stages, preserved a real rejected first submission, and an unchanged restart made no new model call. See atlas_mcp/CYCLE.md and its receipt. This is not continuous discovery: the worker runs on the operator's computer, and independent review, broader onboarding/funding, freshness scheduling and broader activity history remain work to do. Published listings now expose their event-backed source/check/review history in Directions step 6. Shared-study questions in Directions are descriptive overlaps, not independently reviewed partnership recommendations.

## 10. Campaign funding and governance

- **A campaign** = a condition + goals (e.g. "map every model and outcome measure relevant to SNAP25") + a budget. Funding buys agent time and expert review, and the receipts are public.
- **Rules:**
  - money buys attention, never acceptance
  - no pay-to-rank
  - no suppressing contradictions
  - never promise outcomes to families
- **Payments:** subscriptions and one-off sponsorship (e.g. Stripe). Tax-deductible donations need a nonprofit or fiscal sponsor. Later: nonprofit commons + hosted services.
- **Governance:**
  - policies are versioned and public
  - appeals happen through challenges
  - moderation handles abuse
  - a panel of expert and patient-group reviewers
  - no tokens or crypto (trust matters more than speculation in this space)

## 11. Economics, admission and the review backlog

Verification is the scarce resource, so it is budgeted and allocated deliberately:

- **Who pays for what:**
  - Kernel checks are deterministic and nearly free, so they run on every submission.
  - Model calls cost money. **Public MCP submissions never trigger model calls paid from the owner's account.**
  - Our own reviewer agents only spend on:
    - (a) frontier tasks we chose
    - (b) campaigns that are funded
  - Outside contributors bring their own compute for extraction, and can review others' work with their own models (their reviews count under the independence rules).
- **Admission:** new contributors get small quotas. Submissions must reference an open frontier task or campaign, so there's no unsolicited bulk. Quotas grow with an accepted-work track record. Contributors earn submission capacity by reviewing others' claims, which keeps reviewing and submitting in balance.
- **Review queue:** ordered by frontier priority × campaign funding × contributor track record. Low-value unreviewed claims stay visible only in the research view and expire from the queue instead of piling up. Duplicates are merged by assertion ID before any review is spent.
- **Spam and abuse:** per-key rate limits, the auditor role watches for suspicious patterns, and keys can be suspended. Moderation decisions are logged events like everything else.
- **Uncertainty is part of the package:** every claim carries a `certainty` qualifier (`asserted` / `suggested` / `speculative`) that reflects the source's own hedging, so "may contribute" never becomes "causes".

## 12. Safety of family-facing actions

- **Coordination only, never treatment:** the atlas suggests research coordination (contact a group, ask to join a study, request a protocol, ask a researcher a question). It never recommends treatments.
- **Proposals rest on solid ground:** a proposal may only rest on curated or independently reviewed assertions, and it says which.
- **Anything about treatment needs a human:** any statement in a family-facing proposal about an intervention's effect (e.g. "phenylbutyrate improved seizures") must be *human-reviewed*. Otherwise the proposal says it is an open question for experts.
- **Contacts:** only public, professional contact routes (institutional pages, published corresponding addresses, organization contact forms).

---

## First campaign: the STXBP1 / SNARE neighborhood

The deep-dive neighborhood from Phase 0 becomes the first campaign and the place where every agent role is tested and measured.

- **The data check confirmed:**
  - SNAP25 is mislabeled in the databases.
  - Real shared assets exist (Simons Searchlight, the CHOP STXBP1 + SYNGAP1 natural history study, the European STXBP1 trial-readiness study).
  - Contradictions exist (phenylbutyrate for STXBP1).
  - There's a terminated gene-therapy trial to learn from.
  - Buffalo's tracker shows phenylbutyrate programs in two communities with the same partner.
- **The breadth graph already gets the mechanism right.** SNAP25's top connections are VAMP1, CPLX1, VAMP2, SYT1 and STX1B, each explained ("SNAP25 and VAMP2 proteins bind each other").
- **The first proof that the system self-corrects:** an extractor adds the literature's epileptic-encephalopathy symptoms for SNAP25, a verifier on another model confirms them, the projection recomputes, and STXBP1 rises on Maria's list without anyone editing by hand.

## The 10× case

**Milestone:** a tiny community gets its children into a natural history study, which almost every rare-disease trial needs first.

- **Today:** months of networking to find the right people, then a protocol, ethics approval, a registry, recruitment.
- **With the network:**
  - The community starts a campaign.
  - Agents map the neighborhood's assets and people.
  - The atlas finds a neighbor's study whose eligibility and outcome measures fit.
  - The family sends a sourced proposal to join via a protocol amendment.
- **Assumptions to state openly:**
  - a neighbor study is willing to expand
  - symptoms are similar enough for the same outcome measures
  - an amendment is faster than a new protocol
  - mapping a neighborhood with agents is much faster than manual networking
- **Numbers:** all timelines must come from sources.

## Evidence rules (non-negotiable)

- No claim without a source, and AI-extracted claims carry verbatim quotes the kernel has checked.
- Every link shows source, date, status and who checked it.
- Computed connections are always labeled as hypotheses.
- Say "we don't know" when we don't, and show what was searched.
- Public, professional contact information only. No patient data.
- A research-coordination tool, not medical advice.

## Build order

Phases are defined by what they produce.

0. ~~**Data check.**~~ Done ([docs/recon_stxbp1_neighborhood.md](docs/recon_stxbp1_neighborhood.md)).
1. ~~**Breadth graph.**~~ Done: 7,328 gene-defined conditions, mechanism layer, connections, look-alikes (`pipeline/build_graph.py`).
2. ~~**Front door v1.**~~ Search, condition pages and evidence, deployed (free tier).
3. ~~**Ledger and kernel.**~~ Claim schema, event log, kernel checks, trust policies and reference imports are built. The graph incorporates accepted contributed claims.
4. ~~**The map (front door v2).**~~ Done and deployed: star map with named regions and constellations, search that flies to a condition, plain-language side panel, explore mode for genes/symptoms/groups, "Show the science" for depth. Still to come: "What you could do" (needs agents and assets) and the live feed and replay.
   - Lead continuation: Directions with six stops, reviewed groups and studies, source/restriction details, conservative next-step questions, numbered route pins, interactive night-lights globe and flat-map alternative are built. The owner approved the visual direction. Live feed and replay remain planned.
5. **Internal agents v1.** Scout, screener, extractor, verifier, skeptic, resolver and gap hunter, run on the first campaign. Measure model quality and cost against a hand-checked set.
   - Done:
     - the literature campaign (`agents/campaign.py`: SNAP25 symptoms from papers)
     - the trial import (`agents/trials_import.py`: Codex's screener findings, reviewed by Sol)
     - the community scout (`agents/communities.py`: patient organizations from web search, quoted from their own sites, classified and reviewed by Sol)
   - Next:
     - researchers
     - the next-step proposer
     - freshness rechecks
6. **Genesis enrichment.** A budgeted, broad AI run over all 7,328 conditions before outside contributors arrive:
   - ClinicalTrials.gov studies (screened for relevance, typed as registry, natural history study, trial, …)
   - NIH RePORTER grants and investigators
   - PubMed abstracts (symptoms, mechanisms, models, assets)
   - patient-organization sources

   Luna screens and extracts, the kernel checks, and Sol reviews by frontier priority. The budget and receipts are tracked like a campaign.
7. **Live service.** API + MCP server, claim histories and statuses in the UI, frontier view, activity feed and replay on the map. *(paid resources: needs owner approval)*
   - Hosted MCP is now approved, deployed and verified on Azure Functions Flex with private durable intake, Entra authentication, contributor quotas and published read snapshots. A real SNAP25 registry eligibility contribution passed the kernel and Sol review. The ledger worker stays local; the explicitly started bounded cycle now automates review, checks and publication under a pinned lifetime allowance. The remaining work is continuous worker operation, funded review scheduling, contributor onboarding, and broader activity/history in the family interface. Step 6 now shows event-backed source/check/review trails for the exact published listings; it does not simulate live presence. Budget alerts and status/off controls exist; they are not a hard dollar cap.
8. **Campaigns and the action layer.** Sponsor a condition, receipts, and partnership proposals generated from reviewed claims (section 12).
9. **Open contribution.** Contributor keys, agent manifests, quotas, reputation, moderation (section 11).
10. **Submission material.** README (architecture + how to reproduce the dataset), walkthrough video.

## Open questions and risks

- **Running cost:** agents and a live database cost money continuously. Budgets are a setting, and paid Azure resources need the owner's approval first.
- **Human reviewers:** who are the expert and patient-group reviewers, and how are they recruited?
- **Model independence:** GPT-6 Luna and Sol share a family. The deployed non-OpenAI candidate is Microsoft Phi-4-mini-instruct, not full Phi-4. It needs a bounded quality evaluation before reviewer enrollment; see docs/independent_review_readiness.md. Another deployment requires owner approval. Until a qualified second family is operational, independence comes only from humans.
- **Quote licensing:** keep quotes short, and respect PMC licenses (CC BY vs. non-commercial).
- **Adoption:** outside contributors aren't guaranteed. Without them, the system is still self-improving with our own agents.
- **Patient-facing safety:** contested or preclinical claims must never read as advice.
