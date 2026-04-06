"""Layer 5: Naming — plaintext names on the mesh.

No .com. No registrar. No ICANN. No annual fees.
Claim a name, resolve it by gossip, keep it by contributing.

Names are plaintext. No TLD. No dots. Just a word.
"mystore", "jbs-cards", "the-card-shop"
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("megalan.naming")

# Cost in credits to claim a name (burned, not transferred)
NAME_COST = {
    (1, 3): 500,    # 1-3 chars: premium
    (4, 6): 100,    # 4-6 chars: moderate
    (7, 12): 50,    # 7-12 chars: standard
    (13, 999): 10,  # 13+ chars: cheap
}

# Name expires if owner inactive for this long
NAME_EXPIRY_DAYS = 30


@dataclass
class NameRecord:
    name: str
    owner_id: str
    content_hash: str
    address: str  # ip:port where content is served
    claimed_at: float
    last_active: float
    signature: bytes = b""
    witnesses: list[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        return time.time() - self.last_active > NAME_EXPIRY_DAYS * 86400

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "owner_id": self.owner_id,
            "content_hash": self.content_hash,
            "address": self.address,
            "claimed_at": self.claimed_at,
            "last_active": self.last_active,
            "signature": self.signature.hex(),
            "witnesses": self.witnesses,
        }

    @classmethod
    def from_dict(cls, d: dict) -> NameRecord:
        return cls(
            name=d["name"],
            owner_id=d["owner_id"],
            content_hash=d["content_hash"],
            address=d["address"],
            claimed_at=d["claimed_at"],
            last_active=d["last_active"],
            signature=bytes.fromhex(d.get("signature", "")),
            witnesses=d.get("witnesses", []),
        )


def name_cost(name: str) -> int:
    """Calculate credit cost to claim a name."""
    n = len(name)
    for (lo, hi), cost in NAME_COST.items():
        if lo <= n <= hi:
            return cost
    return 10


def validate_name(name: str) -> str | None:
    """Validate a name. Returns error string or None if valid."""
    if not name:
        return "Name cannot be empty"
    if len(name) > 64:
        return "Name too long (max 64 chars)"
    if not all(c.isalnum() or c in "-_" for c in name):
        return "Name can only contain letters, numbers, hyphens, underscores"
    if name.startswith("-") or name.startswith("_"):
        return "Name cannot start with - or _"
    return None


class NameRegistry:
    """Local name registry — tracks names this node knows about."""

    def __init__(self, node_id: str, data_dir: Path | None = None):
        self.node_id = node_id
        self.names: dict[str, NameRecord] = {}  # name → record
        self._resolve_cache: dict[str, tuple[NameRecord, float]] = {}  # name → (record, cached_at)
        self._cache_ttl = 3600  # 1 hour
        self._data_dir = data_dir or Path.home() / ".megalan" / "names"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def claim(self, name: str, content_hash: str, address: str,
              signature: bytes = b"") -> NameRecord | str:
        """Claim a name. Returns NameRecord on success, error string on failure."""
        err = validate_name(name)
        if err:
            return err

        existing = self.names.get(name)
        if existing and not existing.is_expired() and existing.owner_id != self.node_id:
            return f"Name '{name}' already claimed by {existing.owner_id[:12]}..."

        record = NameRecord(
            name=name,
            owner_id=self.node_id,
            content_hash=content_hash,
            address=address,
            claimed_at=time.time(),
            last_active=time.time(),
            signature=signature,
        )
        self.names[name] = record
        self._save()
        log.info(f"Claimed name: {name} → {address}")
        return record

    def resolve(self, name: str) -> NameRecord | None:
        """Resolve a name from local registry or cache."""
        # Check local registry
        record = self.names.get(name)
        if record and not record.is_expired():
            return record

        # Check cache
        cached = self._resolve_cache.get(name)
        if cached:
            record, cached_at = cached
            if time.time() - cached_at < self._cache_ttl and not record.is_expired():
                return record

        return None

    def cache_resolution(self, record: NameRecord):
        """Cache a name resolution received from peers."""
        self._resolve_cache[record.name] = (record, time.time())
        # Also store in registry if we don't have it
        if record.name not in self.names:
            self.names[record.name] = record

    def record_activity(self, name: str):
        """Update last_active for a name we own."""
        record = self.names.get(name)
        if record and record.owner_id == self.node_id:
            record.last_active = time.time()
            self._save()

    def my_names(self) -> list[NameRecord]:
        """Names owned by this node."""
        return [r for r in self.names.values() if r.owner_id == self.node_id]

    def transfer(self, name: str, new_owner_id: str,
                 signature: bytes = b"") -> NameRecord | str:
        """Transfer a name to a new owner. Only the current owner can transfer.

        The actual payment (BTC or otherwise) happens outside the protocol.
        MegaLAN only sees the signed transfer message.
        """
        record = self.names.get(name)
        if not record:
            return f"Name '{name}' not found"
        if record.owner_id != self.node_id:
            return f"You don't own '{name}'"

        record.owner_id = new_owner_id
        record.last_active = time.time()
        record.signature = signature
        self._save()
        log.info(f"Transferred name '{name}' → {new_owner_id[:12]}...")
        return record

    def cleanup_expired(self):
        """Remove expired names."""
        expired = [n for n, r in self.names.items() if r.is_expired()]
        for n in expired:
            del self.names[n]
            log.info(f"Name expired: {n}")
        if expired:
            self._save()

    def _save(self):
        path = self._data_dir / "names.json"
        data = {n: r.to_dict() for n, r in self.names.items()}
        path.write_text(json.dumps(data, indent=2))

    def _load(self):
        path = self._data_dir / "names.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            for name, d in data.items():
                self.names[name] = NameRecord.from_dict(d)
            log.info(f"Name registry loaded: {len(self.names)} names")
        except Exception as e:
            log.error(f"Failed to load name registry: {e}")
