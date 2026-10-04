import json

import pytest

from ledger import identity, merkle, sources
from ledger.api import Ledger, now
from ledger.canonical import canonical_quote, canonical_text, find_quote
from ledger.schema import make_claim

ABSTRACT = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>33299146</PMID><Article>
<ArticleTitle>De novo variants in SNAP25 cause an early-onset developmental and epileptic encephalopathy.</ArticleTitle>
<Abstract><AbstractText Label="RESULTS">All   individuals had developmental delay
and 21 of 23 had seizures, frequently  with onset in the first year.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


class FakeRegistry:
    version = "registry:test"
    ids = {"MONDO:0014590", "MONDO:0012812", "HP:0001250", "HP:0001263", "HGNC:11132"}

    def exists(self, kind, entity):
        if kind in ("condition", "phenotype", "gene"):
            return entity.split("-")[0] in self.ids
        return None

    def dataset_hash(self, dataset):
        if dataset == "phenotype.hpoa":
            return "sha256:pinned"
        raise FileNotFoundError(dataset)


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.db", registry_=FakeRegistry(), keys_dir=tmp_path / "keys")


def agent(ledger, tmp_path, name, kind="agent"):
    return ledger.register(identity.load_or_create(name, tmp_path / "keys"), kind=kind, manifest={"model": "test"})


def seizure_claim(src, signer, quote="21 of 23 had seizures"):
    text = sources.read_text(src, root=src_root(src))
    start, end = find_quote(text, quote) or (0, len(quote))
    return make_claim("MONDO:0014590", "has_symptom", "HP:0001250",
                      [{"type": "publication_text", "source_id": src.source_id, "pmid": "PMID:33299146", "quote": quote, "start": start, "end": end}],
                      {"contributor": signer.contributor, "agent": "extractor", "model": "gpt-6-luna", "created": now()},
                      frequency="21/23", evidence_level="clinical")


_roots = {}


def src_root(src):
    return _roots.get(src.source_id)


@pytest.fixture(autouse=True)
def archive_root(tmp_path, monkeypatch):
    root = tmp_path / "sources"
    monkeypatch.setattr(sources, "ARCHIVE", root)
    # kernel reads archived files through sources.read_text/read_raw with their default root
    import ledger.kernel as kernel
    monkeypatch.setattr(kernel, "read_text", lambda s: sources.read_text(s, root=root))
    monkeypatch.setattr(kernel, "read_raw", lambda s: sources.read_raw(s, root=root))
    yield root


def make_source(ledger, signer, root):
    src = sources.archive(ABSTRACT, "https://pubmed.ncbi.nlm.nih.gov/33299146/", "pubmed_xml", "PubMed abstract", True, root=root)
    _roots[src.source_id] = root
    ledger.add_source(src, signer)
    return src


def test_canonical_text_and_quotes():
    text = canonical_text("A  line\r\nwith  spaces\n\n\n\nend")
    assert text == "A line\nwith spaces\n\nend"
    assert find_quote(text, "line with   spaces") is not None
    assert canonical_quote(" a\n b ") == "a b"


