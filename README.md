# Rare Disease Atlas

**A living, evidence-backed map of the world's monogenic rare diseases.** Search a condition and see which other conditions share its biology, why they are connected, and where every piece of evidence comes from. It works like Google Maps, but for rare-disease research.

**Live:** https://salmon-island-04aa8f603.1.azurestaticapps.net

Built for Hack-Nation's 7th Global AI Hackathon, Challenge 05 ("AI Atlas for the World's Rare Diseases", OpenAI × Buffalo Initiative), and designed to keep growing after it.

## What it does

- **The map:** 7,328 gene-defined rare conditions, each a point of light. Conditions that share symptoms or molecular machinery sit close together, and GPT-6 Sol names the regions and constellations from what their members share (e.g. "Brain Synapse Signaling", "Cell Waste Breakdown").
- **Search** a condition, gene or symptom. The map flies there, lights up the closest relatives, and a simple panel answers *"Who shares your biology?"* in plain language.
- **Evidence everywhere:** every connection shows what it rests on:
  - proteins that bind each other (STRING)
  - shared protein complexes (Complex Portal) and pathways (Reactome, Gene Ontology)
  - shared rare symptoms (HPO), weighted by how rare they are
  - curated gene–disease links (MONDO, Gene2Phenotype, GenCC, ClinGen, Orphanet)

  Computed connections are always labeled as hypotheses.
- **Honesty about gaps:**
  - **Look-alikes:** sister proteins with different diseases are shown as "not the same".
  - **Missing data is stated:** variant effects that aren't curated and outdated database labels are called out (e.g. SNAP25 is still filed as a myasthenic syndrome in MONDO).
- **Show the science:** detailed pages for researchers, with symptoms, machinery, sources and scores.

## Where it is going

The atlas is becoming a self-improving evidence network (see [PLAN.md](PLAN.md)):
- **Contributors:** AI agents, ours and anyone's through an MCP server, propose claims from papers, trials and patient-group sites.
- **Kernel:** a small deterministic kernel checks what can be checked mechanically: schema, identifiers, archived sources, verbatim quotes and signatures.
- **Review:** independent reviewers judge the meaning.
- **Log:** everything is recorded in a signed, append-only Merkle log, and the map is a projection of accepted claims.
- **Campaigns:** patient communities can direct and fund agent work on their disease.

The kernel and log are built and tested ([ledger/](ledger/)); the agents and the live service come next.

## Architecture

```
open datasets ──► pipeline/ (parse, link, compute similarity) ──► data/build/ (graph)
                        │                                          │
                 pipeline/build_map.py (UMAP layout,               pipeline/export_app.py
                 clusters, names by GPT-6 Sol)                     (sharded static bundles)
                                                                   │
ledger/ (claims, kernel, Merkle log, policies) ◄── agents (next)   app/ (React + sigma.js map, static on Azure)
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

Tests: `./.venv/Scripts/python -m pytest ledger/tests`.

## Data sources

MONDO, HPO, Orphanet, Gene2Phenotype, GenCC, ClinGen, HGNC, Complex Portal, Reactome, Gene Ontology, STRING, plus PubMed, ClinicalTrials.gov, NIH RePORTER and the Buffalo Initiative's tracker for research signal. Licenses and retrieval dates are on the app's About page and in `data/sources_manifest.json`.

## For contributors and agents

Start with [AGENTS.md](AGENTS.md) (rules, layout, Azure setup), then [PLAN.md](PLAN.md) (architecture and build order). Parallel tasks live in [docs/agent_tasks/](docs/agent_tasks/), and running Azure resources are listed in [docs/operations.md](docs/operations.md).

*A research-coordination tool, not medical advice.*
