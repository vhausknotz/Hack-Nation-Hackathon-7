# Buffalo Initiative / Rare Disease Atlas — Working Notes

## 1. The challenge in one sentence

Build an **AI map for rare-disease research** that helps a patient group go from:

**“We have this disease.”**

to:

**“Here is a useful connection, why it matters, who to contact, what already exists, and what we could do next.”**

The hackathon brief calls this the **AI Atlas for the World’s Rare Diseases**.

---

## 2. Why Buffalo cares

The Buffalo Initiative wants ultra-rare disease research to move toward treatments faster.

The core problem is not only lack of research.

The problem is that useful knowledge is scattered across:

- papers
- disease databases
- clinical studies
- patient groups
- researchers
- registries
- models
- biomarkers
- funding programs

Different disease communities may be rebuilding the same things without knowing it.

Buffalo wants to help patient groups find useful work that already exists and connect to people who can help.

---

## 3. Why OpenAI is relevant

This is a good AI problem because the data is messy.

The same disease can have several names.

The same mechanism can be described in many ways.

Important facts may be buried in full papers.

Different papers may disagree.

AI can help:

1. **Read** papers and databases.
2. **Extract** genes, variants, phenotypes, mechanisms, claims, researchers, treatments, models, and evidence.
3. **Normalize** different names into the same entity.
4. **Compare** diseases by biology, not only by disease name.
5. **Explain** the connection in simple language.
6. **Suggest the next useful action.**

The important part is not “AI answers a question.”

The important part is:

**AI discovers a connection the user did not know to ask about.**

---

## 4. What the final product should feel like

Think:

**Google Maps for rare-disease research.**

The user enters a disease.

The product says:

- Here is what is known.
- Here are related diseases.
- Here is why they may be related.
- Here is the evidence.
- Here is what already exists.
- Here are patient groups and researchers.
- Here is what is uncertain.
- Here is a useful next step.

The graph is not the product.

**The next useful action is the product.**

The experience should feel:

- simple
- calm
- evidence-backed
- transparent
- actionable
- honest about uncertainty

---

## 5. Is this just “ChatGPT for rare disease”?

It should not be.

A normal AI assistant can already answer:

- What causes this disease?
- What treatments exist?
- Who researches it?
- What trials exist?

The Atlas becomes valuable when it can say:

> “This other disease has a different name but shares the same mechanism.”

> “That community already has a registry or disease model you may be able to reuse.”

> “This researcher works on the same pathway.”

> “This failed trial contains a lesson you should know before spending money.”

> “Here are the papers supporting this connection.”

So the real value is:

**systematic discovery across many diseases and many sources.**

---

## 6. The technical idea we discussed

A strong pipeline could look like this:

### Stage 1 — collect raw information

Possible sources:

- PubMed / PubMed Central
- ClinicalTrials.gov
- OMIM
- ClinVar
- HPO
- MONDO
- Orphanet
- NIH RePORTER
- patient-group websites
- NORD
- GARD
- other open biomedical datasets

For the hackathon, do not try to ingest the whole world.

Start with one disease area and enough material to prove a complete journey.

### Stage 2 — use Luna to structure full papers

Do not rely only on keyword matching.

Do not rely only on abstracts if the important evidence is in the full paper.

For each paper, extract structured fields such as:

```text
paper_id
diseases
genes
variants
phenotypes
mechanisms
pathways
therapeutic approaches
models
biomarkers
researchers
claims
contradictions
clinical implications
```

Every important claim should also carry:

```text
source
page_or_section
supporting_text_span
direct_evidence_or_inference
confidence
```

### Stage 3 — normalize

Resolve things like:

- disease synonyms
- old gene names
- different names for the same phenotype
- different descriptions of the same mechanism

Use standard identifiers when possible.

Examples:

- MONDO for diseases
- HPO for phenotypes
- HGNC for genes

### Stage 4 — reconcile evidence

A second AI pass can compare claims across papers.

Questions include:

