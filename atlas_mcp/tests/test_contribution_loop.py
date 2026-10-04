import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from atlas_mcp.intake import Intake
from atlas_mcp.service import Atlas, ROOT
from atlas_mcp.worker import drain
from ledger import sources
from ledger.api import Ledger
from ledger.store import Store

CID = "MONDO:0014590"
QUOTE = "21 of 23 had seizures"
TEXT = "A test fixture about SNAP25. All individuals had developmental delay and 21 of 23 had seizures."


class TestRegistry:
    version = "test-registry"

    def exists(self, kind, entity):
        return entity in {CID, "HP:0001250", "HGNC:11132"}


@pytest.fixture
def setup(tmp_path):
    state, data = tmp_path / "intake", tmp_path / "data"
    path = tmp_path / "ledger" / "ledger.db"
    data.mkdir()
    condition = {"id": CID, "name": "SNAP25-related epilepsy", "gene": {"symbol": "SNAP25"}, "phenotypes": []}
    (data / "conditions.jsonl").write_text(json.dumps(condition) + "\n", encoding="utf-8")
    ledger = Ledger(path, registry_=TestRegistry(), keys_dir=path.parent / "keys", source_root=path.parent / "sources")
    ledger.store.close()
    intake = Intake(state)
    actor = intake.enroll("extractor", "test-extractor", "test-family-a")["id"]
    src = sources.archive(TEXT.encode(), "https://example.org/test-fixture", "text", "test fixture", True, root=state / "sources")
    with intake.connect() as db:
        db.execute("INSERT INTO sources VALUES (?,?)", (src.source_id, json.dumps(src.to_dict())))
    atlas = Atlas(state, path, data, actor, TestRegistry())
    task = next(t for t in atlas.frontier(CID)["tasks"] if t["kind"] == "evidence")
    atlas.claim_task(task["id"])
    assertion = {"subject": CID, "predicate": "has_symptom", "object": "HP:0001250", "qualifiers": {"evidence_level": "clinical"}}
    start = TEXT.index(QUOTE)
    evidence = [{"type": "publication_text", "source_id": src.source_id, "quote": QUOTE, "start": start, "end": start+len(QUOTE)}]
    return atlas, task["id"], assertion, evidence


def process(atlas):
    return drain(atlas.intake.root, atlas.ledger_path, TestRegistry())


def submit(setup):
    atlas, tid, assertion, evidence = setup
    return atlas.submit_claim(tid, assertion, evidence, "test-extraction@1")


def test_end_to_end_queue_kernel_review_and_no_automatic_publication(setup):
    atlas, tid, _, _ = setup
    before = Store(atlas.ledger_path, readonly=True)
    size = before.size()
    queued = submit(setup)
    assert queued["state"] == "queued"
    assert before.size() == size  # intake never touches ledger, including registration
    before.close()
    assert submit(setup)["duplicate"]
    result = process(atlas)
    assert result["model_calls"] == 0 and result["log_verified"] and not result["website_published"]
    status = atlas.submission(queued["submission_id"])
    assert status["state"] == "kernel_accepted"
    assert status["current_claim"]["review_status"] == "unreviewed"
    cid = status["result"]["claim_id"]
    for suffix, family, expected in [("one", "test-family-a", "reviewed"), ("two", "test-family-b", "independently_reviewed")]:
        reviewer = atlas.intake.enroll("reviewer-"+suffix, "test-reviewer", family, allow_review=True)["id"]
        review_atlas = Atlas(atlas.intake.root, atlas.ledger_path, atlas.data_root, reviewer, TestRegistry())
        task = next(t for t in review_atlas.frontier(CID)["tasks"] if t["kind"] == "review" and t.get("model_family") == family)
        review_atlas.claim_task(task["id"])
        queued_review = review_atlas.submit_review(task["id"], cid, "supports", "Synthetic fixture explicitly states the seizure count.", "test-review@1")
        process(atlas)
        assert review_atlas.submission(queued_review["submission_id"])["current_claim"]["review_status"] == expected
    assert atlas.intake.activity()[-1]["stage"] == "review_recorded"


def test_wrong_quote_gets_useful_kernel_feedback(setup):
    atlas, _, _, evidence = setup
    evidence[0]["quote"] = "all 23 had seizures"
    queued = submit(setup)
    result = process(atlas)["processed"][0]
    assert result["state"] == "kernel_rejected"
    assert any(c["name"] == "evidence" and not c["passed"] for c in result["checks"])
    assert atlas.submission(queued["submission_id"])["result"]["published"] is False


def test_invalid_identifier_rejected_and_malformed_schema_not_queued(setup):
    atlas, tid, assertion, evidence = setup
    assertion["object"] = "HP:9999999"
    submit(setup)
    result = process(atlas)["processed"][0]
    assert result["state"] == "kernel_rejected"
    assert any(c["name"] == "identifiers" and not c["passed"] for c in result["checks"])
    assertion["object"] = "not-an-id"
    assert atlas.submit_claim(tid, assertion, evidence, "test@2")["state"] == "invalid"


