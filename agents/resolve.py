"""Resolver: map free-text symptom descriptions to HPO terms.

1. exact match on HPO names, synonyms and plain-language names (normalized)
2. otherwise: nearest HPO terms by embedding (text-embedding-3-large), and GPT-6 Sol picks the right
   one or says none fits. The method used is recorded with every resolution.
"""

import json
import re

import numpy as np

from . import ROOT  # noqa: F401  (sets up sys.path)
import llm  # noqa: E402
from sources import hpo  # noqa: E402

CACHE = ROOT / "data" / "cache" / "hpo_embeddings"
EMBED_MODEL = "text-embedding-3-large"
DECIDE_MODEL = "gpt-6-sol"


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class HpoResolver:
    def __init__(self):
        self.onto = hpo.load_ontology()
        self.terms = [t for t in self.onto.terms.values() if self.onto.is_phenotypic_abnormality(t.id)]
        self.exact: dict[str, str] = {}
        for t in self.terms:
            for name in [t.name] + t.synonyms + t.layperson:
                self.exact.setdefault(norm(name), t.id)
        self._vectors = None

    def _embeddings(self) -> tuple[list[str], np.ndarray]:
        if self._vectors is None:
            CACHE.mkdir(parents=True, exist_ok=True)
            ids_path, vec_path = CACHE / "ids.json", CACHE / "vectors.npy"
            if ids_path.exists() and vec_path.exists():
                ids, vecs = json.loads(ids_path.read_text()), np.load(vec_path)
            else:
                ids = [t.id for t in self.terms]
                texts = [f"{t.name}. {t.definition[:200]}" for t in self.terms]
                vecs = []
                for i in range(0, len(texts), 256):
                    resp = llm.client().embeddings.create(model=EMBED_MODEL, input=texts[i:i + 256])
                    vecs.extend(d.embedding for d in resp.data)
                vecs = np.asarray(vecs, dtype=np.float32)
                vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
                ids_path.write_text(json.dumps(ids))
                np.save(vec_path, vecs)
            self._vectors = (ids, vecs)
        return self._vectors

    def candidates(self, text: str, k: int = 6) -> list[tuple[str, float]]:
        ids, vecs = self._embeddings()
        q = np.asarray(llm.client().embeddings.create(model=EMBED_MODEL, input=[text]).data[0].embedding, dtype=np.float32)
        q /= np.linalg.norm(q)
        sims = vecs @ q
        best = np.argsort(-sims)[:k]
        return [(ids[i], float(sims[i])) for i in best]

    def resolve(self, text: str, context: str = "") -> dict | None:
        """{"hpo_id", "method", "confidence"} or None when no HPO term fits."""
        key = norm(text)
        if key in self.exact:
            return {"hpo_id": self.exact[key], "method": "exact-name", "confidence": 1.0}
        if key.endswith("s") and key[:-1] in self.exact:
            return {"hpo_id": self.exact[key[:-1]], "method": "exact-name", "confidence": 0.98}
        cands = self.candidates(text)
        options = [{"id": c, "name": self.onto.terms[c].name, "definition": self.onto.terms[c].definition[:220]} for c, _ in cands]
        reply = llm.chat_json(DECIDE_MODEL, [
            {"role": "system", "content": (
                "Map a clinical feature, as written in a paper, to one Human Phenotype Ontology term. "
                "Choose the option that means the same thing (a slightly broader term is acceptable; a narrower or different one is not). "
                'Return JSON {"choice": <option id or null>, "reason": <short>}.')},
            {"role": "user", "content": json.dumps({"feature": text, "context": context[:300], "options": options}, ensure_ascii=False)},
        ], task="resolve-hpo")
        choice = reply.get("choice")
        if choice in {c for c, _ in cands}:
            return {"hpo_id": choice, "method": f"embedding+{DECIDE_MODEL}", "confidence": dict(cands)[choice]}
        return None
