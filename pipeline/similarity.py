"""Similarity between items described by sets of terms, weighting rare terms more than common ones.

Used for symptoms (HPO terms per condition) and for molecular machinery (complexes, pathways,
GO terms, interaction partners per gene). Each item's set should already include ancestor terms.
A term's information content is IC = -ln(share of items that have it); similarity is simGIC:
the IC of the shared terms divided by the IC of all terms either item has.
"""

from dataclasses import dataclass

import numpy as np
from scipy import sparse


@dataclass
class SharedTerm:
    term: str
    ic: float
    count: int  # how many items in the index have this term


class IcIndex:
    def __init__(self, sets: dict[str, set[str]]):
        self.ids = sorted(k for k, v in sets.items() if v)
        self.row = {k: i for i, k in enumerate(self.ids)}
        self.sets = {k: frozenset(sets[k]) for k in self.ids}
        self.vocab = sorted(set().union(*self.sets.values())) if self.ids else []
        self.col = {t: j for j, t in enumerate(self.vocab)}
        rows = [i for i, k in enumerate(self.ids) for _ in self.sets[k]]
        cols = [self.col[t] for k in self.ids for t in self.sets[k]]
        self.matrix = sparse.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)),
                                        shape=(len(self.ids), len(self.vocab)))
        self.counts = np.asarray(self.matrix.sum(axis=0)).ravel()
        self.ic = (-np.log(self.counts / max(len(self.ids), 1))).astype(np.float32)
        self.weighted = self.matrix.multiply(self.ic).tocsr()
        self.total = np.asarray(self.weighted.sum(axis=1)).ravel()

    def __contains__(self, item: str) -> bool:
        return item in self.row

    def term_ic(self, term: str) -> float:
        return float(self.ic[self.col[term]])

    def term_count(self, term: str) -> int:
        return int(self.counts[self.col[term]])

    def top_k(self, queries: list[str], candidates: list[str], k: int, chunk: int = 512) -> dict[str, list[tuple[str, float]]]:
        """For each query item, the k most similar candidate items (excluding itself), by simGIC."""
        q_rows = [self.row[q] for q in queries if q in self.row]
        c_items = [c for c in candidates if c in self.row]
        c_rows = np.array([self.row[c] for c in c_items])
        cand_t = self.matrix[c_rows].T.tocsc()
        c_total = self.total[c_rows]
        out: dict[str, list[tuple[str, float]]] = {}
        for start in range(0, len(q_rows), chunk):
            block = q_rows[start:start + chunk]
            shared = (self.weighted[block] @ cand_t).toarray()
            union = self.total[block][:, None] + c_total[None, :] - shared
            sim = np.divide(shared, union, out=np.zeros_like(shared), where=union > 0)
            for i, r in enumerate(block):
                item = self.ids[r]
                row = sim[i]
                n = min(k + 1, len(row))
                best = np.argpartition(-row, n - 1)[:n]
                ranked = sorted(((c_items[j], float(row[j])) for j in best if c_items[j] != item and row[j] > 0), key=lambda x: -x[1])
                out[item] = ranked[:k]
        return out

    def dense(self, queries: list[str], candidates: list[str]) -> np.ndarray:
        """simGIC matrix (len(queries) x len(candidates)); rows/columns of items not in the index are 0."""
        out = np.zeros((len(queries), len(candidates)), dtype=np.float32)
        qi = [(i, self.row[q]) for i, q in enumerate(queries) if q in self.row]
        ci = [(j, self.row[c]) for j, c in enumerate(candidates) if c in self.row]
        if not qi or not ci:
            return out
        q_pos, q_rows = zip(*qi)
        c_pos, c_rows = zip(*ci)
        shared = (self.weighted[list(q_rows)] @ self.matrix[list(c_rows)].T).toarray()
        union = self.total[list(q_rows)][:, None] + self.total[list(c_rows)][None, :] - shared
        sim = np.divide(shared, union, out=np.zeros_like(shared), where=union > 0)
        out[np.ix_(q_pos, c_pos)] = sim
        return out

    def similarity(self, a: str, b: str) -> float:
        if a not in self.row or b not in self.row:
            return 0.0
        shared = sum(self.term_ic(t) for t in self.sets[a] & self.sets[b])
        union = self.total[self.row[a]] + self.total[self.row[b]] - shared
        return float(shared / union) if union > 0 else 0.0

    def shared_terms(self, a: str, b: str) -> list[SharedTerm]:
        """Terms both items have, most informative first."""
        if a not in self.row or b not in self.row:
            return []
        terms = self.sets[a] & self.sets[b]
        return sorted((SharedTerm(t, self.term_ic(t), self.term_count(t)) for t in terms), key=lambda s: -s.ic)