- Are these two descriptions actually the same mechanism?
- Does one paper support another?
- Is there contradictory evidence?
- Is this connection direct or only inferred?
- How strong is the evidence?

### Stage 5 — build the graph

Possible nodes:

- disease
- gene
- variant
- phenotype
- mechanism
- pathway
- researcher
- patient organization
- clinical trial
- registry
- model
- biomarker
- paper
- drug / therapeutic approach

Possible edges:

- disease → caused by → gene
- gene → affects → pathway
- disease → has phenotype → symptom
- researcher → studies → mechanism
- patient group → maintains → registry
- trial → tests → treatment
- paper → supports → claim

### Stage 6 — discover connections

Now ask the graph:

- Which diseases share mechanisms?
- Which diseases share unusual phenotypes?
- Which groups have reusable assets?
- Which researchers connect two disease areas?
- Which treatments or trial designs might be relevant elsewhere?
- Where is evidence missing?

### Stage 7 — explain the result simply

The user should not see a giant raw graph first.

They should see:

**“Here is the connection.”**

**“Here is why.”**

**“Here is the evidence.”**

**“Here is what is uncertain.”**

**“Here is what you could do next.”**

---

## 7. Why start with one disease instead of manually choosing 20 related diseases?

Because discovering the related diseases is part of the problem.

A better approach:

1. Start with one disease.
2. Gather its known biology and literature.
3. Use structured sources plus AI-extracted mechanisms and phenotypes.
4. Search outward for possible matches.
5. Rank the candidate connections.
6. Deeply analyze the strongest ones.
7. Let the final 5–20 disease cluster emerge from the data.

The system should discover the neighborhood.

You should not manually invent it first.

---

## 8. Full papers vs abstracts

Our conclusion was:

**Full papers are likely important.**

The most useful information may be hidden in:

- methods
- results
- discussion
- supplementary material
- model descriptions
- negative results
- mechanistic explanations

A simple keyword pipeline may miss the important connection.

A good design is therefore:

**full paper → structured extraction → evidence record**

rather than:

**keyword match → abstract → guess**

However, full-text access and licensing matter.

Open-access sources such as PubMed Central are much easier to use safely at scale than scraping arbitrary publisher websites.

---

## 9. GPT-6 Luna and the €130 Azure budget

Microsoft currently lists GPT-6 Luna as a low-cost model intended for high-volume work.

Current Azure Global Standard short-context pricing is:

- **$0.10 / 1M input tokens**
- **$0.50 / 1M output tokens**

Long-context requests cost more.

Luna supports structured outputs and a very large context window.

This means a €130 credit can support a large extraction experiment.

In practice, the main limits may be:

- time
- API throughput / quota
- full-text availability
- cleaning bad source data
- retries
- quality checking

rather than token cost alone.

Do not send the entire corpus in one giant prompt.

Prefer many small jobs:

**one paper → one structured record**

Then store the results in your own database.

---

## 10. Things that already exist

This is important.

The project should **not** claim that nobody has ever built a rare-disease graph.

A lot already exists.

The opportunity is to connect these pieces and make them useful for patient-led action.

### GARD — Genetic and Rare Diseases Information Center

**What it does well**

GARD is an NIH / NCATS public information service.

It gathers information from sources such as:

- Orphanet
- OMIM
- MONDO
- HPO
- MedGen
- National Library of Medicine resources

It turns this information into readable disease pages.

It can help users find:

- disease information
- symptoms
- causes
- patient organizations
- resources
- experts
- clinical studies
- help from GARD Information Specialists

GARD also uses standardized rare-disease data and NCATS has developed data-harmonization work around it, including the GARD Data Tree.

**Why it is close to the challenge**

GARD already solves a lot of the “front door”:

**Search disease → understand disease → find support/resources.**

It is patient-friendly.

It aggregates multiple sources.

It normalizes information.

It connects people to organizations and research resources.

**What it does not appear to make its main product**

GARD is not mainly a cross-disease mechanism-discovery engine.

Its public product does not primarily:

