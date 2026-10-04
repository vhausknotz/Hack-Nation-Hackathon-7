"""Symptom vocabulary for contributors: HPO phenotypic-abnormality terms with names and synonyms.

Agents must cite stable HP IDs; this index lets them find the right one from everyday or
clinical wording. Build: python -m atlas_mcp.terms (writes data/build/hpo_terms.json).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data/build/hpo_terms.json"


def build(out=INDEX):
    sys.path.insert(0, str(ROOT / "pipeline"))
    from sources import hpo
    onto = hpo.load_ontology()
    terms = {t.id: [t.name, *t.layperson[:4], *t.synonyms[:8]] for t in onto.terms.values() if onto.is_phenotypic_abnormality(t.id)}
    out.write_text(json.dumps(terms, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"terms": len(terms), "path": str(out)}


def words(text):
    return re.findall(r"[a-z0-9]+", text.casefold())


def search(index, query, limit=10):
    """Rank terms by exact name, then all query words present, then partial overlap."""
    q = query.strip().casefold()
    if not 2 <= len(q) <= 120:
        raise ValueError("Search symptom terms with 2–120 characters")
    if re.fullmatch(r"hp:\d{7}", q):
        hid = q.upper()
        return [{"id": hid, "name": index[hid][0], "synonyms": index[hid][1:6]}] if hid in index else []
    qw = set(words(q))
    ranked = []
    for hid, names in index.items():
        best = None
        for i, name in enumerate(names):
            n = name.casefold()
            if n == q:
                score = 0 if i == 0 else 1
            else:
                nw = set(words(n))
                if qw <= nw:
                    score = 2 + len(nw - qw) * 0.1
                elif qw & nw and len(qw & nw) >= max(1, len(qw) - 1):
                    score = 5 + len(qw - nw) + len(nw - qw) * 0.1
                else:
                    continue
            best = score if best is None else min(best, score)
        if best is not None:
            ranked.append((best, len(names[0]), hid))
    ranked.sort()
    return [{"id": hid, "name": index[hid][0], "synonyms": index[hid][1:6]} for _, _, hid in ranked[:limit]]


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
