"""The kernel: small, deterministic checks that every claim must pass. No language model in here.

It never decides whether a claim is true. It decides whether the claim is well-formed,
refers to identifiers that exist, cites archived sources whose bytes match their hashes,
quotes them verbatim at the stated offsets, cites pinned datasets, and is signed by a
registered contributor. See PLAN.md section 3 for what it does not guarantee.
"""

from dataclasses import asdict, dataclass

from . import identity
from .canonical import canonical_json, canonical_quote, sha256
from .schema import EVIDENCE_FIELDS, PREDICATES, QUALIFIER_VALUES, TEXT_EVIDENCE, kind_of
from .sources import read_raw, read_text

KERNEL_VERSION = "kernel@1"
MAX_TEXT_OBJECT = 500
MAX_QUOTE = 2000
ALLOWED_RECIPES = {"symptom-simgic@1", "mechanism-weighted@1", "combined-similarity@1"}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)


class Kernel:
    def __init__(self, registry, store, archive_root=None):
        self.registry = registry
        self.store = store
        self.archive_root = archive_root

    # ---- schema ---------------------------------------------------------------------------------------
    def check_schema(self, claim: dict) -> Check:
        try:
            a, evidence, prov = claim["assertion"], claim["evidence"], claim["provenance"]
        except (KeyError, TypeError):
            return Check("schema", False, "claim needs assertion, evidence and provenance")
        pred = PREDICATES.get(a.get("predicate", ""))
        if pred is None:
            return Check("schema", False, f"unknown predicate {a.get('predicate')!r}")
        s_kind = kind_of(str(a.get("subject", "")))
        if s_kind not in pred.subjects:
            return Check("schema", False, f"subject {a.get('subject')!r} is a {s_kind}, {a['predicate']} needs {'/'.join(pred.subjects)}")
        obj = a.get("object")
        if pred.objects == ("text",):
            if not isinstance(obj, str) or not obj.strip() or len(obj) > MAX_TEXT_OBJECT:
                return Check("schema", False, "text object must be a non-empty string under 500 characters")
        elif kind_of(str(obj)) not in pred.objects:
            return Check("schema", False, f"object {obj!r} is a {kind_of(str(obj))}, {a['predicate']} needs {'/'.join(pred.objects)}")
        for key, value in a.get("qualifiers", {}).items():
            if key not in pred.qualifiers:
                return Check("schema", False, f"qualifier {key!r} not allowed for {a['predicate']}")
            allowed = QUALIFIER_VALUES.get(key)
            if allowed is not None and value not in allowed:
                return Check("schema", False, f"qualifier {key}={value!r} not in {sorted(allowed)}")
            if not isinstance(value, (str, int, float)):
                return Check("schema", False, f"qualifier {key} must be a scalar")
        if not isinstance(evidence, list) or not evidence:
            return Check("schema", False, "at least one evidence item is required")
        for item in evidence:
            required = EVIDENCE_FIELDS.get(item.get("type", ""))
            if required is None:
                return Check("schema", False, f"unknown evidence type {item.get('type')!r}")
            if missing := required - set(item):
                return Check("schema", False, f"{item['type']} evidence is missing {sorted(missing)}")
        for key in ("contributor", "agent", "created"):
            if not prov.get(key):
                return Check("schema", False, f"provenance needs {key}")
        return Check("schema", True)

    # ---- identifiers --------------------------------------------------------------------------------------
    def check_identifiers(self, claim: dict) -> Check:
        a = claim["assertion"]
        entities = [a["subject"]] + ([] if PREDICATES[a["predicate"]].objects == ("text",) else [a["object"]])
        if gene := a.get("qualifiers", {}).get("gene"):
            if kind_of(gene) != "gene":
                return Check("identifiers", False, f"qualifier gene={gene!r} is not an HGNC ID")
            entities.append(gene)
        for e in entities:
            if self.registry.exists(kind_of(e), e) is False:
                return Check("identifiers", False, f"{e} does not exist in the pinned registry")
        return Check("identifiers", True, getattr(self.registry, "version", ""))

    # ---- evidence: archived sources, verbatim quotes, pinned datasets ------------------------------------------
    def check_evidence(self, claim: dict, contributor_kind: str | None = None) -> Check:
        for i, item in enumerate(claim["evidence"]):
            t = item["type"]
            if t in TEXT_EVIDENCE:
                source = self.store.source(item["source_id"])
                if source is None:
                    return Check("evidence", False, f"evidence {i}: source {item['source_id']} is not archived")
                if self.archive_root is None:
                    text, raw = read_text(source), read_raw(source)
                else:
                    text, raw = read_text(source, root=self.archive_root), read_raw(source, root=self.archive_root)
                if text is None or raw is None:
                    return Check("evidence", False, f"evidence {i}: archived files for {item['source_id']} are missing")
                if sha256(text.encode("utf-8")) != source["text_hash"] or sha256(raw) != source["raw_hash"]:
                    return Check("evidence", False, f"evidence {i}: archived source does not match its hashes")
                start, end, quote = item["start"], item["end"], item["quote"]
                if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text)):
                    return Check("evidence", False, f"evidence {i}: offsets out of range")
                if len(quote) > MAX_QUOTE:
                    return Check("evidence", False, f"evidence {i}: quote longer than {MAX_QUOTE} characters")
                if canonical_quote(text[start:end]) != canonical_quote(quote):
                    return Check("evidence", False, f"evidence {i}: quote does not appear verbatim at the stated offsets")
            elif t == "curated_database":
                try:
                    pinned = self.registry.dataset_hash(item["dataset"])
                except FileNotFoundError:
                    return Check("evidence", False, f"evidence {i}: dataset {item['dataset']} is not pinned")
                if pinned != item["dataset_hash"]:
                    return Check("evidence", False, f"evidence {i}: dataset hash differs from the pinned version")
            elif t == "computed":
                if item["recipe"] not in ALLOWED_RECIPES:
                    return Check("evidence", False, f"evidence {i}: recipe {item['recipe']!r} is not a declared recipe")
            elif t == "expert_statement":
                if contributor_kind != "human":
                    return Check("evidence", False, f"evidence {i}: expert statements must come from a human contributor")
        return Check("evidence", True)

    # ---- signature --------------------------------------------------------------------------------------
    def check_signature(self, claim: dict, signature: str | None) -> Check:
        contributor = self.store.contributor(claim["provenance"]["contributor"])
        if contributor is None:
            return Check("signature", False, "contributor is not registered")
        if not signature or not identity.verify(contributor["public_key"], canonical_json(claim), signature):
            return Check("signature", False, "signature does not verify against the contributor's key")
        return Check("signature", True)

    def check_claim(self, claim: dict, signature: str | None = None, verify_signature: bool = True) -> list[Check]:
        schema = self.check_schema(claim)
        if not schema.passed:
            return [schema]
        checks = [schema, self.check_identifiers(claim)]
        contributor = self.store.contributor(claim["provenance"]["contributor"])
        checks.append(self.check_evidence(claim, contributor["kind"] if contributor else None))
        if verify_signature:
            checks.append(self.check_signature(claim, signature))
        return checks
