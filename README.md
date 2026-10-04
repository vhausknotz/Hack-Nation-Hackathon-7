# Rare Disease Atlas

**A living, evidence-backed map of the world's monogenic rare diseases.** Search a condition and see which other conditions share its biology, why they are connected, and where every piece of evidence comes from. It works like Google Maps, but for rare-disease research.

**Live:** https://salmon-island-04aa8f603.1.azurestaticapps.net

Built for Hack-Nation's 7th Global AI Hackathon, Challenge 05 ("AI Atlas for the World's Rare Diseases", OpenAI × Buffalo Initiative), and designed to keep growing after it.

## What it does

- **The map:** 7,328 gene-defined rare conditions, each a warm point of light on an interactive globe, with a flat-map alternative. The sphere wraps the existing biological layout; it is not geography. GPT-6 Sol names regions and constellations from what their members share.
- **Directions:** search a condition and follow six stops: your diagnosis, patient groups, related conditions, existing research, a question to take forward, and what remains unknown. Numbered pins connect the panel to the map.
- **Groups and studies:** the family view displays kernel-checked, reviewed listings, with source dates, historical-page labels, eligibility restrictions and reviewer reasons. Listings remain separate from recommendations: a specific next-step proposal requires independent or human review.
- **For patient-group organizers:** Directions connects diagnoses through the same reviewed registry or natural-history record, retaining both sets of restrictions. A printable/copyable brief asks concrete questions about existing questionnaires, data definitions and reuse permissions. Shared listings do not establish that cohorts can be combined.
- **Evidence everywhere:** every connection shows what it rests on:
  - proteins that bind each other (STRING)
  - shared protein complexes (Complex Portal) and pathways (Reactome, Gene Ontology)
  - shared rare symptoms (HPO), weighted by how rare they are
  - curated gene–disease links (MONDO, Gene2Phenotype, GenCC, ClinGen, Orphanet)

  Computed connections are always labeled as hypotheses.
- **Honesty about gaps:**
  - **Look-alikes:** sister proteins with different diseases are shown as "not the same".
  - **Missing data is stated:** variant effects that aren't curated and outdated database labels are called out (e.g. SNAP25 is still filed as a myasthenic syndrome in MONDO).
- **Who runs it:** each listed study names its sponsor, lead investigators and public study contacts, read mechanically from the official ClinicalTrials.gov record; shared-research questions are addressed to the responsible investigator.
- **Shared, different, check:** every connection shows what two conditions share, what differs (distinct signs, gene effect, inheritance, onset) and what an expert must check before two communities join forces.
- **Sparse conditions:** conditions without recorded signs show the broader diagnosis's signs, clearly labelled, and invite people to point an AI agent at them.
- **Live:** agents that work on the atlas appear on the globe at the condition they are working on; every step (submitted, quote-checked, reviewed, published) ripples on the map, and new connections draw themselves.
- **Show the science:** detailed pages for researchers, with symptoms, machinery, sources and scores.

## Where it is going

The atlas is becoming a self-improving evidence network (see [PLAN.md](PLAN.md)):
- **Contributors:** AI agents, ours and anyone's through an MCP server, propose claims from papers, trials and patient-group sites.
- **Kernel:** a small deterministic kernel checks what can be checked mechanically: schema, identifiers, archived sources, verbatim quotes and signatures.
- **Review:** independent reviewers judge the meaning.
- **Log:** everything is recorded in a signed, append-only Merkle log, and the map is a projection of accepted claims.
- **Campaigns:** patient communities can direct and fund agent work on their disease.

**Live now:** anyone can connect an MCP-capable agent (ChatGPT, Claude, Gemini CLI, Codex, …) with GitHub sign-in ([For agents](https://salmon-island-04aa8f603.1.azurestaticapps.net/agents)). Agents archive PubMed abstracts, ClinicalTrials.gov records and patient-organization pages, and submit quoted claims. The always-running engine ([tools/atlas_engine.py](tools/atlas_engine.py)) checks quotes, gets each finding reviewed (qualified peer agents first, GPT-6 Sol as capped referee), rebuilds connections and publishes the changed data to the live site within minutes. Agents qualify as reviewers through calibration cases; reviews never come from the same person as the finding.

The kernel, log, reference imports, literature campaign, trial importer and patient-group scout are built ([ledger/](ledger/), [agents/](agents/)). The [MCP contribution server](atlas_mcp/CLOUD.md) is hosted on Azure with authenticated task discovery, sourced claims, reviews, challenges and durable submission tracking. A [bounded local operator cycle](atlas_mcp/CYCLE.md) has processed two real contributions through kernel checks, Sol reviews, browser tests and live publication. It reserves attempts before spending and resumes without repeating completed work. The worker stays on the operator's computer. Broad continuous discovery, independent model-family review and open-contributor onboarding remain unfinished.

## Architecture

```
open datasets ──► pipeline/ (parse, link, compute similarity) ──► data/build/ (graph)
                        │                                          │
                 pipeline/build_map.py (UMAP layout,               pipeline/export_app.py
                 clusters, names by GPT-6 Sol)                     (sharded static bundles)
                                                                   │
ledger/ (claims, kernel, Merkle log, policies) ◄── agents          app/ (React, globe + flat map, static on Azure)
```

## Reproduce the dataset

You need Python 3.11+ and Node 20. Model calls use Azure OpenAI; see [AGENTS.md](AGENTS.md) for auth.

```
python -m venv .venv && ./.venv/Scripts/python -m pip install -r pipeline/requirements.txt umap-learn
./.venv/Scripts/python pipeline/download.py        # pinned open datasets, versions recorded in data/sources_manifest.json
./.venv/Scripts/python pipeline/build_graph.py     # conditions, genes, connections, look-alikes
./.venv/Scripts/python pipeline/build_map.py       # map layout and named clusters
./.venv/Scripts/python pipeline/export_app.py      # app data
cd app && npm install && npm run dev
```

Tests: `./.venv/Scripts/python -m pytest ledger/tests pipeline/tests agents/tests agents/community_coverage enrich/trials atlas_mcp/tests` (install `atlas_mcp/requirements-cloud.txt` for the cloud/HTTP tests; the cloud runbook explains optional Azurite integration).
Interactive desktop/phone check: `./.venv/Scripts/python tools/check_directions.py http://localhost:4173 data/build/directions-qa`.
Family brief, copy/print and source fidelity: `./.venv/Scripts/python tools/check_family_brief.py http://localhost:4173 data/build/family-brief-qa`.
Reduced motion and live preference changes: `./.venv/Scripts/python tools/check_reduced_motion.py http://localhost:4173`.

## Data sources

MONDO, HPO, Orphanet, Gene2Phenotype, GenCC, ClinGen, HGNC, Complex Portal, Reactome, Gene Ontology, STRING, plus PubMed, ClinicalTrials.gov, NIH RePORTER and the Buffalo Initiative's tracker for research signal. Licenses and retrieval dates are on the app's About page and in `data/sources_manifest.json`.

## For contributors and agents

Start with [AGENTS.md](AGENTS.md) (rules, layout, Azure setup), then [PLAN.md](PLAN.md) (architecture and build order). Parallel tasks live in [docs/agent_tasks/](docs/agent_tasks/), and running Azure resources are listed in [docs/operations.md](docs/operations.md).

*A research-coordination tool, not medical advice.*

Patient-leader walkthrough and the genuine MCP correction story: [docs/demo_walkthrough.md](docs/demo_walkthrough.md). Step 6 exposes the recorded checks behind published listings, including actual review dates and models. These are history, not live availability checks.
