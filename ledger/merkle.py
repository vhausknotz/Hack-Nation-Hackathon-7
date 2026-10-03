"""Merkle tree hashing, inclusion proofs and consistency proofs, as in RFC 6962 (Certificate Transparency).

Leaves are domain-separated from interior nodes so that no leaf can be passed off as a node.
An inclusion proof shows an entry is in the log; a consistency proof shows a later log
extends an earlier one without changing anything that was already there.
"""

import hashlib

EMPTY_ROOT = hashlib.sha256(b"").hexdigest()


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _split(n: int) -> int:
    """Largest power of two strictly smaller than n."""
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


def root(leaves: list[bytes]) -> bytes:
    """Merkle tree hash over leaf hashes."""
    if not leaves:
        return bytes.fromhex(EMPTY_ROOT)
    if len(leaves) == 1:
        return leaves[0]
    k = _split(len(leaves))
    return node_hash(root(leaves[:k]), root(leaves[k:]))


def inclusion_proof(index: int, leaves: list[bytes]) -> list[bytes]:
    n = len(leaves)
    if not 0 <= index < n:
        raise IndexError(index)
    if n == 1:
        return []
    k = _split(n)
    if index < k:
        return inclusion_proof(index, leaves[:k]) + [root(leaves[k:])]
    return inclusion_proof(index - k, leaves[k:]) + [root(leaves[:k])]


def verify_inclusion(leaf: bytes, index: int, size: int, proof: list[bytes], expected_root: bytes) -> bool:
    """RFC 9162 section 2.1.3.2 verification."""
    if index >= size:
        return False
    fn, sn, r = index, size - 1, leaf
    for p in proof:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            if not fn & 1:
                while fn & 1 == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == expected_root


def consistency_proof(old_size: int, leaves: list[bytes]) -> list[bytes]:
    """Proof that the first old_size leaves form a prefix of `leaves` (RFC 6962 SUBPROOF)."""
    if not 0 < old_size <= len(leaves):
        raise ValueError("old_size must be in 1..len(leaves)")

    def subproof(m: int, d: list[bytes], complete: bool) -> list[bytes]:
        n = len(d)
        if m == n:
            return [] if complete else [root(d)]
        k = _split(n)
        if m <= k:
            return subproof(m, d[:k], complete) + [root(d[k:])]
        return subproof(m - k, d[k:], False) + [root(d[:k])]

    return subproof(old_size, leaves, True)


def verify_consistency(old_size: int, new_size: int, proof: list[bytes], old_root: bytes, new_root: bytes) -> bool:
    """RFC 9162 section 2.1.4.2 verification."""
    if old_size == new_size:
        return not proof and old_root == new_root
    if old_size == 0 or old_size > new_size or not proof:
        return False
    path = list(proof)
    if old_size & (old_size - 1) == 0:  # old_size is a power of two: its root is the first proof node
        path.insert(0, old_root)
    fn, sn = old_size - 1, new_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    fr = sr = path[0]
    for c in path[1:]:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            fr = node_hash(c, fr)
            sr = node_hash(c, sr)
            if not fn & 1:
                while fn & 1 == 0 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            sr = node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return sn == 0 and fr == old_root and sr == new_root