def test_valid_claim_passes_kernel_and_is_logged(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    result = ledger.propose(seizure_claim(src, extractor), extractor)
    assert result.accepted, result.checks
    types = [h["type"] for h in ledger.history(result.claim_id)]
    assert types == ["claim.proposed", "kernel.checked"]
    assert ledger.verify_log()["ok"]


def test_quote_that_is_not_in_the_source_is_rejected(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    claim = seizure_claim(src, extractor, quote="21 of 23 had seizures")
    claim["evidence"][0]["quote"] = "all 23 had seizures"  # invented
    result = ledger.propose(claim, extractor)
    assert not result.accepted
    assert any(c["name"] == "evidence" and not c["passed"] for c in result.checks)


def test_unknown_identifier_and_bad_schema_are_rejected(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    claim = seizure_claim(src, extractor)
    claim["assertion"]["object"] = "HP:9999999"
    assert not ledger.propose(claim, extractor).accepted
    claim = seizure_claim(src, extractor)
    claim["assertion"]["predicate"] = "cures"
    assert not ledger.propose(claim, extractor).accepted


def test_signature_from_unregistered_key_fails(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    impostor = identity.load_or_create("agent:extractor", tmp_path / "other-keys")  # same name, different key
    result = ledger.propose(seizure_claim(src, extractor), impostor)
    assert not result.accepted
    assert any(c["name"] == "signature" and not c["passed"] for c in result.checks)
    assert ledger.store.claim(result.claim_id) is None  # refused, not logged
    assert ledger.verify_log()["ok"]


def test_review_independence_counts_model_families_not_prompts(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    cid = ledger.propose(seizure_claim(src, extractor), extractor).claim_id
    v1, v2, v3 = (agent(ledger, tmp_path, f"agent:verifier-{i}") for i in range(3))
    ledger.review(cid, "supports", "quote states 21 of 23 had seizures", v1, model_family="openai-gpt6", model="gpt-6-sol")
    ledger.review(cid, "supports", "same model, other prompt", v2, model_family="openai-gpt6", model="gpt-6-sol")
    assert ledger.claim_status(cid) == "reviewed"
    ledger.review(cid, "supports", "second family agrees", v3, model_family="other-family", model="x")
    assert ledger.claim_status(cid) == "independently_reviewed"
    with pytest.raises(ValueError):
        ledger.review(cid, "supports", "self review", extractor, model_family="openai-gpt6")


def test_reviewed_counter_claim_makes_assertion_contested(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    result = ledger.propose(seizure_claim(src, extractor), extractor)
    skeptic = agent(ledger, tmp_path, "agent:skeptic")
    counter = ledger.propose(seizure_claim(src, skeptic, quote="All individuals had developmental delay"), skeptic)
    ledger.challenge(result.assertion_id, "illustrative counter-evidence", skeptic, counter_claim=counter.claim_id)
    assert ledger.assertion_state(result.assertion_id)["state"] != "contested"  # counter-claim not yet reviewed
    human = agent(ledger, tmp_path, "human:expert", kind="human")
    ledger.review(counter.claim_id, "supports", "checked", human)
    assert ledger.assertion_state(result.assertion_id)["state"] == "contested"


def test_redaction_removes_content_but_keeps_proofs(ledger, tmp_path, archive_root):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    result = ledger.propose(seizure_claim(src, extractor), extractor)
    head = ledger.publish_tree_head()
    proposed = [e for e in ledger.store.events_for(result.claim_id) if e["type"] == "claim.proposed"][0]
    ledger.redact(proposed["id"], "personal_data", agent(ledger, tmp_path, "human:moderator", kind="human"))
    assert ledger.store.event(proposed["id"])["payload"] is None
    assert ledger.store.claim(result.claim_id) is None
    proof = ledger.inclusion_proof(proposed["id"], size=head["size"])
    assert proof["root"] == head["root"]
    assert merkle.verify_inclusion(bytes.fromhex(proof["leaf"]), proof["index"], proof["size"], [bytes.fromhex(p) for p in proof["proof"]], bytes.fromhex(head["root"]))
    c = ledger.consistency_proof(head["size"])
    assert merkle.verify_consistency(c["old_size"], c["new_size"], [bytes.fromhex(p) for p in c["proof"]], bytes.fromhex(head["root"]), bytes.fromhex(c["new_root"]))
    assert ledger.verify_log()["ok"]


@pytest.mark.parametrize("kind", ["review", "challenge"])
def test_redacted_reason_leaves_projections_and_legacy_rows_are_hidden(ledger, tmp_path, archive_root, kind):
    extractor = agent(ledger, tmp_path, "agent:extractor")
    src = make_source(ledger, extractor, archive_root)
    cid = ledger.propose(seizure_claim(src, extractor), extractor).claim_id
    human = agent(ledger, tmp_path, "human:moderator", kind="human")
    reason = "Synthetic private detail that must disappear"
    if kind == "review":
        event_id = ledger.review(cid, "supports", reason, human)
        table, read, read_all = "reviews", ledger.store.reviews_for, ledger.store.all_reviews
        assert ledger.claim_status(cid) == "human_reviewed"
    else:
        event_id = ledger.challenge(cid, reason, human)
        table, read, read_all = "challenges", ledger.store.challenges_for, ledger.store.all_challenges
    projected = tuple(read(cid)[0])
    head = ledger.publish_tree_head()
    ledger.redact(event_id, "personal_data", human)
    assert ledger.store.db.execute(f"SELECT COUNT(*) FROM {table} WHERE event_id=?", (event_id,)).fetchone()[0] == 0
    assert not read(cid) and not read_all()
    assert reason not in json.dumps(ledger.history(cid))
    if kind == "review":
        assert ledger.claim_status(cid) == "unreviewed"
    proof = ledger.inclusion_proof(event_id, size=head["size"])
    assert merkle.verify_inclusion(bytes.fromhex(proof["leaf"]), proof["index"], proof["size"],
                                   [bytes.fromhex(p) for p in proof["proof"]], bytes.fromhex(head["root"]))
    assert ledger.verify_log()["ok"]

    # A ledger redacted by the old implementation can still have the duplicate
    # reason. Public read paths must suppress it without a destructive migration.
    placeholders = ",".join("?" for _ in projected)
    ledger.store.db.execute(f"INSERT INTO {table} VALUES ({placeholders})", projected)
    assert not read(cid) and not read_all()
    if kind == "review":
        assert ledger.claim_status(cid) == "unreviewed"


def test_reference_import_commits_to_all_claims(ledger, tmp_path):
    importer = agent(ledger, tmp_path, "importer:hpo", kind="importer")
    claims = [
        make_claim("MONDO:0012812", "has_symptom", "HP:0001250",
                   [{"type": "curated_database", "dataset": "phenotype.hpoa", "dataset_hash": "sha256:pinned", "record": "OMIM:612164|HP:0001250"}],
                   {"contributor": importer.contributor, "agent": "importer", "created": "2026-10-04"}),
        make_claim("MONDO:0012812", "has_symptom", "HP:0009999",  # unknown term: rejected
                   [{"type": "curated_database", "dataset": "phenotype.hpoa", "dataset_hash": "sha256:pinned", "record": "x"}],
                   {"contributor": importer.contributor, "agent": "importer", "created": "2026-10-04"}),
    ]
    result = ledger.record_import("phenotype.hpoa", "hpo-importer@1", claims, importer)
    assert result["claims"] == 1 and result["rejected"] == 1
    rows = ledger.store.claims_where("origin = 'reference'")
    assert len(rows) == 1 and json.loads(rows[0]["body"])["assertion"]["object"] == "HP:0001250"
    assert ledger.assertion_state(rows[0]["assertion_id"])["state"] == "curated"
