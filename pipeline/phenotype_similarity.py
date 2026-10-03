"""Symptom similarity between diseases, weighting rare symptoms more than common ones.

Each disease is the set of its annotated HPO terms plus all their ancestors. A term's
information content (IC) is -ln(share of diseases that have it), so "Seizure" (shared by
hundreds of diseases) counts little and an unusual sign counts a lot. Similarity is simGIC:
the IC of the terms both diseases share divided by the IC of all terms either one has.
"""

from dataclasses import dataclass

import numpy as np
from scipy import sparse

from sources.hpo import Ontology


@dataclass
class SharedSymptom:
    hpo_id: str
    name: str
    plain_name: str
    ic: float
    disease_count: int  # how many diseases in the index have this symptom (or a more specific one)


class PhenotypeIndex:
    def __init__(self, ontology: Ontology, disease_terms: dict[str, set[str]]):
        self.ontology = ontology
        self.ids = sorted(d for d, terms in disease_terms.items() if terms)
        self.row = {d: i for i, d in enumerate(self.ids)}
        self.closures = []
        for d in self.ids:
            closure = set()
            for t in disease_terms[d]:
                closure |= ontology.ancestors(t)
            self.closures.append({t for t in closure if ontology.is_phenotypic_abnormality(t)})
        vocab = sorted(set().union(*self.closures))
        self.col = {t: j for j, t in enumerate(vocab)}
        rows = [i for i, c in enumerate(self.closures) for _ in c]
        cols = [self.col[t] for c in self.closures for t in c]
        self.matrix = sparse.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(len(self.ids), len(vocab)))
        self.counts = np.asarray(self.matrix.sum(axis=0)).ravel()
        self.ic = -np.log(self.counts / len(self.ids))
        self.total_ic = self.matrix @ self.ic

    def __contains__(self, disease_id: str) -> bool:
        return disease_id in self.row

    def scores(self, disease_id: str) -> np.ndarray:
        """simGIC of one disease against every disease in the index (aligned with self.ids)."""
        i = self.row[disease_id]
        weighted = self.matrix[i].multiply(self.ic).toarray().ravel()
        shared = self.matrix @ weighted
        union = self.total_ic + self.total_ic[i] - shared
        return np.divide(shared, union, out=np.zeros_like(shared), where=union > 0)

    def similar(self, disease_id: str, top: int = 20) -> list[tuple[str, float]]:
        s = self.scores(disease_id)
        s[self.row[disease_id]] = -1
        order = np.argsort(-s)[:top]
        return [(self.ids[j], float(s[j])) for j in order]

    def rank_of(self, disease_id: str, other_id: str) -> tuple[int, float]:
        """1-based rank of other_id among all diseases most similar to disease_id."""
        s = self.scores(disease_id)
        s[self.row[disease_id]] = -1
        score = s[self.row[other_id]]
        return int((s > score).sum()) + 1, float(score)

    def shared_symptoms(self, a: str, b: str, top: int = 10) -> list[SharedSymptom]:
        """The most specific symptoms both diseases share, most informative first."""
        shared = self.closures[self.row[a]] & self.closures[self.row[b]]
        specific = self.ontology.most_specific(shared)
        out = [
            SharedSymptom(t, self.ontology.label(t), self.ontology.label(t, plain=True),
                          float(self.ic[self.col[t]]), int(self.counts[self.col[t]]))
            for t in specific
        ]
        return sorted(out, key=lambda s: -s.ic)[:top]