- discover hidden mechanistic connections across diseases
- build an evidence path through full scientific papers
- cluster diseases by mechanism
- identify reusable research assets across unrelated communities
- propose a shared experiment
- tell two patient groups why they should collaborate
- turn the network into a specific research “next move”

A simple way to say it:

**GARD helps you understand where you are.**

**The Buffalo Atlas should help you discover where to go next.**

### NORD Rare Disease Database

NORD provides readable rare-disease reports and support information.

Typical content includes:

- symptoms
- causes
- diagnosis
- treatments
- clinical trials
- patient organizations

It is very useful for understanding one disease.

It is not mainly a cross-disease mechanism discovery system.

### RARe-SOURCE

This is one of the closest existing projects.

RARe-SOURCE is an NCATS project designed to combine rare-disease information from separate sources.

Its goal is to connect:

- diseases
- genes
- proteins
- variants
- literature
- chemistry

It explicitly aims to help researchers find similarities and generate treatment ideas.

This overlaps strongly with the **backend idea** of the Buffalo challenge.

The challenge brief itself mentions RARe-SOURCE as an example of existing work.

So a good Buffalo project should not merely recreate RARe-SOURCE.

It should add a strong action and user layer.

### Monarch Initiative

Monarch already has a large biomedical knowledge graph.

It connects things such as:

- diseases
- genes
- phenotypes
- variants
- publications

It also has phenotype-similarity tools.

This means:

**disease → gene → phenotype graphing is not novel by itself.**

Monarch may be useful as an existing foundation.

### DisMech

DisMech is especially important for our idea.

It is a mechanism-first knowledge base developed within the Monarch ecosystem.

It uses AI-supported curation to create structured, evidence-backed disease mechanism records.

It models causal chains such as:

**genetic cause → molecular problem → cellular process → phenotype**

It also links claims to references and exact evidence snippets.

It is already exploring cross-disease mechanism similarity and drug-repurposing ideas.

This means:

**“AI reads literature and turns it into structured disease mechanisms” is also not completely new.**

This is probably the strongest warning against pitching the project as only an “AI literature compiler.”

The stronger differentiation is:

**turn those mechanisms into patient-group collaboration and an actionable next step.**

### Open Targets

Open Targets integrates evidence connecting:

- diseases
- therapeutic targets
- variants
- drugs
- studies
- literature

It is very strong for drug-target identification and prioritization.

Its main user is closer to a scientist or drug developer than a patient-group leader.

### Matchmaker Exchange

Matchmaker Exchange connects rare-disease cases across databases using genotype and phenotype information.

Its focus is especially useful for:

- finding similar patients
- matching candidate genes
- discovering genetic causes

It solves a different but related matching problem.

---

## 11. So does GARD already solve the challenge?

**Partly. Yes.**

GARD already gives the user:

**Disease → understandable information → patient groups → research/support resources.**

That is a large part of the experience.

But the Buffalo challenge asks for something further:

**Disease → hidden biological connection → related community → reusable asset → evidence → collaboration → next research step.**

That last chain is the main gap.

Another simple distinction:

### GARD asks

**“What do we know about this disease?”**

### The Atlas should ask

**“What else in the world could help this disease move forward?”**

That is the important product difference.

---

## 12. The strongest competitors / adjacent systems

If researching before building, study these first:

1. **GARD** — patient-friendly rare-disease information
2. **RARe-SOURCE** — NIH rare-disease data integration
3. **Monarch Initiative** — biomedical knowledge graph
4. **DisMech** — AI-curated mechanism graphs from literature
5. **Open Targets** — therapeutic target / drug evidence
6. **Matchmaker Exchange** — patient and gene matching
7. **NORD** — disease reports and patient organizations

The key design question is:

**What can our product do that becomes much harder when using these separately?**

---

## 13. Example diseases we discussed

### Hutchinson-Gilford Progeria Syndrome

A good prototype disease because:

- known genetic basis
- known mechanism
- substantial literature for an ultra-rare disease
- researchers and patient organizations exist
- related lamin biology creates possible cross-disease connections

### Fibrodysplasia Ossificans Progressiva (FOP)

