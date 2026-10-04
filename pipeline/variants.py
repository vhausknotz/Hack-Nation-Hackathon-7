"""Variant-level evidence from ClinVar: what has been reported in each gene, and for which atlas condition.

    python pipeline/variants.py [--upload]

Downloads ClinVar's weekly variant_summary (about 450 MB, kept for six days) and writes
    data/build/variants_summary.json   condition id -> counts by classification and variant type, most-reported variants
    data/build/variants/<SYMBOL>.json  gene -> compact list of every germline ClinVar variant (the website's look-up)
With --upload the per-gene files that changed go to blob storage (variants/<SYMBOL>.json); the MCP host serves them
publicly at /variants/<SYMBOL>, so the static website does not grow.

Germline records on GRCh38 only. A variant counts for a condition when the submitting lab named that condition's
disease for the same gene (MONDO, OMIM or Orphanet identifier, or the MONDO parent of a gene-specific split such as
"MELAS caused by mutation in MT-TL1"). The variant type is read from the HGVS description. No language model is used.
"""
import gzip
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"
RAW = ROOT / "data" / "raw" / "clinvar_variant_summary.txt.gz"
OUT_DIR = BUILD / "variants"
SUMMARY = BUILD / "variants_summary.json"
URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
MAX_PER_GENE = 6000
# Too general to say which disease the lab meant.
GENERIC = {"MONDO:0003847", "MONDO:0700096", "MONDO:0000001", "MONDO:0019052"}

STARS = {"practice guideline": 4, "reviewed by expert panel": 3, "criteria provided, multiple submitters, no conflicts": 2,
         "criteria provided, conflicting classifications": 1, "criteria provided, single submitter": 1}
CLASS_ORDER = {"P": 0, "LP": 1, "C": 2, "VUS": 3, "LB": 4, "B": 5, "O": 6}
NAME = re.compile(r"^(?P<tx>[^\s(:]+)(?:\([^)]*\))?:(?P<c>[cmgn]\.\S+)(?:\s+\((?P<p>p\.[^)]+)\))?")
MISSENSE = re.compile(r"p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{2}")


