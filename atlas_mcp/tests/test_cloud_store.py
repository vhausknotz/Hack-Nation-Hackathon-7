"""Real Azure Storage SDK integration against local Azurite; no Azure bill.

Run with ATLAS_TEST_AZURITE=1 after starting azurite on loopback default ports.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from atlas_mcp.tests.test_contribution_loop import setup, TestRegistry, CID

pytestmark = pytest.mark.skipif(os.getenv("ATLAS_TEST_AZURITE") != "1", reason="Local Azurite integration is opt-in")


@pytest.fixture
def cloud():
    from azure.data.tables import TableClient
    from azure.storage.blob import ContainerClient
    from atlas_mcp.cloud_store import CloudIntake, CloudStore
    name = "atlastest" + uuid.uuid4().hex
    table = TableClient.from_connection_string("UseDevelopmentStorage=true", name)
    container = ContainerClient.from_connection_string("UseDevelopmentStorage=true", name)
    store = CloudStore(table, container)
    store.initialize()
    try:
        yield CloudIntake(store)
    finally:
        table.delete_table()
        container.delete_container()


def evidence_task(n):
    return {"id": "evidence:" + str(n), "condition_id": "MONDO:0014590", "kind": "evidence"}


def test_concurrent_leases_cannot_have_two_owners(cloud):
    a = cloud.enroll("alice", "test", "family-a", "issuer|alice")["id"]
    b = cloud.enroll("bravo", "test", "family-b", "issuer|bravo")["id"]
    cloud.seed([evidence_task(1)])
    def claim(actor):
        try:
            return cloud.claim("evidence:1", actor)["actor"]
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        winners = [v for v in pool.map(claim, [a, b]) if v]
    assert len(winners) == 1
    assert cloud.task("evidence:1")["actor"] == winners[0]


def test_global_tool_allowance_is_atomic_across_callers(cloud):
    actors = [cloud.enroll(name, "test", "family", "issuer|"+name)["id"] for name in ("alice", "bravo")]
    def call(actor):
        try:
            cloud.admit_call(actor, daily_limit=3, actor_limit=3)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(4) as pool:
        assert sum(pool.map(call, actors*2)) == 3


def test_atomic_quota_duplicate_delivery_and_durable_restart(cloud):
    from atlas_mcp.cloud_store import CloudIntake
    actor = cloud.enroll("alice", "test", "family-a", "issuer|alice", quota=1)["id"]
    cloud.seed([evidence_task(1)])
    cloud.claim("evidence:1", actor)
    def submit(n):
        try:
            return cloud.enqueue(actor, "evidence:1", "claim", {"n": n})
        except ValueError:
            return None
    with ThreadPoolExecutor(4) as pool:
        accepted = [v for v in pool.map(submit, range(4)) if v]
    assert len(accepted) == 1
    # Fresh object, with no local files or memory from the first gateway instance.
    restarted = CloudIntake(cloud.store)
    pending = restarted.pending()
    assert len(pending) == 1
    import json
    body = json.loads(cloud.store.container.download_blob(pending[0]["blob"]).readall())
    from ledger.canonical import canonical_json
    from ledger.identity import verify
    assert verify(cloud.profile(actor)["public_key"], canonical_json(body["envelope"]), body["signature"])
    assert restarted.enqueue(actor, "evidence:1", "claim", body["envelope"]["payload"])["duplicate"]
    result = {"state": "kernel_rejected", "published": False}
    restarted.acknowledge(pending[0]["id"], result)
    restarted.acknowledge(pending[0]["id"], result)
    assert restarted.submission(pending[0]["id"], actor)["result"] == result
    assert not restarted.pending()
    with pytest.raises(ValueError, match="conflicts"):
        restarted.acknowledge(pending[0]["id"], {"state": "kernel_accepted"})


def test_three_task_limit_principal_isolation_and_immutable_blobs(cloud):
    actor = cloud.enroll("alice", "test", "family-a", "issuer|alice")["id"]
    other = cloud.enroll("bravo", "test", "family-b", "issuer|bravo")["id"]
    assert cloud.principal_actor("issuer|alice") == actor
    with pytest.raises(ValueError):
        cloud.principal_actor("different-issuer|alice")
    cloud.seed([evidence_task(n) for n in range(4)])
    for n in range(3):
        cloud.claim(f"evidence:{n}", actor)
    with pytest.raises(ValueError, match="three"):
        cloud.claim("evidence:3", actor)
    sid = cloud.enqueue(actor, "evidence:1", "claim", {"n": 1})["submission_id"]
    with pytest.raises(ValueError):
        cloud.submission(sid, other)
    with pytest.raises(ValueError):
        cloud.enqueue(other, "evidence:1", "claim", {"n": 2})
    cloud.store.immutable("test/blob", b"original")
    with pytest.raises(ValueError, match="differs"):
        cloud.store.immutable("test/blob", b"replacement")


def test_cloud_source_to_kernel_ack_retry_and_published_read_model(cloud, setup, monkeypatch, tmp_path):
    from atlas_mcp.cloud_service import CloudAtlas, Projection
    from atlas_mcp.cloud_publish import publish
    from atlas_mcp.cloud_worker import pull_and_drain
    from ledger import sources
    from ledger.store import Store
    import json
    local_atlas, _, assertion, evidence = setup
    manifest = publish(cloud.store, local_atlas.ledger_path, local_atlas.data_root)
    actor = cloud.enroll("cloud-extractor", "test", "family-a", "issuer|extractor")["id"]
    atlas = CloudAtlas(cloud, Projection(cloud.store.container), actor)
    assert atlas.search("SNAP25")["matches"][0]["id"] == CID
    tid = atlas.frontier(CID)["tasks"][0]["id"]
    atlas.claim_task(tid)
    with local_atlas.intake.connect() as db:
        src = json.loads(db.execute("SELECT body FROM sources").fetchone()[0])
    cloud.record_source(src, sources.read_raw(src, local_atlas.intake.root/"sources"),
                        sources.read_text(src, local_atlas.intake.root/"sources"), actor, tid, "fixture:1")
    assert evidence[0]["quote"] in atlas.source(src["source_id"])["text"]
    queued = atlas.submit_claim(tid, assertion, evidence, "test-cloud@1")
    worker_state = tmp_path/"cloud-bridge"
    ack = cloud.acknowledge
    monkeypatch.setattr(cloud, "acknowledge", lambda *_: (_ for _ in ()).throw(RuntimeError("lost cloud acknowledgement")))
    with pytest.raises(RuntimeError, match="lost cloud"):
        pull_and_drain(cloud, worker_state, local_atlas.ledger_path, TestRegistry())
    store = Store(local_atlas.ledger_path, readonly=True)
    size = store.size()
    store.close()
    monkeypatch.setattr(cloud, "acknowledge", ack)
    receipt = pull_and_drain(cloud, worker_state, local_atlas.ledger_path, TestRegistry())
    assert receipt["log_verified"] and receipt["model_calls"] == 0 and not receipt["website_published"]
    store = Store(local_atlas.ledger_path, readonly=True)
    assert store.size() == size
    store.close()
    result = atlas.submission(queued["submission_id"])
    assert result["state"] == "kernel_accepted"
    assert "has not caught up" in result["notice"]
    publish(cloud.store, local_atlas.ledger_path, local_atlas.data_root)
    fresh = CloudAtlas(cloud, Projection(cloud.store.container), actor)
    assert fresh.submission(queued["submission_id"])["current_claim"]["review_status"] == "unreviewed"
    assert fresh.condition(CID)["recent_contributions"][0]["claim_id"] == result["result"]["claim_id"]
    # A second computer with a fresh ledger cannot silently become the sequencer.
    with pytest.raises(ValueError, match="another local worker"):
        pull_and_drain(cloud, tmp_path/"different-worker", local_atlas.ledger_path, TestRegistry())
