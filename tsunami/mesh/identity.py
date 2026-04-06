"""Layer 0: Identity — every node is a keypair.

Ed25519 for signing (timecards, name claims, vouches).
X25519 for key exchange (encrypted peer connections).
Node ID = SHA-256(public_key)[:20] — 40 hex chars.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

log = logging.getLogger("megalan.identity")

IDENTITY_DIR = Path.home() / ".megalan"
IDENTITY_FILE = IDENTITY_DIR / "identity.json"


class NodeIdentity:
    """A node's cryptographic identity."""

    def __init__(
        self,
        signing_key: Ed25519PrivateKey,
        exchange_key: X25519PrivateKey,
    ):
        self._signing_key = signing_key
        self._exchange_key = exchange_key
        self.public_key = signing_key.public_key()
        self.exchange_public = exchange_key.public_key()
        self.node_id = self._compute_id()

    def _compute_id(self) -> str:
        raw = self.public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(raw).hexdigest()[:40]

    def sign(self, data: bytes) -> bytes:
        return self._signing_key.sign(data)

    def verify(self, signature: bytes, data: bytes) -> bool:
        try:
            self.public_key.verify(signature, data)
            return True
        except Exception:
            return False

    @staticmethod
    def verify_with_key(public_key: Ed25519PublicKey, signature: bytes, data: bytes) -> bool:
        try:
            public_key.verify(signature, data)
            return True
        except Exception:
            return False

    def derive_shared_secret(self, peer_exchange_public: X25519PublicKey) -> bytes:
        return self._exchange_key.exchange(peer_exchange_public)

    def public_key_bytes(self) -> bytes:
        return self.public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def exchange_public_bytes(self) -> bytes:
        return self.exchange_public.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def save(self, path: Path = IDENTITY_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        signing_bytes = self._signing_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        exchange_bytes = self._exchange_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        data = {
            "node_id": self.node_id,
            "signing_key": signing_bytes.hex(),
            "exchange_key": exchange_bytes.hex(),
        }
        path.write_text(json.dumps(data, indent=2))
        path.chmod(0o600)
        log.info(f"Identity saved to {path} — node_id: {self.node_id}")

    @classmethod
    def load(cls, path: Path = IDENTITY_FILE) -> NodeIdentity:
        data = json.loads(path.read_text())
        signing_key = Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(data["signing_key"])
        )
        exchange_key = X25519PrivateKey.from_private_bytes(
            bytes.fromhex(data["exchange_key"])
        )
        identity = cls(signing_key, exchange_key)
        log.info(f"Identity loaded — node_id: {identity.node_id}")
        return identity

    @classmethod
    def generate(cls) -> NodeIdentity:
        signing_key = Ed25519PrivateKey.generate()
        exchange_key = X25519PrivateKey.generate()
        identity = cls(signing_key, exchange_key)
        log.info(f"New identity generated — node_id: {identity.node_id}")
        return identity

    @classmethod
    def load_or_generate(cls, path: Path = IDENTITY_FILE) -> NodeIdentity:
        if path.exists():
            return cls.load(path)
        identity = cls.generate()
        identity.save(path)
        return identity