def download() -> str:
    """The local copy of ClinVar's release; returns its release date."""
    RAW.parent.mkdir(parents=True, exist_ok=True)
    head = requests.head(URL, timeout=60)
    head.raise_for_status()
    release = parsedate_to_datetime(head.headers["Last-Modified"]).date().isoformat()
    stamp = RAW.with_suffix(".release")
    if RAW.exists() and stamp.exists() and stamp.read_text().strip() == release:
        return release
    temp = RAW.with_suffix(".part")
    with requests.get(URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with temp.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    temp.replace(RAW)
    stamp.write_text(release)
    return release


def classify(text: str) -> str:
    t = text.lower()
    if "conflicting" in t:
        return "C"
    if t.startswith("pathogenic"):
        return "P"
    if t.startswith("likely pathogenic"):
        return "LP"
    if t.startswith("uncertain significance"):
        return "VUS"
    if t.startswith("likely benign"):
        return "LB"
    if t.startswith("benign"):
        return "B"
    return "O"


def kind(c: str | None, p: str | None, vtype: str) -> str:
    """Variant type from the HGVS description, in words a family's report uses."""
    if vtype.lower().startswith("copy number") or not c:
        return "large"
    if c.startswith("m."):
        return "mitochondrial"
    if p:
        if "fs" in p:
            return "frameshift"
        if "=" in p:
            return "synonymous"
        if re.match(r"p\.Met1(?!\d)", p):
            return "start"
        if p.endswith(("Ter", "*")):
            return "nonsense"
        if any(k in p for k in ("del", "ins", "dup")):
            return "inframe"
        if MISSENSE.fullmatch(p):
            return "missense"
        return "other"
    if re.search(r"\d[+-][12](?!\d)", c):
        return "splice"
    if re.search(r"\d[+-]\d", c):
        return "intronic"
    if c.startswith(("c.-", "c.*")):
        return "untranslated"
    return "other"


def mondo_parents() -> dict[str, set[str]]:
    parents, current = defaultdict(set), None
    with (ROOT / "data/raw/mondo.obo").open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("id: "):
                current = line[4:].strip()
            elif line.startswith("is_a: ") and current:
                parents[current].add(line[6:].split()[0])
    return parents


def condition_keys():
    """gene HGNC id -> [(condition id, identifiers a lab may have used for it)]."""
    parents = mondo_parents()
    by_gene = defaultdict(list)
    for line in (BUILD / "conditions.jsonl").read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        c = json.loads(line)
        keys = {c["disease"]} | {x for k in ("OMIM", "Orphanet") for x in c.get("xrefs", {}).get(k, [])}
        if c["disease"].startswith("MONDO:0800") or c.get("synthetic"):  # gene-specific splits: labs name the parent
            keys |= parents.get(c["disease"], set())
        by_gene[c["gene"]["hgnc_id"]].append((c["id"], keys - GENERIC, c["gene"]["symbol"]))
    return by_gene


def phenotype_ids(field: str) -> list[set[str]]:
    out = []
    for entry in field.split("|"):
        ids = set()
        for raw in entry.split(","):
            raw = raw.strip()
            if raw.startswith("MONDO:MONDO:"):
                ids.add(raw[6:])
            elif raw.startswith(("OMIM:", "Orphanet:")):
                ids.add(raw)
        out.append(ids)
    return out


def build(release: str) -> tuple[dict, dict]:
    by_gene = condition_keys()
    genes: dict[str, dict] = {}
    seen: dict[str, set] = defaultdict(set)
    with gzip.open(RAW, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline().lstrip("#").rstrip("\n").split("\t")
        col = {name: i for i, name in enumerate(header)}
        for line in f:
            row = line.rstrip("\n").split("\t")
            if row[col["Assembly"]] != "GRCh38" or row[col["OriginSimple"]] == "somatic":
                continue
            hgnc = row[col["HGNC_ID"]]
            if hgnc not in by_gene:
                continue
            vid = row[col["VariationID"]]
            if vid in seen[hgnc]:
                continue
            seen[hgnc].add(vid)
            m = NAME.match(row[col["Name"]])
            c, p = (m.group("c"), m.group("p")) if m else (None, None)
            hgvs = f"{m.group('tx')}:{c}" if m else row[col["Name"]][:80]
            names = row[col["PhenotypeList"]].split("|")
            matched, named = set(), ""
            for i, ids in enumerate(phenotype_ids(row[col["PhenotypeIDS"]])):
                hit = [cid for cid, keys, _ in by_gene[hgnc] if ids & keys]
                matched.update(hit)
                label = names[i] if i < len(names) else ""
                if not hit and not named and label and label.lower() not in ("not provided", "not specified", "see cases"):
                    named = label[:70]
            rs = row[col["RS# (dbSNP)"]]
            gene = genes.setdefault(hgnc, {"symbol": by_gene[hgnc][0][2], "conditions": [cid for cid, _, _ in by_gene[hgnc]], "rows": []})
            gene["rows"].append([int(vid), hgvs, p or "", classify(row[col["ClinicalSignificance"]]),
                                 STARS.get(row[col["ReviewStatus"]], 0), int(row[col["NumberSubmitters"]] or 0),
                                 kind(c, p, row[col["Type"]]), sorted(gene["conditions"].index(x) for x in matched),
                                 f"rs{rs}" if rs not in ("-", "-1", "") else "", row[col["LastEvaluated"]] if row[col["LastEvaluated"]] != "-" else "",
                                 named])

    files, summary = {}, {}
    for hgnc, g in genes.items():
        rows = sorted(g["rows"], key=lambda r: (CLASS_ORDER[r[3]], -r[5], -r[4], r[0]))
        per = {cid: {"plp": 0, "vus": 0, "conflicting": 0, "benign": 0, "types": Counter(), "top": []} for cid in g["conditions"]}
        unassigned = 0
        for r in rows:
            disease_causing = r[3] in ("P", "LP")
            if disease_causing and not r[7]:
                unassigned += 1
            for i in r[7]:
                s = per[g["conditions"][i]]
                if disease_causing:
                    s["plp"] += 1
                    s["types"][r[6]] += 1
                    if len(s["top"]) < 3:
                        s["top"].append([r[0], r[1], r[2], r[4], r[5]])
                elif r[3] == "VUS":
                    s["vus"] += 1
                elif r[3] == "C":
                    s["conflicting"] += 1
                elif r[3] in ("B", "LB"):
                    s["benign"] += 1
        for cid, s in per.items():
            summary[cid] = {**s, "types": dict(s["types"].most_common()), "gene_unassigned_plp": unassigned, "release": release}
        files[g["symbol"]] = {"gene": g["symbol"], "release": release, "conditions": g["conditions"],
                              "fields": ["id", "hgvs", "protein", "class", "stars", "submitters", "type", "conditions", "rs", "evaluated", "named"],
                              "total": len(rows), "variants": rows[:MAX_PER_GENE]}
    return files, summary


def upload(files: dict) -> int:
    sys.path.insert(0, str(ROOT))
    from atlas_mcp.cloud import configured_store
    container = configured_store().container
    manifest_path = OUT_DIR / ".uploaded.json"
    done = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    count = 0
    for symbol, body in files.items():
        raw = json.dumps(body, separators=(",", ":")).encode()
        digest = hashlib.sha256(raw).hexdigest()
        if done.get(symbol) == digest:
            continue
        container.upload_blob(f"variants/{symbol}.json", raw, overwrite=True)
        done[symbol] = digest
        count += 1
        if count % 200 == 0:
            manifest_path.write_text(json.dumps(done))
    manifest_path.write_text(json.dumps(done))
    return count


def main() -> None:
    started = time.time()
    release = download()
    files, summary = build(release)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for symbol, body in files.items():
        (OUT_DIR / f"{symbol}.json").write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")
    temp = SUMMARY.with_suffix(".tmp")
    temp.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
    temp.replace(SUMMARY)
    with_plp = sum(1 for s in summary.values() if s["plp"])
    print(f"ClinVar {release}: {len(files)} genes, {sum(f['total'] for f in files.values())} variants, "
          f"{with_plp}/{len(summary)} conditions with disease-causing variants named for them ({time.time() - started:.0f}s)")
    if "--upload" in sys.argv:
        print(f"uploaded {upload(files)} changed gene files")


if __name__ == "__main__":
    main()
