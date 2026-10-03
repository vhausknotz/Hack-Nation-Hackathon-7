# The Plan: what we're building, how, and why

Living document and the source of truth for decisions. Brief: [CHALLENGE_BRIEF.md](CHALLENGE_BRIEF.md). Sponsor: [docs/buffalo_initiative.md](docs/buffalo_initiative.md).

## TL;DR

- **The sponsor's goal:** "Help accelerate the path toward treatment for the 5,000+ monogenic rare diseases that remain fragmented across research silos," turning an evidence-backed knowledge graph into "actionable next steps for patients and researchers."
- **What:** type a rare diagnosis and see three things: which other communities share its biology, what they've already built that you can reuse, and one concrete step to take this week. Every claim has a source.
- **For whom:** patient groups first, especially the leader of a tiny one ("Maria"), and researchers. The same engine also serves new parents and pharma or funder scouts.
- **Why it's different:** existing tools describe *one* disease. We connect *across* diseases by mechanism and symptoms, and turn the connection into an action.
- **How:** open biomedical databases give a graph covering all monogenic rare diseases. Azure OpenAI models (GPT-6 Luna and Sol) read papers, trials and patient-group sites to add evidence-backed claims and assets. Graph analytics find neighbors, reusable assets, shared people and gaps.
- **Core experience:** one search, one answer page built on the brief's three questions, and one click to a sourced partnership proposal.

---

## 1. Why

### The problem (from the brief)
- **Knowledge is scattered** across papers, databases, trials and patient groups.
- **Groups rebuild what exists** because they can't find each other's registries, models or study designs.
- **Names hide mechanisms.** Different genes can break the same process, and one gene can break things in different ways.

### Who it's for
- **Maria, leader of a tiny or new patient group.** "We may be the only family with this diagnosis." She gets the most value because she has no scientific advisors yet. Big, established foundations already know their neighbors.
- The same engine serves the brief's other three personas through different starting points:
  - **Devon**, a newly diagnosed parent, needs plain language and to find a community.
  - **Priya**, a pharma or funder scout, starts from a therapy type and wants ranked disease clusters.
  - **Dr. Osei**, a researcher, starts from a gene and asks who else works on the same mechanism.

### Why the sponsor cares
Buffalo Initiative backs **patient-led** therapy programs for ultra-rare monogenic diseases. Their thesis is shared playbooks and infrastructure, so that "every program makes the next one faster." They run a public **Therapy Tracker** of 60+ patient-led programs. Our atlas is the discovery layer for that model: it finds *which* infrastructure, *which* neighbors and *which* next step, and Buffalo's own programs appear inside the graph.

### What already exists, and where we fit
- **Building on, not competing with:**
  - GARD and NORD explain one disease.
  - MONDO, HPO, Orphanet and Monarch provide biology data.
  - DisMech holds AI-curated mechanisms.
  - Open Targets focuses on drug targets.
  - COMBINEDBrain is real shared infrastructure.
- **Our layer is connection → evidence → action.** Not "tell me about my disease" but "what in the world can move my disease forward, why, and what do I do now."

---

## 2. What the user sees

### One search box
It accepts a disease, gene, symptom, patient group or mechanism, and resolves synonyms visibly ("Munc18-1 → STXBP1 gene").

### One answer page, built on the brief's three questions

