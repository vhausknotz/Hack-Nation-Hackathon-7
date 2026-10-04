"""Cloud MCP application adapter: published Blob reads and transactional Table intake."""
import hashlib
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
        try:
            return self.projection.read("claims/"+cid.split(":")[-1]+".json")
        except ValueError:
            # Fresh claims are readable for peer review before the next full snapshot.
            live = self.live_blob("live/claims/"+cid.split(":")[-1]+".json")
            if live is None:
                raise
            return live

    def live_blob(self, name):
        try:
            return json.loads(self.intake.store.container.download_blob(name).readall())
        except ResourceNotFoundError:
            return None

    def person(self, actor):
        """The human behind an agent (GitHub account or operator principal); reviews must cross people."""
        profile = self.intake.store.get("profile", actor) or {}
        principal = profile.get("principal", actor)
        return "|".join(principal.split("|")[:2]) if principal.startswith("github|") else principal

    def claim_task(self, tid):
        task = self.intake.task(tid)
        if task and task["kind"] == "review":
            spec = json.loads(task["body"])
            claim = self.claim(spec["claim_id"])
            if self.person(claim["claim"]["provenance"]["contributor"]) == self.person(self.actor):
                raise ValueError("Reviews must come from a different person than the contributor")
        return super().claim_task(tid)

    def submit_review(self, tid, cid, verdict, reason, prompt):
        claim = self.claim(cid)
        if self.person(claim["claim"]["provenance"]["contributor"]) == self.person(self.actor):
            raise ValueError("Reviews must come from a different person than the contributor")
        return super().submit_review(tid, cid, verdict, reason, prompt)

    # ---- reviewer calibration ----------------------------------------------------------------------
    CAL_ROUND, CAL_PASS = 5, 4

    def calibration_set(self):
        cases = self.live_blob("live/calibration.json")
        if not cases:
            raise ValueError("Calibration is not available yet; try again later")
        return {c["id"]: c for c in cases}

    def current_round(self, state):
        done = {cid for r in state["rounds"] for cid in r["cases"]}
        return [cid for cid in state["answers"] if cid not in done]

    def calibration_case(self):
        profile = self.writable()
        if profile.get("allow_review"):
            return {"qualified": True, "notice": "You are already a reviewer. Use list_frontier to find review tasks."}
        cases = self.calibration_set()
        state = self.intake.store.get("calibration", self.actor) or {"rounds": [], "answers": {}}
        if len(state["rounds"]) >= 2 and not any(r["passed"] for r in state["rounds"]):
            raise ValueError("Calibration attempts used up; ask the operator")
        pending = state.get("pending")
        if not pending or pending not in cases:
            order = sorted(cases, key=lambda c: hashlib.sha256((self.actor + c).encode()).hexdigest())
            pending = next((cid for cid in order if cid not in state["answers"]), None)
            if not pending:
                raise ValueError("No calibration cases left")
            state["pending"] = pending
            self.intake.store.table.upsert_entity(self.intake.store.entity("calibration", self.actor, state))
        case = cases[pending]
        return {"case_id": pending, "case_number": len(self.current_round(state)) + 1, "of": self.CAL_ROUND,
                "condition": case["condition"], "claim": case["claim"], "qualifiers": case["qualifiers"],
                "quote": case["quote"], "source_context": case["source_context"],
                "task": "Judge ONLY whether the quote (and its context) supports the claim exactly as stated for patients with this "
                        "condition. Answer with submit_calibration: supports | supports_with_qualification | does_not_support | "
                        "out_of_scope, plus a one-sentence reason."}

    def submit_calibration(self, case_id, verdict, reason):
        self.writable()
        from ledger.schema import REVIEW_VERDICTS
        if verdict not in REVIEW_VERDICTS or not 10 <= len(reason or "") <= 2000:
            raise ValueError("Use a supported verdict and a reason of 10-2000 characters")
        cases = self.calibration_set()
        state = self.intake.store.get("calibration", self.actor) or {"rounds": [], "answers": {}}
        if state.get("pending") != case_id or case_id not in cases:
            raise ValueError("Answer the case returned by get_calibration_case")
        bucket = "support" if verdict.startswith("supports") else "reject"
        state["answers"][case_id] = bucket == cases[case_id]["answer"]
        state.pop("pending", None)
        current = self.current_round(state)
        result = {"recorded": True, "answered": len(current), "of": self.CAL_ROUND}
        if len(current) >= self.CAL_ROUND:
            score = sum(state["answers"][c] for c in current)
            passed = score >= self.CAL_PASS
            state["rounds"].append({"cases": current, "score": score, "passed": passed, "at": time.time()})
            result.update(score=score, passed=passed)
            if passed:
                def grant(seq):
                    profile = self.intake.store.get("profile", self.actor)
                    profile.update(allow_review=True, qualified_at=time.time(), calibration_score=f"{score}/{self.CAL_ROUND}")
                    return None, [("profile", self.actor, profile),
                                  self.intake.event(seq, self.actor, {"id": None, "condition_id": None}, "reviewer_qualified", None,
                                                    {"score": f"{score}/{self.CAL_ROUND}"})]
                self.intake.store.atomic(grant)
                result["notice"] = "Qualified as a reviewer. list_frontier now includes review tasks for findings by other people."
            else:
                result["notice"] = "Not qualified this round. One more round with new cases is allowed." if len(state["rounds"]) < 2 else "Not qualified."
        self.intake.store.table.upsert_entity(self.intake.store.entity("calibration", self.actor, state))
        return result

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
        live = self.live_blob("live/review-frontier.json")
        me = self.person(self.actor)
        for item in (live if live is not None else self.projection.read("review-frontier.json")):
            if condition_id and item["condition_id"] != condition_id:
                continue
            if not profile["allow_review"] or item["contributor"] == self.actor or family_key(family) in {family_key(f) for f in item["reviewed_families"]}:
                continue
            if self.actor in item.get("reviewers", []) or self.person(item["contributor"]) == me:
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

    def term_index(self):
        if getattr(self.projection, "terms", None) is None:
            try:
                self.projection.terms = self.projection.read("terms/hpo.json")
            except ValueError:
                self.projection.terms = {}
        return self.projection.terms

    def source_text(self, sid):
        if not re.fullmatch(r"src:sha256:[0-9a-f]{64}", sid):
            raise ValueError("Invalid source ID")
        src = self.intake.store.get("source", sid)
        if src:
            name = "sources/text/"+src["text_hash"].split(":")[1]
        else:
            src = self.projection.read("sources/"+sid.split(":")[-1]+".json")
            name = self.projection.prefix+"/text/"+sid.split(":")[-1]
        try:
            raw = self.intake.store.container.download_blob(name).readall()
        except ResourceNotFoundError:
            raise ValueError(f"Archived text for {sid} is not available; fetch the source first") from None
        if sha256(raw) != src["text_hash"]:
            raise ValueError("Archived source hash differs")
        return raw.decode("utf-8")

    def fetch_source(self, tid, provider, record_id):
        self.writable()
        self.intake.owned_task(tid, self.actor)
        official_url(provider, record_id)
        # Renderer version prevents an older partial eligibility archive from
        # satisfying a new complete-record request. Old source IDs stay valid.
        cache_key = provider+("@eligibility-2" if provider == "clinicaltrials" else "")+":"+record_id
        cached = self.intake.store.get("sourcecache", cache_key)
        if cached:
            return {**cached, "cached": True, "next": "get_source"}
        time.sleep(self.intake.reserve_fetch(self.actor, tid))
        with tempfile.TemporaryDirectory(prefix="atlas-source-") as directory:
            root = Path(directory)
            src = fetch_official(provider, record_id, root)
            self.intake.record_source(src.to_dict(), sources.read_raw(src, root), sources.read_text(src, root), self.actor, tid, cache_key)
        return {"source_id": src.source_id, "cached": False, "next": "get_source", "notice": "Archived from provider; relevance and meaning are not yet checked."}

    def fetch_page(self, tid, url):
        """Archive a public organization page (patient group, foundation, registry) for represented_by claims."""
        from .page_fetch import fetch_public_page, org_id, public_url
        self.writable()
        self.intake.owned_task(tid, self.actor)
        public_url(url if "://" in url else "https://" + url)
        time.sleep(self.intake.reserve_fetch(self.actor, tid))
        raw, read_from, mode, content_date = fetch_public_page(url)
        with tempfile.TemporaryDirectory(prefix="atlas-page-") as directory:
            root = Path(directory)
            src = sources.archive(raw, read_from, "html", "organization website, quoted for citation", False, root=root)
            text = sources.read_text(src, root)
            self.intake.record_source(src.to_dict(), sources.read_raw(src, root), text, self.actor, tid, "page:" + read_from)
        return page_result(src, text, read_from, mode, content_date, org_id(url))

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


def page_result(src, text, read_from, mode, content_date, organization_id):
    return {"source_id": src.source_id, "read_from": read_from, "mode": mode, "content_date": content_date,
            "suggested_organization_id": organization_id, "text": text[:20000], "total_characters": len(text),
            "untrusted_source_text": True,
            "notice": ("Archived. Quote a sentence that names this condition or its gene and shows whom the organization serves; "
                       "submit represented_by with object = the organization ID and qualifiers org_type, scope, name, homepage. "
                       + ("This is a historical Internet Archive copy: it shows what the site said then, not that the group is active now."
                          if mode == "archived_snapshot" else ""))}
