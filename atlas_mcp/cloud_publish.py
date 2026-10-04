"""Operator-only publication of read projections; never uploads ledger signing keys."""
import json
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ledger import sources
from ledger.policy import claim_review_status
from ledger.store import Store
from .challenge_view import challenge_view


def publish(cloud, ledger_path, data_root):
    prefix = "published/"+uuid.uuid4().hex
    conditions = {c["id"]: c for c in map(json.loads, (Path(data_root)/"conditions.jsonl").read_text(encoding="utf-8").splitlines())}
    objects, recent, frontier = {}, defaultdict(list), []
    with_store = Store(Path(ledger_path), readonly=True)
    try:
        store = with_store
        head = store.db.execute("SELECT size,root,ts,signature FROM tree_heads ORDER BY size DESC LIMIT 1").fetchone()
        for row in store.claims_where("origin='contributed'"):
            cid = row["claim_id"]
            claim = json.loads(row["body"])
            reviews = [dict(v) for v in store.reviews_for(cid)]
            status = claim_review_status(reviews)
            history = [{"seq": r["seq"], "type": r["type"], "actor": r["actor"], "at": r["ts"], "redacted": bool(r["redacted"])} for r in store.events_for(cid)]
            objects["claims/"+cid.split(":")[-1]+".json"] = {"claim_id": cid, "claim": claim, "origin": row["origin"],
                "kernel_accepted": bool(row["kernel_ok"]), "review_status": status, "reviews": reviews, "history": history,
                **challenge_view(store, row)}
            recent[row["subject"]].append({"claim_id": cid, "predicate": row["predicate"], "kernel_ok": row["kernel_ok"], "review_status": status, "seq": row["created_seq"]})
            if row["kernel_ok"] and row["subject"] in conditions and status not in {"independently_reviewed", "human_reviewed", "rejected"}:
                frontier.append({"claim_id": cid, "condition_id": row["subject"], "contributor": row["contributor"],
                                 "reviewed_families": sorted({v["model_family"] for v in reviews if v["model_family"]})})
            for evidence in claim.get("evidence", []):
                sid = evidence.get("source_id")
                if not sid or not sid.startswith("src:sha256:"):
                    continue
                name = "sources/"+sid.split(":")[-1]+".json"
                if name in objects:
                    continue
                src = store.source(sid)
                if not src:
                    continue
                objects[name] = src
                if src["redistributable"]:
                    text = sources.read_text(src, root=Path(ledger_path).parent/"sources")
                    if text is not None:
                        objects["text/"+sid.split(":")[-1]] = text.encode()
        for cid, c in conditions.items():
            objects["conditions/"+cid+".json"] = {"condition": c, "recent_contributions": sorted(recent[cid], key=lambda r: r["seq"], reverse=True)[:40]}
        objects["catalog.json"] = {cid: {k: c[k] for k in ("id", "name", "gene", "also_known_as") if k in c} | {
            "phenotype_count": len(c.get("phenotypes", []))} for cid, c in conditions.items()}
        objects["review-frontier.json"] = frontier
        terms = Path(data_root)/"hpo_terms.json"
        if terms.exists():
            objects["terms/hpo.json"] = json.loads(terms.read_text(encoding="utf-8"))
        manifest = {"prefix": prefix, "published_at": datetime.now(timezone.utc).isoformat(), "ledger_tree_head": dict(head) if head else None,
                    "conditions": len(conditions), "records": len(objects), "claim_coverage": "Contributed claims; bulk reference evidence remains in the local ledger.",
                    "website_updated": False}
    finally:
        with_store.close()
    def upload(item):
        name, body = item
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        cloud.immutable(prefix+"/"+name, raw)
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(upload, objects.items()))
    # One atomic blob replacement after all records exist. Readers keep their old
    # complete version throughout this upload and never observe a partial build.
    cloud.container.upload_blob("published/current.json", json.dumps(manifest).encode(), overwrite=True)
    return manifest
