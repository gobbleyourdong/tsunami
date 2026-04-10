"""Layer 6: Content hosting — serve Tsunami apps from the mesh.

Deploy: chunk files, hash them, distribute to nearby peers.
Serve: HTTP server on the node, serves content by name.
Replicate: popular content spreads to more peers automatically.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path
from http import HTTPStatus

log = logging.getLogger("megalan.hosting")

CHUNK_SIZE = 64 * 1024  # 64KB chunks (like BitTorrent pieces)


@dataclass
class ContentManifest:
    """Describes a deployed app — its files and their hashes."""
    name: str
    owner_id: str
    total_size: int
    file_count: int
    content_hash: str  # hash of the manifest itself
    files: dict[str, str] = field(default_factory=dict)  # relative_path → sha256
    created_at: float = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "owner_id": self.owner_id,
            "total_size": self.total_size,
            "file_count": self.file_count,
            "content_hash": self.content_hash,
            "files": self.files,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ContentManifest:
        return cls(**d)


class ContentStore:
    """Local content storage — holds deployed apps."""

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or Path.home() / ".megalan" / "content"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.manifests: dict[str, ContentManifest] = {}  # name → manifest
        self._load_manifests()

    def deploy(self, name: str, source_dir: str, owner_id: str) -> ContentManifest:
        """Deploy a directory of static files as a named app.

        Typically source_dir is a Tsunami build output (dist/).
        """
        source = Path(source_dir)
        if not source.is_dir():
            raise ValueError(f"Source directory does not exist: {source_dir}")

        # Copy files to content store
        dest = self._data_dir / name
        if dest.exists():
            # Remove old version
            import shutil
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        files = {}
        total_size = 0

        for filepath in source.rglob("*"):
            if filepath.is_file():
                rel = filepath.relative_to(source)
                dest_file = dest / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                data = filepath.read_bytes()
                dest_file.write_bytes(data)

                file_hash = hashlib.sha256(data).hexdigest()
                files[str(rel)] = file_hash
                total_size += len(data)

        # Create manifest
        import time
        manifest_data = json.dumps(files, sort_keys=True).encode()
        content_hash = hashlib.sha256(manifest_data).hexdigest()

        manifest = ContentManifest(
            name=name,
            owner_id=owner_id,
            total_size=total_size,
            file_count=len(files),
            content_hash=content_hash,
            files=files,
            created_at=time.time(),
        )
        self.manifests[name] = manifest
        self._save_manifest(name, manifest)

        log.info(f"Deployed '{name}': {len(files)} files, {total_size:,} bytes, hash={content_hash[:12]}...")
        return manifest

    def get_file(self, name: str, path: str) -> tuple[bytes, str] | None:
        """Get a file from a deployed app. Returns (data, content_type) or None."""
        # Strip leading/trailing slashes
        path = path.strip("/")

        # Default to index.html for empty/directory requests
        if not path:
            path = "index.html"

        file_path = self._data_dir / name / path

        # If path is a directory, try index.html inside it
        if file_path.is_dir():
            file_path = file_path / "index.html"

        if not file_path.exists() or not file_path.is_file():
            return None

        # Security: don't serve files outside the content directory
        try:
            file_path.resolve().relative_to(self._data_dir.resolve())
        except ValueError:
            return None

        data = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        return data, content_type

    def list_apps(self) -> list[ContentManifest]:
        return list(self.manifests.values())

    def _save_manifest(self, name: str, manifest: ContentManifest):
        path = self._data_dir / name / ".manifest.json"
        path.write_text(json.dumps(manifest.to_dict(), indent=2))

    def _load_manifests(self):
        for d in self._data_dir.iterdir():
            if d.is_dir():
                manifest_path = d / ".manifest.json"
                if manifest_path.exists():
                    try:
                        data = json.loads(manifest_path.read_text())
                        self.manifests[d.name] = ContentManifest.from_dict(data)
                    except Exception as e:
                        log.error(f"Failed to load manifest for {d.name}: {e}")


class ContentServer:
    """HTTP server that serves deployed apps by name.

    Routes:
      GET /<name>/          → serves index.html of the app
      GET /<name>/<path>    → serves a file from the app
      GET /api/status       → node status JSON
      GET /api/apps         → list deployed apps
    """

    def __init__(self, content_store: ContentStore, port: int = 8080,
                 node_status_fn: callable = None,
                 node_peers_fn: callable = None,
                 node_ledger_fn: callable = None,
                 node_names_fn: callable = None):
        self.store = content_store
        self.port = port
        self._node_status_fn = node_status_fn
        self._node_peers_fn = node_peers_fn
        self._node_ledger_fn = node_ledger_fn
        self._node_names_fn = node_names_fn
        self._server: asyncio.Server | None = None

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_request, "0.0.0.0", self.port,
        )
        log.info(f"Content server listening on http://0.0.0.0:{self.port}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_request(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter):
        try:
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=10,
            )
            try:
                request = request_line.decode("ascii", errors="ignore").strip()
            except Exception:
                writer.close()
                return
            if not request or not request.startswith(("GET", "POST", "HEAD", "PUT", "DELETE")):
                writer.close()
                return

            # Parse HTTP request line: GET /path HTTP/1.1
            parts = request.split()
            if len(parts) < 2:
                await self._send_response(writer, 400, b"Bad Request")
                return

            method, path = parts[0], parts[1]

            # Read and discard headers
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if line == b"\r\n" or line == b"\n" or not line:
                    break

            if method != "GET":
                await self._send_response(writer, 405, b"Method Not Allowed")
                return

            # Route
            if path == "/api/status":
                status = self._node_status_fn() if self._node_status_fn else {}
                body = json.dumps(status, indent=2).encode()
                await self._send_response(writer, 200, body, "application/json")

            elif path == "/api/apps":
                apps = [m.to_dict() for m in self.store.list_apps()]
                body = json.dumps(apps, indent=2).encode()
                await self._send_response(writer, 200, body, "application/json")

            elif path == "/api/peers":
                peers = self._node_peers_fn() if self._node_peers_fn else []
                body = json.dumps(peers, indent=2).encode()
                await self._send_response(writer, 200, body, "application/json")

            elif path == "/api/ledger":
                ledger = self._node_ledger_fn() if self._node_ledger_fn else {}
                body = json.dumps(ledger, indent=2).encode()
                await self._send_response(writer, 200, body, "application/json")

            elif path == "/api/names":
                names = self._node_names_fn() if self._node_names_fn else []
                body = json.dumps(names, indent=2).encode()
                await self._send_response(writer, 200, body, "application/json")

            else:
                # Serve content: /<name>/<path>
                path = path.lstrip("/")
                if "/" in path:
                    name, file_path = path.split("/", 1)
                else:
                    name, file_path = path, ""

                result = self.store.get_file(name, file_path)
                if result:
                    data, content_type = result
                    await self._send_response(writer, 200, data, content_type)
                else:
                    await self._send_response(writer, 404, b"Not Found")

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            log.error(f"Request handler error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _send_response(self, writer: asyncio.StreamWriter, status: int,
                             body: bytes, content_type: str = "text/plain"):
        status_text = HTTPStatus(status).phrase
        headers = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(headers.encode() + body)
        await writer.drain()
