"""Content replication — spread apps across the mesh.

Your neighbor can serve your app. Popular content spreads automatically.
Replication factor: 3 (content exists on at least 3 nearby nodes).

Protocol:
  Owner deploys → broadcasts REPLICATE_OFFER to peers
  Peer accepts → owner sends file chunks
  Peer now serves the content too

  Visitor requests content → routed to nearest peer that has it
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("megalan.replication")

TARGET_REPLICAS = 3
CHUNK_SIZE = 64 * 1024  # 64KB


@dataclass
class ReplicaInfo:
    """Tracks where content is replicated."""
    name: str
    owner_id: str
    content_hash: str
    holders: list[str]  # node_ids that have this content

    @property
    def replica_count(self) -> int:
        return len(self.holders)

    @property
    def needs_more(self) -> bool:
        return self.replica_count < TARGET_REPLICAS


class ReplicationManager:
    """Manages content replication across the mesh."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.replicas: dict[str, ReplicaInfo] = {}  # name → replica info

    def register_local(self, name: str, owner_id: str, content_hash: str):
        """Register content we're hosting locally."""
        if name not in self.replicas:
            self.replicas[name] = ReplicaInfo(
                name=name,
                owner_id=owner_id,
                content_hash=content_hash,
                holders=[self.node_id],
            )
        elif self.node_id not in self.replicas[name].holders:
            self.replicas[name].holders.append(self.node_id)

    def register_remote(self, name: str, owner_id: str, content_hash: str,
                        holder_id: str):
        """Register that a peer is holding content."""
        if name not in self.replicas:
            self.replicas[name] = ReplicaInfo(
                name=name,
                owner_id=owner_id,
                content_hash=content_hash,
                holders=[holder_id],
            )
        elif holder_id not in self.replicas[name].holders:
            self.replicas[name].holders.append(holder_id)

    def needs_replication(self) -> list[ReplicaInfo]:
        """Content we own that needs more replicas."""
        return [
            r for r in self.replicas.values()
            if r.owner_id == self.node_id and r.needs_more
        ]

    def find_holders(self, name: str) -> list[str]:
        """Find all node_ids that hold content for a name."""
        info = self.replicas.get(name)
        return info.holders if info else []

    def pack_content(self, content_dir: Path) -> list[dict]:
        """Pack a content directory into transferable chunks."""
        chunks = []
        for f in sorted(content_dir.rglob("*")):
            if f.is_file() and f.name != ".manifest.json":
                rel = str(f.relative_to(content_dir))
                data = f.read_bytes()
                for i in range(0, len(data), CHUNK_SIZE):
                    chunk = data[i:i + CHUNK_SIZE]
                    chunks.append({
                        "path": rel,
                        "offset": i,
                        "data": chunk.hex(),
                        "hash": hashlib.sha256(chunk).hexdigest(),
                        "total_size": len(data),
                    })
        return chunks

    def unpack_content(self, chunks: list[dict], dest_dir: Path):
        """Unpack received chunks into a content directory."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        files: dict[str, bytearray] = {}

        for chunk in sorted(chunks, key=lambda c: (c["path"], c["offset"])):
            path = chunk["path"]
            data = bytes.fromhex(chunk["data"])

            # Verify chunk hash
            expected = chunk["hash"]
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                log.warning(f"Chunk hash mismatch for {path} at offset {chunk['offset']}")
                continue

            if path not in files:
                files[path] = bytearray(chunk["total_size"])
            files[path][chunk["offset"]:chunk["offset"] + len(data)] = data

        for path, data in files.items():
            dest = dest_dir / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(bytes(data))

        log.info(f"Unpacked {len(files)} files to {dest_dir}")
