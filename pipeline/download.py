"""Download the open source files the atlas is built from into data/raw/.

Idempotent: files that already exist are skipped unless --force is given.
Usage: python pipeline/download.py [--force] [name ...]
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

HPO = "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download"
ORPHA = "https://www.orphadata.com/data/xml"

# name -> (url, description, license)
SOURCES = {
    "hp.json": (f"{HPO}/hp.json", "Human Phenotype Ontology (symptom terms + hierarchy)", "HPO license (free, attribution)"),
    "phenotype.hpoa": (f"{HPO}/phenotype.hpoa", "HPO disease -> phenotype annotations (OMIM/ORPHA/DECIPHER)", "HPO license (free, attribution)"),
    "genes_to_phenotype.txt": (f"{HPO}/genes_to_phenotype.txt", "HPO gene -> phenotype (via disease)", "HPO license (free, attribution)"),
    "genes_to_disease.txt": (f"{HPO}/genes_to_disease.txt", "HPO gene -> disease associations", "HPO license (free, attribution)"),
    "mondo.obo": ("https://purl.obolibrary.org/obo/mondo.obo", "MONDO disease ontology (IDs, synonyms, xrefs)", "CC BY 4.0"),
    "orphanet_genes.xml": (f"{ORPHA}/en_product6.xml", "Orphanet genes associated with rare diseases (incl. LoF/GoF type)", "CC BY 4.0"),
    "orphanet_nomenclature.xml": (f"{ORPHA}/en_product1.xml", "Orphanet disease nomenclature, synonyms, xrefs", "CC BY 4.0"),
    "orphanet_phenotypes.xml": (f"{ORPHA}/en_product4.xml", "Orphanet disease -> HPO phenotypes with frequency", "CC BY 4.0"),
    "orphanet_prevalence.xml": (f"{ORPHA}/en_product9_prev.xml", "Orphanet epidemiology / prevalence", "CC BY 4.0"),
    "hgnc_complete_set.txt": ("https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt", "HGNC gene symbols, previous symbols, aliases", "CC0"),
}


def download(name: str, force: bool = False) -> dict:
    url, desc, license_ = SOURCES[name]
    dest = RAW / name
    if dest.exists() and not force:
        print(f"skip  {name} (exists, {dest.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"get   {name} <- {url}")
        t0 = time.time()
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
        print(f"done  {name} ({dest.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s)")
    return {
        "file": name,
        "url": url,
        "description": desc,
        "license": license_,
        "bytes": dest.stat().st_size,
        "retrieved": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).isoformat(),
    }


def main(argv: list[str]) -> None:
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("--")] or list(SOURCES)
    RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data" / "sources_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for name in names:
        manifest[name] = download(name, force)
    manifest_path.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
