"""MegaLAN Node — the runtime.

Listens for peer connections, manages the peer table,
handles messages, runs the heartbeat loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from .identity import NodeIdentity
from .peer import PeerConnection, PeerInfo, connect_to_peer
from .protocol import (
    Message, MessageType,
    ping_msg, pong_msg,
    peers_near_me_msg, peers_list_msg,
)
from .ledger import Ledger
from .naming import NameRegistry
from .hosting import ContentStore, ContentServer
from .executor import JobExecutor
from .replication import ReplicationManager
from .discovery import LocalDiscovery
from .peers import save_peers, load_peers, get_reconnect_candidates
from .benchmark import run_benchmark

log = logging.getLogger("megalan.node")

DEFAULT_PORT = 9999
MAX_PEERS = 32
TARGET_PEERS = 12
HEARTBEAT_INTERVAL = 30  # seconds
PEER_TIMEOUT = 300  # 5 minutes → mark offline
PEER_EXPIRY = 3600  # 1 hour → remove from table


@dataclass
class NodeConfig:
    port: int = DEFAULT_PORT
    max_peers: int = MAX_PEERS
    target_peers: int = TARGET_PEERS


class Node:
    """A MegaLAN node."""

    def __init__(self, identity: NodeIdentity, config: NodeConfig | None = None):
        self.identity = identity
        self.config = config or NodeConfig()
        self.peers: dict[str, PeerConnection] = {}  # node_id → connection
        self.peer_table: dict[str, PeerInfo] = {}  # node_id → info
        self.ledger = Ledger(identity.node_id)
        self.names = NameRegistry(identity.node_id)
        self.content = ContentStore()
        self.content_server = ContentServer(
            self.content, port=self.config.port + 1,
            node_status_fn=self.status,
            node_peers_fn=self._api_peers,
            node_ledger_fn=self._api_ledger,
            node_names_fn=self._api_names,
        )
        self.executor = JobExecutor()
        self.replication = ReplicationManager(identity.node_id)
        self.discovery = LocalDiscovery(identity.node_id, self.config.port, 0)
        self.capability: float = 0
        self._server: asyncio.Server | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._pending_results: dict[str, asyncio.Future] = {}

        # Load known peers from disk
        saved = load_peers()
        self.peer_table.update(saved)
        self._handlers: dict[MessageType, callable] = {
            MessageType.PING: self._handle_ping,
            MessageType.PONG: self._handle_pong,
            MessageType.PEERS_NEAR_ME: self._handle_peers_request,
            MessageType.PEERS_LIST: self._handle_peers_list,
            MessageType.VOUCH: self._handle_vouch,
            MessageType.JOB_OFFER: self._handle_job_offer,
            MessageType.RESULT: self._handle_result,
            MessageType.RESOLVE: self._handle_resolve,
            MessageType.CLAIM_NAME: self._handle_claim_name,
            MessageType.TRANSFER_NAME: self._handle_transfer_name,
            MessageType.REPLICATE_OFFER: self._handle_replicate_offer,
            MessageType.REPLICATE_ACCEPT: self._handle_replicate_accept,
            MessageType.REPLICATE_DATA: self._handle_replicate_data,
        }

    async def start(self):
        """Start the node — listen for connections, run heartbeat."""
        self.capability = run_benchmark()
        log.info(f"Node {self.identity.node_id[:12]}... starting")
        log.info(f"Capability score: {self.capability:.1f}")

        self._server = await asyncio.start_server(
            self._handle_incoming,
            "0.0.0.0",
            self.config.port,
        )
        self._running = True

        addr = self._server.sockets[0].getsockname()
        log.info(f"Listening on {addr[0]}:{addr[1]}")

        # Start content HTTP server on port+1
        await self.content_server.start()

        # Start mDNS discovery (zero-config local network)
        self.discovery.capability = self.capability
        self.discovery.on_peer_found(self._on_mdns_peer)
        await self.discovery.start()

        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._reconnect_saved_peers()),
            asyncio.create_task(self._save_peers_loop()),
        ]

    async def stop(self):
        """Shut down the node."""
        self._running = False
        # Cancel background tasks cleanly
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.discovery.stop()
        save_peers(self.peer_table)
        for conn in list(self.peers.values()):
            await conn.close()
        await self.content_server.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        log.info("Node stopped")

    async def connect(self, host: str, port: int = DEFAULT_PORT):
        """Connect to a peer by IP."""
        try:
            conn = await connect_to_peer(
                self.identity, host, port, self.capability, self.config.port
            )
            self.peers[conn.peer_info.node_id] = conn
            self.peer_table[conn.peer_info.node_id] = conn.peer_info
            log.info(f"Connected to {conn.peer_info.node_id[:12]}... at {host}:{port}")
            asyncio.create_task(self._recv_loop(conn))
        except Exception as e:
            log.error(f"Failed to connect to {host}:{port}: {e}")

    async def add_peer(self, address: str):
        """Add a peer by address string (ip:port)."""
        host, port_str = address.rsplit(":", 1)
        await self.connect(host, int(port_str))

    @property
    def credits(self) -> float:
        return self.ledger.balance

    @property
    def peer_count(self) -> int:
        return len([c for c in self.peers.values() if c.connected])

    def status(self) -> dict:
        return {
            "node_id": self.identity.node_id,
            "port": self.config.port,
            "http_port": self.config.port + 1,
            "capability": self.capability,
            "credits": self.ledger.balance,
            "peers_connected": self.peer_count,
            "peers_known": len(self.peer_table),
            "names_owned": len(self.names.my_names()),
            "apps_hosted": len(self.content.list_apps()),
        }

    async def deploy(self, name: str, source_dir: str) -> str | None:
        """Deploy a Tsunami build to the mesh with a plaintext name.

        Returns the URL where the app is accessible, or None on failure.
        """
        from .naming import name_cost

        # Check name cost
        from .naming import name_cost as calc_name_cost
        cost = calc_name_cost(name)
        # Only charge if this is a NEW name (not redeploying our own)
        existing = self.names.names.get(name)
        if not existing or existing.owner_id != self.identity.node_id:
            if self.ledger.balance < cost:
                log.warning(f"Deploy: need {cost} credits for name '{name}', have {self.ledger.balance:.0f}")
                # Allow it anyway for now — credits are earned by running the node
                # In production this would block until you have enough credits

        # Validate and claim name
        err = self.names.claim(
            name,
            content_hash="pending",
            address=f"0.0.0.0:{self.config.port + 1}",
        )
        if isinstance(err, str):
            log.error(f"Deploy failed: {err}")
            return None

        # Deploy content
        manifest = self.content.deploy(name, source_dir, self.identity.node_id)

        # Update name record with real content hash
        self.names.names[name].content_hash = manifest.content_hash

        # Broadcast name claim to peers
        from .protocol import claim_name_msg
        msg = claim_name_msg(
            self.identity.node_id, name, manifest.content_hash
        )
        msg.signature = self.identity.sign(msg.signing_data())
        await self._broadcast(msg)

        # Track in replication manager
        self.replication.register_local(name, self.identity.node_id, manifest.content_hash)

        # Offer replicas to peers
        asyncio.create_task(self._offer_replicas(name, manifest.content_hash))

        url = f"http://localhost:{self.config.port + 1}/{name}/"
        log.info(f"Deployed '{name}' → {url}")
        return url

    async def _offer_replicas(self, name: str, content_hash: str):
        """Offer content replication to connected peers."""
        msg = Message(
            type=MessageType.REPLICATE_OFFER,
            sender=self.identity.node_id,
            payload={"name": name, "content_hash": content_hash},
        )
        msg.signature = self.identity.sign(msg.signing_data())
        await self._broadcast(msg)

    async def request_build(self, prompt: str, timeout: int = 600) -> dict | None:
        """Request a Tsunami build from the network.

        Sends JOB_OFFER to all peers, waits for result.
        This is the "dad in the backyard" flow — send a prompt, get an app.
        """
        import uuid
        from .protocol import job_offer_msg

        job_id = uuid.uuid4().hex
        self._pending_results[job_id] = asyncio.Future()

        msg = job_offer_msg(
            self.identity.node_id,
            job_id=job_id,
            job_type="tsunami_agent",
            payload={"prompt": prompt},
            requirements={"min_capability": 10, "min_trust": 0.3},
            offered_credits=100,
            timeout_s=timeout,
        )
        msg.signature = self.identity.sign(msg.signing_data())
        await self._broadcast(msg)

        log.info(f"Requested build: '{prompt[:50]}...' job={job_id[:12]}...")

        try:
            result = await asyncio.wait_for(
                self._pending_results[job_id], timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            log.warning(f"Build request timed out: {job_id[:12]}...")
            return None
        finally:
            self._pending_results.pop(job_id, None)

    async def _handle_result(self, msg: Message, conn: PeerConnection):
        """Handle a job result coming back from a worker."""
        job_id = msg.payload.get("job_id", "")
        success = msg.payload.get("success", False)

        # Update trust based on job outcome
        if success:
            self._update_trust(msg.sender, +0.02)
            self.ledger.verify(job_id, ok=True)
        else:
            self._update_trust(msg.sender, -0.10)
            self.ledger.verify(job_id, ok=False)

        # Resolve pending future if we requested this job
        if job_id in self._pending_results:
            future = self._pending_results[job_id]
            if not future.done():
                future.set_result(msg.payload)
                log.info(f"Result received for job {job_id[:12]}... "
                         f"success={success} worker={msg.sender[:12]}...")

    # --- Incoming connections ---

    async def _handle_incoming(self, reader: asyncio.StreamReader,
                               writer: asyncio.StreamWriter):
        conn = PeerConnection(self.identity, reader, writer, is_initiator=False)
        try:
            peer_info = await conn.handshake(self.capability, self.config.port)
            if len(self.peers) >= self.config.max_peers:
                log.warning(f"Max peers reached, rejecting {peer_info.node_id[:12]}...")
                await conn.close()
                return
            self.peers[peer_info.node_id] = conn
            self.peer_table[peer_info.node_id] = peer_info
            log.info(f"Accepted connection from {peer_info.node_id[:12]}...")
            await self._recv_loop(conn)
        except Exception as e:
            log.error(f"Incoming connection failed: {e}")
            await conn.close()

    # --- Message receive loop ---

    async def _recv_loop(self, conn: PeerConnection):
        while conn.connected and self._running:
            try:
                msg = await asyncio.wait_for(conn.recv(), timeout=PEER_TIMEOUT)
                handler = self._handlers.get(msg.type)
                if handler:
                    await handler(msg, conn)
                else:
                    log.debug(f"Unhandled message type: {msg.type}")

                # Update last_seen
                if conn.peer_info and conn.peer_info.node_id in self.peer_table:
                    self.peer_table[conn.peer_info.node_id].last_seen = time.time()

            except asyncio.TimeoutError:
                log.debug(f"Peer {conn.peer_info.node_id[:12]}... timed out")
                break
            except asyncio.IncompleteReadError:
                log.debug(f"Peer {conn.peer_info.node_id[:12]}... disconnected")
                break
            except Exception as e:
                log.error(f"Error receiving from peer: {e}")
                break

        # Clean up
        if conn.peer_info:
            self.peers.pop(conn.peer_info.node_id, None)
        await conn.close()

    # --- Message handlers ---

    async def _handle_ping(self, msg: Message, conn: PeerConnection):
        if conn.peer_info and conn.peer_info.node_id in self.peer_table:
            self.peer_table[conn.peer_info.node_id].credit_balance = msg.payload.get("credit_balance", 0)
        reply = pong_msg(self.identity.node_id, self.ledger.balance)
        await conn.send(reply)

    async def _handle_pong(self, msg: Message, conn: PeerConnection):
        if conn.peer_info and conn.peer_info.node_id in self.peer_table:
            self.peer_table[conn.peer_info.node_id].credit_balance = msg.payload.get("credit_balance", 0)

    async def _handle_peers_request(self, msg: Message, conn: PeerConnection):
        known = [
            {
                "node_id": info.node_id,
                "address": info.address,
                "capability": info.capability,
                "hops": info.hops,
            }
            for nid, info in self.peer_table.items()
            if nid != msg.sender and info.last_seen > time.time() - PEER_TIMEOUT
        ]
        reply = peers_list_msg(self.identity.node_id, known[:20])
        await conn.send(reply)

    async def _handle_peers_list(self, msg: Message, conn: PeerConnection):
        for peer_data in msg.payload.get("peers", []):
            nid = peer_data["node_id"]
            if nid == self.identity.node_id:
                continue
            if nid not in self.peer_table:
                self.peer_table[nid] = PeerInfo(
                    node_id=nid,
                    address=peer_data["address"],
                    capability=peer_data.get("capability", 0),
                    hops=peer_data.get("hops", 1) + 1,
                    trust=0.3,  # stranger
                    vouched_by=[msg.sender],
                )
                log.info(f"Discovered peer {nid[:12]}... via {msg.sender[:12]}...")

    async def _handle_vouch(self, msg: Message, conn: PeerConnection):
        vouched_id = msg.payload.get("node_id")
        if not vouched_id or vouched_id == self.identity.node_id:
            return
        voucher_trust = self.peer_table.get(msg.sender, PeerInfo(node_id="", address="")).trust
        new_trust = voucher_trust * 0.5
        if vouched_id in self.peer_table:
            self.peer_table[vouched_id].trust = max(self.peer_table[vouched_id].trust, new_trust)
            if msg.sender not in self.peer_table[vouched_id].vouched_by:
                self.peer_table[vouched_id].vouched_by.append(msg.sender)
        log.debug(f"Vouch for {vouched_id[:12]}... from {msg.sender[:12]}... (trust={new_trust:.2f})")

    async def _handle_job_offer(self, msg: Message, conn: PeerConnection):
        from .protocol import job_accept_msg, clock_in_msg, clock_out_msg, result_msg

        job_id = msg.payload["job_id"]
        job_type = msg.payload.get("job_type", "tsunami_agent")
        requirements = msg.payload.get("requirements", {})

        # Check if we meet requirements
        min_cap = requirements.get("min_capability", 0)
        min_trust = requirements.get("min_trust", 0)
        peer_trust = self.peer_table.get(msg.sender, PeerInfo(node_id="", address="")).trust

        if self.capability < min_cap:
            log.info(f"Job {job_id[:12]}... rejected: capability {self.capability} < {min_cap}")
            return
        if peer_trust < min_trust:
            log.info(f"Job {job_id[:12]}... rejected: trust {peer_trust} < {min_trust}")
            return

        log.info(f"Job accepted: {job_id[:12]}... type={job_type} from {msg.sender[:12]}...")

        # Accept
        accept = job_accept_msg(self.identity.node_id, job_id)
        await conn.send(accept)

        # Clock in
        self.ledger.clock_in(job_id, self.identity.node_id, msg.sender)
        ci = clock_in_msg(self.identity.node_id, job_id)
        await conn.send(ci)
        await self._broadcast(ci, exclude=msg.sender)

        # Execute the job
        job_result = await self.executor.execute(
            job_id, job_type, msg.payload.get("job_payload", {}),
        )

        # Clock out
        credits = self.ledger.clock_out(
            job_id, job_result.result_hash,
            capability=self.capability, job_type=job_type,
        )
        co = clock_out_msg(self.identity.node_id, job_id, job_result.result_hash)
        await conn.send(co)
        await self._broadcast(co, exclude=msg.sender)

        # Send result
        result_data = {
            "success": job_result.success,
            "result_hash": job_result.result_hash,
            "duration_s": job_result.duration_s,
            "output_dir": job_result.output_dir,
            "error": job_result.error,
        }
        res = result_msg(self.identity.node_id, job_id, result_data)
        await conn.send(res)

        log.info(f"Job {job_id[:12]}... completed: success={job_result.success} "
                 f"duration={job_result.duration_s:.1f}s credits={credits:.2f}")

    async def _handle_resolve(self, msg: Message, conn: PeerConnection):
        name = msg.payload.get("name", "")
        record = self.names.resolve(name)
        if record:
            from .protocol import resolve_response_msg
            reply = resolve_response_msg(
                self.identity.node_id, name,
                record.owner_id, record.address, record.content_hash,
            )
            await conn.send(reply)

    async def _handle_claim_name(self, msg: Message, conn: PeerConnection):
        """Witness a name claim from a peer."""
        name = msg.payload.get("name", "")
        content_hash = msg.payload.get("content_hash", "")
        if name and msg.sender:
            from .naming import NameRecord
            record = NameRecord(
                name=name,
                owner_id=msg.sender,
                content_hash=content_hash,
                address=conn.peer_info.address if conn.peer_info else "",
                claimed_at=msg.timestamp,
                last_active=msg.timestamp,
                signature=msg.signature,
                witnesses=[self.identity.node_id],
            )
            self.names.cache_resolution(record)
            log.info(f"Witnessed name claim: '{name}' by {msg.sender[:12]}...")

    async def _handle_transfer_name(self, msg: Message, conn: PeerConnection):
        """Witness a name transfer between two peers."""
        name = msg.payload.get("name", "")
        new_owner = msg.payload.get("new_owner_id", "")
        if name and new_owner:
            record = self.names.names.get(name)
            if record and record.owner_id == msg.sender:
                record.owner_id = new_owner
                record.last_active = msg.timestamp
                record.signature = msg.signature
                log.info(f"Witnessed name transfer: '{name}' → {new_owner[:12]}...")
            # Forward to other peers
            await self._broadcast(msg, exclude=msg.sender)

    async def _handle_replicate_offer(self, msg: Message, conn: PeerConnection):
        """A peer is offering to replicate content to us."""
        name = msg.payload.get("name", "")
        content_hash = msg.payload.get("content_hash", "")
        if not name:
            return

        # Do we already have this content?
        if name in self.content.manifests:
            existing = self.content.manifests[name]
            if existing.content_hash == content_hash:
                log.debug(f"Already have '{name}', skipping replication")
                return

        # Accept — request the data
        log.info(f"Accepting replica of '{name}' from {msg.sender[:12]}...")
        accept = Message(
            type=MessageType.REPLICATE_ACCEPT,
            sender=self.identity.node_id,
            payload={"name": name},
        )
        await conn.send(accept)

        # Track that this peer holds the content
        self.replication.register_remote(name, msg.sender, content_hash, msg.sender)

    async def _handle_replicate_accept(self, msg: Message, conn: PeerConnection):
        """Peer wants our content — pack and send it."""
        name = msg.payload.get("name", "")
        if not name or name not in self.content.manifests:
            return

        manifest = self.content.manifests[name]
        content_dir = self.content._data_dir / name

        if not content_dir.exists():
            log.warning(f"Content directory missing for '{name}'")
            return

        # Pack content into chunks
        chunks = self.replication.pack_content(content_dir)

        # Send as REPLICATE_DATA
        data_msg = Message(
            type=MessageType.REPLICATE_DATA,
            sender=self.identity.node_id,
            payload={
                "name": name,
                "owner_id": manifest.owner_id,
                "content_hash": manifest.content_hash,
                "chunks": chunks,
            },
        )
        await conn.send(data_msg)
        self.replication.register_remote(name, manifest.owner_id, manifest.content_hash, msg.sender)
        log.info(f"Sent replica of '{name}' to {msg.sender[:12]}... ({len(chunks)} chunks)")

    async def _handle_replicate_data(self, msg: Message, conn: PeerConnection):
        """Receive replicated content chunks from a peer."""
        name = msg.payload.get("name", "")
        chunks = msg.payload.get("chunks", [])
        if not name or not chunks:
            return

        # Unpack into content store
        from pathlib import Path
        dest = Path.home() / ".megalan" / "content" / name
        self.replication.unpack_content(chunks, dest)

        # Create manifest
        owner_id = msg.payload.get("owner_id", msg.sender)
        content_hash = msg.payload.get("content_hash", "")
        from .hosting import ContentManifest
        import time as _time
        manifest = ContentManifest(
            name=name,
            owner_id=owner_id,
            total_size=sum(len(bytes.fromhex(c["data"])) for c in chunks),
            file_count=len(set(c["path"] for c in chunks)),
            content_hash=content_hash,
            files={c["path"]: c["hash"] for c in chunks},
            created_at=_time.time(),
        )
        self.content.manifests[name] = manifest
        self.content._save_manifest(name, manifest)
        self.replication.register_local(name, owner_id, content_hash)

        log.info(f"Replicated '{name}' — {manifest.file_count} files, {manifest.total_size:,} bytes")

    # --- Broadcast ---

    async def _broadcast(self, msg: Message, exclude: str = ""):
        for nid, conn in list(self.peers.items()):
            if nid == exclude:
                continue
            if conn.connected:
                try:
                    await conn.send(msg)
                except Exception:
                    pass

    # --- Background loops ---

    async def _heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            msg = ping_msg(self.identity.node_id, self.ledger.balance)
            await self._broadcast(msg)

    async def _cleanup_loop(self):
        while self._running:
            await asyncio.sleep(60)
            now = time.time()
            expired = [
                nid for nid, info in self.peer_table.items()
                if now - info.last_seen > PEER_EXPIRY and nid not in self.peers
            ]
            for nid in expired:
                del self.peer_table[nid]
                log.debug(f"Expired peer {nid[:12]}...")
            self.names.cleanup_expired()

    async def _reconnect_saved_peers(self):
        """On startup, try to reconnect to previously known peers."""
        candidates = get_reconnect_candidates(self.peer_table)
        if not candidates:
            return

        # Filter out ephemeral ports (>10000 are likely OS-assigned source ports)
        valid = []
        for p in candidates:
            try:
                _, port_str = p.address.rsplit(":", 1)
                port = int(port_str)
                if port < 10000:  # likely a real listening port
                    valid.append(p)
            except (ValueError, AttributeError):
                continue

        if not valid:
            return

        log.info(f"Reconnecting to {len(valid)} saved peers...")
        for peer_info in valid[:self.config.target_peers]:
            if peer_info.node_id in self.peers:
                continue
            try:
                host, port_str = peer_info.address.rsplit(":", 1)
                await self.connect(host, int(port_str))
            except Exception as e:
                log.debug(f"Failed to reconnect to {peer_info.node_id[:12]}...: {e}")

    async def _save_peers_loop(self):
        """Periodically save peer table to disk."""
        while self._running:
            await asyncio.sleep(300)  # every 5 minutes
            save_peers(self.peer_table)

    def _api_peers(self) -> list:
        return [
            {
                "node_id": info.node_id,
                "address": info.address,
                "hops": info.hops,
                "trust": round(info.trust, 3),
                "capability": info.capability,
                "connected": info.node_id in self.peers and self.peers[info.node_id].connected,
                "last_seen": info.last_seen,
            }
            for info in self.peer_table.values()
        ]

    def _api_ledger(self) -> dict:
        return self.ledger.summary()

    def _api_names(self) -> list:
        return [r.to_dict() for r in self.names.names.values()]

    def _on_mdns_peer(self, discovered):
        """Callback when mDNS finds a peer on the local network."""
        if discovered.node_id in self.peers:
            return  # already connected
        if len(self.peers) >= self.config.max_peers:
            return
        # Schedule connection (can't await from callback)
        asyncio.get_event_loop().create_task(
            self.connect(discovered.host, discovered.port)
        )

    def _update_trust(self, node_id: str, delta: float):
        """Update trust score for a peer."""
        info = self.peer_table.get(node_id)
        if info:
            info.trust = max(0.0, min(1.0, info.trust + delta))