Also a strong prototype disease because:

- strong genetic starting point
- known signaling mechanism
- enough literature
- clear opportunity to connect by pathway rather than by disease name

### Ribose-5-phosphate isomerase deficiency

Interesting as a later stress test.

There is very little disease-specific evidence.

A useful Atlas would have to move outward through:

**gene → pathway → related metabolic biology → other disorders**

### Aquagenic urticaria

Extremely rare, but a harder first demo.

Its underlying mechanism is less clearly defined.

This makes a mechanism-first graph harder to bootstrap.

### “Fields disease”

Very rare and poorly standardized in major disease resources.

Probably a bad first benchmark.

Could be useful later as a test of how the system behaves when data is extremely sparse.

---

## 14. What would make the project weak?

### Weak version

**“We put rare-disease information in a graph and added a chatbot.”**

Many existing systems already do large parts of that.

### Strong version

**“We continuously turn scattered scientific evidence into a trustworthy map that finds non-obvious cross-disease opportunities and gives a patient organization a concrete next action.”**

That is much closer to the Buffalo challenge.

---

## 15. Possible hackathon MVP

### Input

One rare disease.

### Corpus

Perhaps:

- a few thousand relevant full-text open papers
- structured disease and phenotype databases
- clinical trials
- patient organizations
- researchers
- registries / research assets

### AI processing

Use Luna for:

- extraction
- normalization assistance
- mechanism identification
- contradiction detection
- evidence classification
- cross-paper reconciliation
- plain-language explanation

### Graph

Create evidence-backed links between:

- diseases
- genes
- mechanisms
- phenotypes
- treatments
- assets
- researchers
- patient groups

### Output

Show one complete journey:

**Disease A**

→ shared mechanism

→ Disease B

→ existing asset

→ patient group / researcher

→ evidence

→ uncertainty

→ concrete next step

---

## 16. The best one-line pitch so far

> **An AI research map that finds the next useful move for a rare-disease patient group.**

A slightly more technical version:

> **We turn scattered rare-disease literature and databases into an evidence-backed mechanism graph that discovers reusable research, collaborators, and the next experiment.**

---

## 17. Key strategic insight

Do not compete with GARD, Monarch, RARe-SOURCE, or Open Targets by rebuilding their databases.

Use them where possible.

Your unique layer should be:

**connection + evidence + action.**

Or even more simply:

**Not “tell me about my disease.”**

**“Tell me what we should investigate next, and show me why.”**

---

## Sources

### Challenge brief
- *AI Atlas for the World’s Rare Diseases — OpenAI × Buffalo Initiative × Hack-Nation*, uploaded challenge brief, especially pages 2–6.

### GARD / NCATS
- [GARD](https://rarediseases.info.nih.gov/)
- [About GARD](https://rarediseases.info.nih.gov/about)
- [NCATS — GARD](https://ncats.nih.gov/research/research-resources/gard)
- [NCATS — Rare Disease Translational Research](https://ncats.nih.gov/research/research-activities/informatics/rare-disease-translational-research)

### Existing related systems
- [RARe-SOURCE — NCATS](https://ncats.nih.gov/research/research-activities/rare-source)
- [Monarch Initiative](https://monarchinitiative.org/)
- [DisMech](https://dismech.monarchinitiative.org/)
- [Open Targets Platform](https://platform.opentargets.org/)
- [Matchmaker Exchange](https://www.matchmakerexchange.org/)
- [NORD Rare Disease Database](https://rarediseases.org/rare-diseases/)

### GPT-6 Luna / Azure
- [Microsoft — GPT-6 Astra, Sol and Luna](https://azure.microsoft.com/en-us/blog/gpt-6-astra-sol-and-luna-for-production-agents-in-microsoft-foundry/)
- [Microsoft Learn — Azure OpenAI reasoning models](https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning)

---

## Final working mental model

**Existing systems give you pieces of the map.**

**Luna can help read and structure the messy literature.**

**The knowledge graph connects the pieces.**

**The product should turn those connections into a next move.**