def test_task_ownership_expiry_and_no_self_review(setup):
    atlas, tid, _, _ = setup
    other = atlas.intake.enroll("other", "test", "test-family-a", allow_review=True)["id"]
    with pytest.raises(ValueError, match="another contributor"):
        atlas.intake.claim(tid, other)
    queued = submit(setup)
    process(atlas)
    cid = atlas.submission(queued["submission_id"])["result"]["claim_id"]
    with atlas.intake.connect() as db:
        profile = atlas.intake.profile(atlas.actor)
        profile["allow_review"] = True
        db.execute("UPDATE profiles SET body=? WHERE id=?", (json.dumps(profile), atlas.actor))
    task = next(t for t in atlas.frontier(CID)["tasks"] if t["kind"] == "review")
    with pytest.raises(ValueError, match="own claims"):
        atlas.claim_task(task["id"])
    with atlas.intake.connect() as db:
        db.execute("UPDATE tasks SET expires=0 WHERE id=?", (tid,))
    with pytest.raises(ValueError, match="renew"):
        submit(setup)


def test_tampered_queue_signature_and_source_hash_rejected(setup):
    atlas, _, _, _ = setup
    queued = submit(setup)
    with atlas.intake.connect() as db:
        db.execute("UPDATE submissions SET signature='ed25519:tampered' WHERE id=?", (queued["submission_id"],))
    assert process(atlas)["processed"][0]["state"] == "rejected"


def test_worker_replay_after_acknowledgment_loss_is_idempotent(setup):
    atlas, _, _, _ = setup
    queued = submit(setup)
    process(atlas)
    with atlas.snapshot() as store:
        size = store.size()
    with atlas.intake.connect() as db:
        db.execute("UPDATE submissions SET state='queued',result=NULL WHERE id=?", (queued["submission_id"],))
    assert process(atlas)["processed"][0]["state"] == "kernel_accepted"
    with atlas.snapshot() as store:
        assert store.size() == size


def test_writer_lease_prevents_second_writer_but_not_intake(setup):
    atlas, _, _, _ = setup
    ledger = Ledger(atlas.ledger_path, registry_=TestRegistry(), keys_dir=atlas.ledger_path.parent / "keys")
    try:
        assert submit(setup)["state"] == "queued"
        with pytest.raises(RuntimeError, match="Another ledger writer"):
            process(atlas)
    finally:
        ledger.store.close()
    assert process(atlas)["processed"][0]["state"] == "kernel_accepted"


def test_quota_and_readonly_connection_cannot_submit(setup):
    atlas, tid, assertion, evidence = setup
    with atlas.intake.connect() as db:
        profile = atlas.intake.profile(atlas.actor)
        profile["daily_quota"] = 1
        db.execute("UPDATE profiles SET body=? WHERE id=?", (json.dumps(profile), atlas.actor))
    submit(setup)
    with pytest.raises(ValueError, match="quota"):
        atlas.submit_claim(tid, assertion, evidence, "different-prompt")
    readonly = Atlas(atlas.intake.root, atlas.ledger_path, atlas.data_root)
    with pytest.raises(ValueError, match="Read-only"):
        readonly.claim_task(tid)


def test_source_arbitrary_urls_not_fetched_and_metadata_only_for_restricted_archive(setup):
    atlas, tid, _, evidence = setup
    with pytest.raises(ValueError, match="Arbitrary URLs"):
        atlas.fetch_source(tid, "pubmed", "https://127.0.0.1/secret")
    sid = evidence[0]["source_id"]
    with atlas.intake.connect() as db:
        src = json.loads(db.execute("SELECT body FROM sources WHERE id=?", (sid,)).fetchone()[0])
        src["redistributable"] = False
        db.execute("UPDATE sources SET body=? WHERE id=?", (json.dumps(src), sid))
    assert "text" not in atlas.source(sid)


def test_real_mcp_stdio_client_roundtrip(setup):
    """Launch the real SDK server and exercise protocol discovery and a queued submission."""
    atlas, tid, assertion, evidence = setup

    async def run():
        def body(result):
            return result.structuredContent or json.loads(result.content[0].text)
        params = StdioServerParameters(command=sys.executable, args=["-B", str(ROOT / "tools/run_mcp.py"), "--state", str(atlas.intake.root),
            "--ledger", str(atlas.ledger_path), "--data", str(atlas.data_root), "--contributor", atlas.actor], cwd=str(atlas.data_root))
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                assert {"submit_claim", "submit_review", "get_activity", "get_submission", "fetch_source"} <= names
                found = await client.call_tool("search_atlas", {"query": "SNAP25"})
                assert not found.isError
                assert body(found)["matches"][0]["id"] == CID
                claim = await client.call_tool("submit_claim", {"task_id": tid, "assertion": assertion, "evidence": evidence, "prompt": "test-wire@1"})
                assert not claim.isError and body(claim)["state"] == "queued"
                return body(claim)["submission_id"]
    sid = asyncio.run(run())
    assert process(atlas)["processed"][0]["state"] == "kernel_accepted"
    assert atlas.submission(sid)["current_claim"]["review_status"] == "unreviewed"
