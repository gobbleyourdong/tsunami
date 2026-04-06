"""Peer persistence — remember your neighbors across restarts.

Saves known peers to ~/.megalan/peers.json so you don't have to
re-add everyone every time. Automatically reconnects on startup.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .peer import PeerInfo

log = logging.getLogger("megalan.peers")

PEERS_FILE = Path.home() / ".megalan" / "peers.json"


def save_peers(peers: dict[str, PeerInfo], path: Path = PEERS_FILE):
    """Save known peers to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    for nid, info in peers.items():
        data[nid] = {
            "node_id": info.node_id,
            "address": info.address,
            "hops": info.hops,
            "trust": info.trust,
            "capability": info.capability,
            "last_seen": info.last_seen,
            "vouched_by": info.vouched_by,
        }
    path.write_text(json.dumps(data, indent=2))
    log.debug(f"Saved {len(data)} peers to {path}")


def load_peers(path: Path = PEERS_FILE) -> dict[str, PeerInfo]:
    """Load known peers from disk."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        peers = {}
        for nid, d in data.items():
            peers[nid] = PeerInfo(
                node_id=d["node_id"],
                address=d["address"],
                hops=d.get("hops", 1),
                trust=d.get("trust", 0.5),
                capability=d.get("capability", 0),
                last_seen=d.get("last_seen", 0),
                vouched_by=d.get("vouched_by", []),
            )
        log.info(f"Loaded {len(peers)} known peers from {path}")
        return peers
    except Exception as e:
        log.error(f"Failed to load peers: {e}")
        return {}


def get_reconnect_candidates(peers: dict[str, PeerInfo],
                             max_age_hours: int = 72) -> list[PeerInfo]:
    """Get peers worth reconnecting to, sorted by trust then recency."""
    cutoff = time.time() - (max_age_hours * 3600)
    candidates = [
        p for p in peers.values()
        if p.last_seen > cutoff and p.address and p.address != "unknown"
    ]
    candidates.sort(key=lambda p: (-p.trust, -p.last_seen))
    return candidates