| Section | Shows |
|---|---|
| **1. Who shares your biology?** | 3–5 closest communities, each with a one-line reason, a connection strength and an evidence tier |
| **2. Why are you connected?** | A small path of about five nodes (your gene → shared mechanism → neighbor gene → neighbor disease → their patient group). Click any link to see the quote, source, date, confidence and any contradicting evidence |
| **3. What already exists?** | A **road-to-treatment** strip: community → registry → natural history study → models → outcome measures and biomarkers → therapy program → trial. Each station is marked *you have it*, *borrowable from a neighbor* or *missing*. Asset cards are split into **reusable**, **differs** and **needs expert review** (the brief's exact bar) |
| **4. What to do this week?** | 1–3 concrete steps with a named partner. A **Draft proposal** button produces a sourced, ready-to-send document plus a checklist of what must be confirmed first |

**Always visible: "What we don't know."** It shows what we searched, what evidence is missing and the next question to test. If there's no supported route, this becomes the main answer.

### One visual language for evidence
The three tiers use the judges' own words:
- **Data:** observed in a curated database or reported in a paper. Solid line.
- **Hypothesis:** inferred by the atlas. Dashed line.
- **Clinical proof:** shown in a trial or an approval. Gold.

Contradicting evidence shows as a red marker on the link.

### Depth for other personas (behind a click, not in the main journey)
- **Map view:** every rare disease as a calm star map with your neighborhood highlighted, like "you are here" on a map.
- **Persona views:**
  - Devon: plain language, "find my community or help build it"
  - Priya: start from a therapy type or mechanism and get ranked clusters, including Buffalo Therapy Tracker programs
  - Dr. Osei: start from a gene and see who else works on this mechanism under any gene name
- **Contribute (stretch):** a patient group adds an asset ("we run a registry"). It enters as unverified until checked.

---

## 3. How it works

### 3.1 Data in two layers

**Breadth layer: all 5,000+ monogenic rare diseases (plus other rare diseases where the data exists), no AI needed.** This means anyone can search any disease.

| Source | Gives us | Access |
|---|---|---|
| MONDO | Stable disease IDs, synonyms, cross-references | Open download |
| HPO annotations | Disease → symptoms (with frequency and references) | Open download |
| Orphanet (Orphadata) | Gene → disease links typed *loss of function* or *gain of function*, prevalence | Open download |
| HGNC | Gene IDs and old gene names | Open download |
| ClinVar | Variants and their consequences | Open download |
| Reactome / Gene Ontology / SynGO | Gene → pathway, biological process, synaptic function | Open download |
| Complex Portal | Gene → protein complex (e.g. the SNARE complex) | Open download |
| Gene2Phenotype, ClinGen dosage | Variant effect: loss of function, dominant negative, gain of function | Open download (to evaluate) |
| ClinicalTrials.gov | Studies, conditions, interventions, eligibility | API v2 |
| NIH RePORTER | Grants, investigators, institutions | API |
| PubMed / PMC | Papers, abstracts, authors, open full text | E-utilities API |
| Buffalo Therapy Tracker | Patient-led programs (modality, stage, organization) | Public web page (cite it; check terms) |
| Patient-group sources (NORD, Orphanet, Global Genes, COMBINEDBrain members, group websites) | Communities, registries, studies, biorepositories | Web pages plus AI extraction |

OMIM restricts redistribution, so we reference OMIM IDs through the HPO and MONDO crosswalks.

**Depth layer: the demo neighborhood, built by AI.** Papers, trials, patient-group sites and tracker entries become extracted claims and assets, each with a verbatim quote.

### 3.2 The key idea: each kind of sharing needs its own kind of similarity

| What a group wants to borrow | Similarity that matters |
|---|---|
| Registry, natural history study, outcome measures | Shared symptoms and disease course |
| A drug or therapy approach | Same mechanism *and* same variant effect (protein missing vs. protein toxic) |
| Lab models, assays | Same protein, complex or pathway |
| Advisors, collaborators | People who published on, or were funded for, either disease |

Symptom similarity weights **rare symptoms more than common ones**: "you both have seizures (hundreds of diseases do), but you also share X (only a handful do)." That is the brief's "broad vs. unusually informative symptoms."

### 3.3 The graph
- **The unit of a "community" is the gene-defined condition** (e.g. "SNAP25-related disorder"), because patient groups, Buffalo's tracker and families all think by gene. A condition groups its OMIM, Orphanet and MONDO entries, and splits only when variant effects differ (e.g. SCN2A gain vs. loss of function).
- **Nodes:** disease, gene, variant class, mechanism, pathway, symptom, patient group, researcher, paper, study/trial, asset (registry, natural history study, model, biomarker, outcome measure, biorepository), therapy program, funder/grant.
- **Every edge carries:**
  - relationship type
  - source (ID + URL) and date
  - confidence
  - evidence tier (data / hypothesis / clinical proof)
  - supporting quote (for anything read from text)
  - contradicting evidence, if any
  - how it was made (database import, AI extraction with model name, or analytics)

### 3.4 Where AI does the work (your Azure Foundry)

| Job | Model | Guardrail |
|---|---|---|
| **Filter** whether a paper, trial or grant is actually about the condition (a "SNAP25" search returns Botox and Alzheimer's trials; "NSF" returns the National Science Foundation) | `gpt-6-luna` | Every keyword hit is checked before it becomes an edge |
| **Extract** claims, mechanisms, assets and people from papers, trials and group sites | `gpt-6-luna` | Structured output; must return an exact quote that is found verbatim in the source, or the claim is dropped |
| **Reconcile** names to stable IDs (MONDO, HPO, HGNC) | `text-embedding-3-large` shortlists, `gpt-6-sol` decides | Low-confidence matches are flagged, not merged |
| **Verify** with a second pass: does the quote really support the claim? Is there a contradiction? | `gpt-6-sol` | Disagreement lowers confidence |
| **Explain** a path in plain language | `gpt-6-sol` | Every sentence cites the edges it relies on |
| **Propose** a partnership letter | `gpt-6-sol` | Uses only facts from the graph; sources listed |

This covers the brief's "Built with OpenAI" trio (Extract, Reconcile, Explain), which the track prize requires.

### 3.5 Graph analytics
- **Neighbors:** symptom similarity (rare symptoms weighted higher) plus mechanism similarity (shared gene, complex or pathway, and the *same* variant effect).
- **Clusters:** community detection over the combined similarity. AI names each cluster from its shared features.
- **Asset matching:** each asset type is matched with the similarity that fits it (3.2).
- **Shared people:** researchers, clinicians and funders who already bridge two "unrelated" communities (the brief's "network overlap").
- **Counterexamples:** same gene but different variant effect, or similar symptoms but different mechanism. These are flagged "don't merge" and shown, because judges ask for them.
- **Gaps:** for each community, which road-to-treatment stations are missing and whether a neighbor has them.

### 3.6 Architecture

```
pipeline/ (Python, offline)                          app/ (deployed web app)
download → normalize → extract (Azure) → verify      search → answer page → evidence drawer
        → build graph → analytics → data/build/ ───► map view, persona views
                                                     api: proposal drafting, explain-on-demand (Azure)
```

- The graph is precomputed and ships with the app, so there's no database server to keep alive.
- Live AI runs only for proposals and on-demand explanations. Results are cached and the key stays server-side.
- Hosting: Vercel or Azure (decide at deploy time). We deploy early and keep it deployed.
- **Stretch: "deepen any disease."** Run the depth pipeline on demand for a disease outside the demo neighborhood, labeled "fresh, unreviewed."

---

## 4. The deep-dive neighborhood (confirmed in Phase 0)

**STXBP1 and the SNARE-machinery disorders** (STXBP1, SNAP25, STX1B, VAMP2, SYT1, CPLX1, …). The SNARE complex is the protein machinery nerve cells use to release signals. Full findings: [docs/recon_stxbp1_neighborhood.md](docs/recon_stxbp1_neighborhood.md).

**The anchor story: Maria's child has SNAP25-related disorder.**
- About 32 known patients, no trial, no natural history study.
- The databases still file it as a myasthenic syndrome, while the literature describes an epileptic encephalopathy.
- **The atlas connects her through mechanism.** STXBP1 is part of the same SNARE machinery (the "SNAREopathies" literature), where symptom matching alone fails.
- **It finds real assets:**
  - Simons Searchlight already covers SNAP25.
  - A multi-gene STXBP1 + SYNGAP1 natural history study is recruiting at CHOP.
  - A European STXBP1 trial-readiness study is running.
  - The STXBP1 Foundation has a phenylbutyrate program.
- **It shows contradictions:** phenylbutyrate for STXBP1 has both supporting and opposing 2026 evidence.
- **It shows lessons:** a terminated gene-therapy trial.
- **It finds bridge people:** e.g. Weill Cornell partners with several communities.

**Why it fits:**
- Buffalo's home turf (pediatric, neurogenetic, monogenic) and in Buffalo's own tracker.
- Untreated.
- A real backtest: from SLC6A1's side, STXBP1 ranks #12 of 10,739 diseases by symptoms, the pairing the real phenylbutyrate trial made.
- Clean counterexamples the graph finds on its own: STXBP2, the same protein family, causes an immune disease; SYT2 and VAMP1 belong to the neuromuscular cluster.

The breadth layer still covers every monogenic disease. This neighborhood is where the deep evidence layer is built and checked first.

---

## 5. Rules we hold ourselves to

- No claim without a source. AI-extracted claims carry a verbatim quote.
- Every link shows source, date, confidence and tier.
- AI inference is always labeled "hypothesis."
- Say "we don't know" when we don't, and show what we searched.
- Public, professional contact information only. No patient data.
- A research-coordination tool, not medical advice.
- Plain language first, detail on click.

---

## 6. The 10× case

**Milestone:** a tiny community gets its children into a natural history study. Almost every rare-disease trial needs one first.

- **Today:** networking to find the right people, designing a protocol, getting ethics approval, setting up a registry, recruiting.
- **With the atlas:** find a neighbor's study whose eligibility and outcome measures fit, ask to join through a protocol amendment, and use shared infrastructure like a biorepository.
- **Assumptions to state openly:**
  - A neighbor study is willing to expand.
  - Symptoms are similar enough to use the same outcome measures.
  - An ethics amendment is faster than a new protocol.
  - The atlas turns months of networking into one search.
- **What must be validated next:** talk to patient-group leaders and study investigators, and test the atlas against historical cases (the 4-PBA trial).
- **Numbers:** all timelines must come from sources. No invented numbers.

---

## 7. Build order

Phases are defined by what they produce. Each one ends with something we can look at.

0. ~~**Data check.**~~ Done: go. See [docs/recon_stxbp1_neighborhood.md](docs/recon_stxbp1_neighborhood.md).
1. **Breadth graph.** Every monogenic rare disease with IDs, synonyms, genes (with loss/gain of function), symptoms and trials. Output: searchable graph data.
2. **App skeleton.** Search plus the answer page, wired to real breadth data and deployed. Output: a live URL.
3. **Depth layer.** AI extraction and verification for the neighborhood (papers, trials, group sites, tracker). Output: evidence-backed claims and assets.
4. **Analytics.** Neighbors, clusters, asset matching, shared people, counterexamples, gaps.
5. **Action.** Road to treatment, next steps, proposal drafting, the "what we don't know" view.
6. **Polish.** Map view, persona views, a plain-language pass, the backtest on the 4-PBA precedent.
7. **Submission.** README (architecture and how to reproduce the dataset), the 1-minute walkthrough, the team video.

---

## 8. Open questions and risks

- **Patient-group and registry data is the messiest layer.** It needs AI extraction plus manual spot checks.
- **Symptom similarity alone groups "everything with seizures."** Mechanism and rare symptoms must carry the weight.
- **Data terms:** OMIM is restricted; the Buffalo tracker's terms need checking; respect site terms and robots.txt.
- **Product name and visual identity:** to be decided.
