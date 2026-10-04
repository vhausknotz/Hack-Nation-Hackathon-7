"""Cloud MCP application adapter: published Blob reads and transactional Table intake."""
import json
import re
import tempfile
import time
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from ledger import sources
from ledger.canonical import sha256
from ledger.policy import claim_review_status, family_key
from .service import Atlas, bounded
from .source_fetch import official_url, fetch_official


class Projection:
    """A versioned public read model. The pointer changes only after upload finishes."""
    def __init__(self, container):
        self.container = container
        self.manifest = json.loads(container.download_blob("published/current.json").readall())
        self.prefix = self.manifest["prefix"]
        self.catalog = self.read("catalog.json")

    def read(self, name):
        try:
            return json.loads(self.container.download_blob(self.prefix+"/"+name).readall())
        except ResourceNotFoundError:
            raise ValueError("Record is not in this published MCP snapshot") from None


class CloudAtlas(Atlas):
    def __init__(self, intake, projection, actor):
        self.intake, self.projection, self.actor = intake, projection, actor
        self.conditions = projection.catalog
        self.intake.profile(actor)

    def condition(self, cid):
        if cid not in self.conditions:
            raise ValueError("Unknown condition; use search_atlas for a stable ID")
        result = self.projection.read("conditions/"+cid+".json")
        return {**result, "snapshot": self.projection.manifest,
                "notice": "Published MCP snapshot, refreshed by the operator worker. Queue acceptance is not review or website publication."}

    def claim(self, cid):
        if not re.fullmatch(r"claim:sha256:[0-9a-f]{64}", cid):
            raise ValueError("Invalid claim ID")
        return self.projection.read("claims/"+cid.split(":")[-1]+".json")

    def frontier(self, condition_id=None, limit=20):
        bounded(limit, 1, 50)
        if condition_id and condition_id not in self.conditions:
            raise ValueError("Unknown condition")
        selected = [self.conditions[condition_id]] if condition_id else sorted(
            self.conditions.values(), key=lambda c: (c["phenotype_count"], c["id"]))[:50]
        tasks = [{"id": "evidence:"+c["id"], "condition_id": c["id"], "kind": "evidence",
                  "title": "Find sourced evidence for "+c["name"],
                  "goal": "Find directly relevant sources. Explain population and qualifications; missing records are not proof of absence.",
                  "allowed_predicates": ["has_symptom", "has_name", "has_asset", "studied_by", "represented_by", "has_variant_effect"]} for c in selected]
        profile = self.writable()
        family = profile["model_family"]
        for item in self.projection.read("review-frontier.json"):
            if condition_id and item["condition_id"] != condition_id:
                continue
            if not profile["allow_review"] or item["contributor"] == self.actor or family_key(family) in {family_key(f) for f in item["reviewed_families"]}:
                continue
            tasks.append({"id": "review:"+item["claim_id"]+":"+family, "condition_id": item["condition_id"], "kind": "review",
                          "model_family": family, "claim_id": item["claim_id"], "title": "Check whether the source supports this claim"})
            if len(tasks) >= 100:
                break
        self.intake.seed(tasks)
        return {"tasks": self.intake.tasks(condition_id, limit), "notice": "Deterministic frontier from the published MCP snapshot."}

    def source(self, sid, offset=0, limit=12000):
        bounded(offset, 0, 2_000_000); bounded(limit, 1, 20000)
        if not re.fullmatch(r"src:sha256:[0-9a-f]{64}", sid):
            raise ValueError("Invalid source ID")
        src = self.intake.store.get("source", sid)
        if src:
            name = "sources/text/"+src["text_hash"].split(":")[1]
        else:
            src = self.projection.read("sources/"+sid.split(":")[-1]+".json")
            name = self.projection.prefix+"/text/"+sid.split(":")[-1]
        if not src["redistributable"]:
            return {"source": src, "notice": "Verification-only archive. Read its public URL; existing claim quotes remain available."}
        raw = self.intake.store.container.download_blob(name).readall()
        if sha256(raw) != src["text_hash"]:
            raise ValueError("Archived source hash differs")
        text = raw.decode("utf-8")
        return {"source": src, "text": text[offset:offset+limit], "offset": offset, "total_characters": len(text),
                "next_offset": offset+limit if offset+limit < len(text) else None, "untrusted_source_text": True}

    def fetch_source(self, tid, provider, record_id):
        self.writable()
        self.intake.owned_task(tid, self.actor)
        official_url(provider, record_id)
        cache_key = provider+":"+record_id
        cached = self.intake.store.get("sourcecache", cache_key)
        if cached:
            return {**cached, "cached": True, "next": "get_source"}
        time.sleep(self.intake.reserve_fetch(self.actor, tid))
        with tempfile.TemporaryDirectory(prefix="atlas-source-") as directory:
            root = Path(directory)
            src = fetch_official(provider, record_id, root)
            self.intake.record_source(src.to_dict(), sources.read_raw(src, root), sources.read_text(src, root), self.actor, tid, cache_key)
        return {"source_id": src.source_id, "cached": False, "next": "get_source", "notice": "Archived from provider; relevance and meaning are not yet checked."}

    def submission(self, sid):
        self.writable()
        item = self.intake.submission(sid, self.actor)
        cid = (item.get("result") or {}).get("claim_id")
        if cid:
            try:
                item["current_claim"] = self.claim(cid)
            except ValueError:
                item["notice"] = "Worker receipt is available; the published MCP read snapshot has not caught up yet."
        return item
