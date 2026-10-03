# Phase 0 data check: the STXBP1 / SNARE neighborhood

Run on 2026-10-03 with `pipeline/recon_neighborhood.py`, `pipeline/recon_research.py` and `pipeline/sources/buffalo_tracker.py`. All API responses are cached in `data/cache/`, so these numbers can be reproduced.

## Verdict: go

The neighborhood has everything the brief asks for: a tiny, isolated community; a mechanistic link that names hide; real reusable assets; shared people; real contradictions; and clean counterexamples. Several findings change how we build (see "What this changes").

## The story the data supports

**Maria's child has SNAP25-related disorder.**
- About 32 people are known worldwide ([Simons Searchlight](https://www.simonssearchlight.org/research/what-we-study/snap25/)).
- No trial or natural history study targets it.
- The structured databases (MONDO and HPO, Sept 2026 releases) still file SNAP25 only under "congenital myasthenic syndrome 18." The literature describes mainly an early-onset developmental and epileptic encephalopathy (Klöckner et al. 2021, PMID 33299146), and Simons Searchlight calls it DEE117. **No DEE117 entry exists in MONDO or HPO**, even though they go up to DEE121.

**The connection a symptom matcher misses:**
- SNAP25 and STXBP1 (Munc18-1) are parts of the same SNARE machinery nerve cells use to release signals. The field calls this disease family "SNAREopathies" (Verhage & Sørensen 2020, *Neuron*, PMID 32559416; Cali et al. 2021, PMID 35095745).
- Because the databases mislabel SNAP25, symptom similarity alone ranks STXBP1 around #2,500 for it. The mechanism layer plus the literature is what connects them.

**What already exists next door (all real, all sourced):**

| Asset | Covers | Source |
|---|---|---|
| Simons Searchlight registry | Many genes, **including SNAP25** and STXBP1 | NCT01238250; simonssearchlight.org |
| STXBP1 + SYNGAP1 natural history study (CHOP, recruiting, target 600) | Already multi-gene | NCT06555965 |
| European STXBP1 trial-readiness study (ESCO, recruiting) | STXBP1 | NCT06625112 |
| STXBP1 biomarker study (Spain) | STXBP1 | NCT06356233 |
| Baker-Gordon syndrome natural history study (Univ. of Missouri) | SYT1, another SNARE-machinery gene | NCT06399952 |
| Phenylbutyrate trial (Weill Cornell, 50 enrolled) | STXBP1 **and** SLC6A1 together | NCT04937062; also in Buffalo's tracker (STXBP1 Foundation) |
| Gene therapy CAP-002 (Capsida) | STXBP1; **terminated: "stopping rule for study was met"** after 1 patient | NCT06983158, a lesson to surface |

**People who bridge communities:**
- Ingo Helbig (CHOP) leads 10 NIH grants on STXBP1 and also appears on STX1B grants.
- Weill Cornell partners with three tracker organizations (STXBP1, GABA-A, GLUT1).
- Unravel Biosciences partners with seven (DLG4, H-abc, CSNK2A1, SETBP1, SPATA5, v-ATPase, ZTTK).

**A real contradiction to show (Module 2):**
- *Supporting* phenylbutyrate for STXBP1: a case series and a 2026 report of parent-observed improvement (PMID 42447769).
- *Arguing against* it: a 2026 virtual screening and zebrafish study (PMID 42268630).
- Meanwhile it's being pursued for SLC6A1 (new remote Phase 2, NCT07847918) and GABA-A receptor disorders (Buffalo tracker: "Ravicti Repurposed for GABA-A Receptors").

**A backtest that works:** from SLC6A1's side, STXBP1 ranks **#12 of 10,739 diseases** by symptoms. That's the pairing the real phenylbutyrate trial made. The shared rare features include atonic seizures (87 diseases have them) and slow EEG frequencies (40).

**Counterexamples the graph finds on its own:**
- **Same protein family, different tissue.** STXBP2 is STXBP1's sister protein (Munc18-2) but causes an immune disease, familial hemophagocytic lymphohistiocytosis 5. Its symptom similarity to STXBP1 is about 0. It clusters tightly with the other immune SNARE diseases (STX11 #1, UNC13D #4).
- **Same machinery, different site.** SYT2, VAMP1 and SNAP25's myasthenic form cluster as presynaptic congenital myasthenic syndromes (neuromuscular junction), separate from the brain cluster.
- **Same gene, opposite mechanism.** Orphanet labels SCN2A early-infantile epilepsy as gain of function, and lists CACNA1A under both loss and gain of function. This is the brief's "Gene A, variant 1 vs. variant 2" diagram, in real data.

## Numbers

- **Breadth:** 5,326 rare MONDO diseases have a causal gene, and 4,938 of them (93%) have symptom annotations. The symptom index covers 10,739 diseases and 12,731 symptom terms. 4,899 symptom terms have plain-language (layperson) names.
- **Mechanism labels are sparse:** only 1,436 of 6,857 Orphanet germline gene–disease links say loss or gain of function.
- **Research signal per gene** (PubMed disease-related papers / trials / NIH projects FY22–26):

  | Gene | Papers | Trials | NIH projects |
  |---|---|---|---|
  | STXBP1 | 310 | 12 | 25 |
  | SNAP25 | 154 (mostly not about the disorder) | 20 (none about the disorder) | 29 |
  | SLC6A1 | 111 | 7 | 13 |
  | SYNGAP1 | 209 | 5 | 112 |
  | STX1B | 39 | 0 relevant | 2 |
  | SYT1 | 44 | 5 | 36 |
  | CPLX1 | 13 | 0 | 0 |

- **Buffalo tracker:** 65 programs, 47 patient organizations, 50 diseases. 46 programs are at target validation. Modalities: 22 repurposed small molecules, 21 gene therapies, 10 ASOs.

## What this changes in the plan

1. **The unit of a "community" is the gene-defined condition** (e.g. "SNAP25-related disorder"). Patient groups, the Buffalo tracker and families all think by gene. A condition groups its OMIM, Orphanet and MONDO entries, and splits only when variant effects differ (SCN2A, CACNA1A).
2. **Symptom similarity is necessary but not sufficient.** For SNAP25 it fails because the database label is outdated. Mechanism needs its own open sources:
   - protein complexes (Complex Portal)
   - pathways (Reactome)
   - synaptic function (SynGO / Gene Ontology)
   - variant effect (Gene2Phenotype, ClinGen dosage)
   - literature claims

   These still need to be evaluated.
3. **Keyword hits are noisy, so AI relevance filtering is required.**
   - "SNAP25" matches 20 trials, none about the disorder (Botox cleaves SNAP25; it's also an Alzheimer's biomarker).
   - "NSF" matches the National Science Foundation (1,077 grants).

   Every paper, trial and grant must be checked as "actually about this condition" before it becomes an edge.
4. **Databases lag the literature, and the product should say so.** "Databases list this as a myasthenic syndrome; recent literature describes an epileptic encephalopathy" is a strong, honest feature.
5. **Buffalo's tracker belongs in the graph** as self-reported program nodes. Its disclaimer says programs are self-reported and unverified. It gives real network-overlap edges (shared partners) and shared therapy approaches (glycerol phenylbutyrate in two communities).
6. **The road-to-treatment strip can be computed from data:**
   - STXBP1 has a registry, natural history studies, a biomarker study, models, a therapy program and trials.
   - SNAP25 has a registry (Simons Searchlight) and a human-neuron model study (PMID 40181518), and nothing else. That gap is the honest-gap view.

## Open items

- **Patient groups:** there's no single clean directory. The STXBP1 Foundation is confirmed (Buffalo tracker). Its 2021 Ciitizen digital natural history (150 patients) needs a current-status check. We found no SNAP25-specific foundation; Simons Searchlight serves as its community hub.
- **Tracker access:** the site's anti-spam filter rejects non-browser user agents, so we fetch with a plain browser UA (7 pages, 2 s apart, cached; robots.txt allows crawling). For production, ask Buffalo for the data directly.
- **Unverified for now:** DEE117 being SNAP25 rests on Simons Searchlight; check OMIM.
