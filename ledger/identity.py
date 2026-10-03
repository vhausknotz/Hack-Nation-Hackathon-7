"""Contributor identities: Ed25519 signing keys.

Every event is signed by the contributor that made it, so authorship can be checked by anyone
holding the public key. Private keys live in data/ledger/keys/ (gitignored) and never leave it.
"""

import base64
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import LEDGER_DIR

KEYS_DIR = LEDGER_DIR / "keys"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass
class Signer:
    contributor: str
    key: Ed25519PrivateKey

    @property
    def public_key(self) -> str:
        raw = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return "ed25519:" + _b64(raw)

    def sign(self, message: bytes) -> str:
        return "ed25519:" + _b64(self.key.sign(message))


def verify(public_key: str, message: bytes, signature: str) -> bool:
    if not (public_key.startswith("ed25519:") and signature.startswith("ed25519:")):
        return False
    try:
        Ed25519PublicKey.from_public_bytes(_unb64(public_key[8:])).verify(_unb64(signature[8:]), message)
        return True
    except (InvalidSignature, ValueError):
        return False


def load_or_create(contributor: str, keys_dir: Path = KEYS_DIR) -> Signer:
    """The signing key for a contributor, created on first use."""
    keys_dir.mkdir(parents=True, exist_ok=True)
    path = keys_dir / f"{contributor.replace(':', '_').replace('/', '_')}.pem"
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    else:
        key = Ed25519PrivateKey.generate()
        path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return Signer(contributor, key)
