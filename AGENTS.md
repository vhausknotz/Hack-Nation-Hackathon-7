# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, Cursor, …) working in this repo.

## Project

Hack-Nation 7th Global AI Hackathon, **Challenge 05: AI Atlas for the World's Rare Diseases** (OpenAI × Buffalo Initiative). One developer working with AI agents. The goal is a **great, deployed product** that someone new understands instantly, even though the system underneath is complex. The submission also needs a short walkthrough video, but that is not a design driver.

## Read first

1. [PLAN.md](PLAN.md): what we build, how and why. This is the source of truth for decisions.
2. [CHALLENGE_BRIEF.md](CHALLENGE_BRIEF.md): the challenge brief, transcribed. Use it instead of the PDF.
3. [docs/buffalo_initiative.md](docs/buffalo_initiative.md): who the sponsor is and what they care about.

`buffalo_rare_disease_atlas_notes.md` is an early ChatGPT brainstorm. Treat it as ideas, not decisions.

## Repo layout (planned)

```
pipeline/     Python: download → normalize → extract (AI) → verify → build graph → analytics
data/raw/     downloaded source files (gitignored, re-downloadable)
data/cache/   cached LLM and API responses (gitignored)
data/build/   built graph data the app ships with
app/          web app (search → answer page → evidence → proposal)
docs/         research notes and decisions
```

## Azure OpenAI (Foundry)

- **Resource:** `valiOpenAI` (Sweden Central). OpenAI-compatible base URL: `https://valiopenai.cognitiveservices.azure.com/openai/v1/`. Pass the **deployment name** as `model`.
- **Which model for what:**
  - `gpt-6-luna`: bulk extraction (cheap, high volume)
  - `gpt-6-sol`: reconciliation decisions, verification, plain-language explanations, proposals
  - `text-embedding-3-large`: entity matching and semantic search (3072 dimensions)
  - Also deployed: `gpt-5.4-mini`, `gpt-5.4-nano`, `o4-mini`
- **Local auth:** Entra ID through the user's Az PowerShell login. Azure CLI is *not* installed. No API key needed. If auth fails, ask the user to run `Connect-AzAccount`. Tested and working:

  ```python
  from azure.identity import DefaultAzureCredential, get_bearer_token_provider
  from openai import OpenAI

  token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
  client = OpenAI(base_url="https://valiopenai.cognitiveservices.azure.com/openai/v1/", api_key=token)
  client.chat.completions.create(model="gpt-6-luna", messages=[...])
  ```

- **Python env:** `.venv/` at repo root (Python 3.11; `openai`, `azure-identity` installed). Run with `./.venv/Scripts/python`.
- **Deployed app:** server-side env var `AZURE_OPENAI_API_KEY` only. Never put it in client code and never commit it. Keep secrets in `.env` (gitignored) and document variable names in `.env.example`.
- **Cache every LLM call** on disk under `data/cache/`, keyed by a hash of model + prompt. Reruns are then free, and the dataset is reproducible from the README.

## Evidence rules (non-negotiable; judges score this)

- No claim without a source. AI-extracted claims must include a quote that is found **verbatim** in the source text, or the claim is dropped.
- Every edge records source (ID + URL), date, confidence, evidence tier (`data` | `hypothesis` | `clinical_proof`) and how it was made (database import, AI extraction with model name, or analytics inference).
- AI inferences are always labeled `hypothesis`, never shown as fact.
- When evidence is missing, say so and show what was searched.
- Public, professional contact information only. No patient data. Not medical advice.

## Working preferences

- Don't put time estimates on tasks or plans. Describe steps by what they produce.
- Clarity beats feature count. Every screen should make sense at a glance; depth goes behind a click.
- Respect data licenses and site terms. OMIM restricts redistribution, so reference OMIM IDs through HPO and MONDO crosswalks.
