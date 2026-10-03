import pytest

from ledger import merkle


def leaves(n):
    return [merkle.leaf_hash(f"event-{i}".encode()) for i in range(n)]


@pytest.mark.parametrize("n", range(1, 34))
def test_inclusion_proofs_verify_for_every_leaf(n):
    ls = leaves(n)
    root = merkle.root(ls)
    for i in range(n):
        proof = merkle.inclusion_proof(i, ls)
        assert merkle.verify_inclusion(ls[i], i, n, proof, root)


def test_inclusion_proof_rejects_wrong_leaf_or_root():
    ls = leaves(11)
    root = merkle.root(ls)
    proof = merkle.inclusion_proof(4, ls)
    assert not merkle.verify_inclusion(ls[5], 4, 11, proof, root)
    assert not merkle.verify_inclusion(ls[4], 4, 11, proof, merkle.root(ls[:10]))


@pytest.mark.parametrize("new", range(1, 26))
def test_consistency_proofs_verify_for_every_prefix(new):
    ls = leaves(new)
    for old in range(1, new + 1):
        proof = merkle.consistency_proof(old, ls)
        assert merkle.verify_consistency(old, new, proof, merkle.root(ls[:old]), merkle.root(ls))


def test_consistency_proof_detects_rewritten_history():
    ls = leaves(12)
    tampered = list(ls)
    tampered[3] = merkle.leaf_hash(b"rewritten")
    proof = merkle.consistency_proof(7, tampered)
    assert not merkle.verify_consistency(7, 12, proof, merkle.root(ls[:7]), merkle.root(tampered))


def test_leaves_and_nodes_are_domain_separated():
    a, b = leaves(2)
    assert merkle.leaf_hash(a + b) != merkle.node_hash(a, b)
