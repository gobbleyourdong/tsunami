"""Tests for Layer 5: Naming."""

import tempfile
import time
from pathlib import Path

from megalan.naming import NameRegistry, validate_name, name_cost


def test_validate_name():
    assert validate_name("mystore") is None
    assert validate_name("jbs-cards") is None
    assert validate_name("app_123") is None
    assert validate_name("") is not None
    assert validate_name("-bad") is not None
    assert validate_name("_bad") is not None
    assert validate_name("has spaces") is not None
    assert validate_name("a" * 65) is not None


def test_name_cost():
    assert name_cost("ab") == 500       # 1-3 chars premium
    assert name_cost("abc") == 500
    assert name_cost("abcd") == 100     # 4-6 chars
    assert name_cost("abcdefg") == 50   # 7-12 chars
    assert name_cost("a" * 20) == 10    # 13+ chars cheap


def test_claim_and_resolve():
    with tempfile.TemporaryDirectory() as d:
        reg = NameRegistry("node1", Path(d))
        result = reg.claim("mystore", "hash123", "localhost:9999")
        assert not isinstance(result, str)  # not an error
        assert result.name == "mystore"
        assert result.owner_id == "node1"

        resolved = reg.resolve("mystore")
        assert resolved is not None
        assert resolved.content_hash == "hash123"


def test_claim_duplicate():
    with tempfile.TemporaryDirectory() as d:
        reg = NameRegistry("node1", Path(d))
        reg.claim("taken", "hash1", "addr1")

        reg2 = NameRegistry("node2", Path(d))
        reg2.names = reg.names  # share state
        result = reg2.claim("taken", "hash2", "addr2")
        assert isinstance(result, str)  # error — already claimed


def test_transfer():
    with tempfile.TemporaryDirectory() as d:
        reg = NameRegistry("owner", Path(d))
        reg.claim("valuable", "hash1", "addr1")

        result = reg.transfer("valuable", "new_owner")
        assert not isinstance(result, str)
        assert result.owner_id == "new_owner"


def test_transfer_not_owner():
    with tempfile.TemporaryDirectory() as d:
        reg = NameRegistry("not_owner", Path(d))
        reg.names["taken"] = type("R", (), {
            "name": "taken", "owner_id": "someone_else",
            "is_expired": lambda: False,
        })()
        result = reg.transfer("taken", "buyer")
        assert isinstance(result, str)  # error


def test_expiry():
    with tempfile.TemporaryDirectory() as d:
        reg = NameRegistry("node1", Path(d))
        record = reg.claim("expiring", "hash1", "addr1")
        record.last_active = time.time() - (31 * 86400)  # 31 days ago
        assert record.is_expired()
        reg.cleanup_expired()
        assert "expiring" not in reg.names


def test_cache_resolution():
    with tempfile.TemporaryDirectory() as d:
        reg = NameRegistry("node1", Path(d))
        from megalan.naming import NameRecord
        remote = NameRecord(
            name="remote-app", owner_id="node2",
            content_hash="hash2", address="192.168.1.5:9999",
            claimed_at=time.time(), last_active=time.time(),
        )
        reg.cache_resolution(remote)
        resolved = reg.resolve("remote-app")
        assert resolved is not None
        assert resolved.owner_id == "node2"
