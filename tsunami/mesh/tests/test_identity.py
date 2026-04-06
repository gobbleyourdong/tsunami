"""Tests for Layer 0: Identity."""

import tempfile
from pathlib import Path

from megalan.identity import NodeIdentity


def test_generate():
    identity = NodeIdentity.generate()
    assert len(identity.node_id) == 40
    assert identity.public_key is not None
    assert identity.exchange_public is not None


def test_node_id_deterministic():
    identity = NodeIdentity.generate()
    assert identity.node_id == identity._compute_id()


def test_sign_verify():
    identity = NodeIdentity.generate()
    data = b"hello megalan"
    sig = identity.sign(data)
    assert identity.verify(sig, data)
    assert not identity.verify(sig, b"wrong data")


def test_save_load():
    identity = NodeIdentity.generate()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    identity.save(path)
    loaded = NodeIdentity.load(path)
    assert loaded.node_id == identity.node_id
    path.unlink()


def test_shared_secret():
    a = NodeIdentity.generate()
    b = NodeIdentity.generate()
    secret_ab = a.derive_shared_secret(b.exchange_public)
    secret_ba = b.derive_shared_secret(a.exchange_public)
    assert secret_ab == secret_ba


def test_unique_ids():
    ids = {NodeIdentity.generate().node_id for _ in range(10)}
    assert len(ids) == 10
