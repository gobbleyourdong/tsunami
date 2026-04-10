"""Peer connection — encrypted TCP between two nodes.

Handshake:
  A → B: HELLO { node_id, pubkey, exchange_pubkey }
  B → A: HELLO { node_id, pubkey, exchange_pubkey }
  Both derive shared secret via X25519
  All subsequent messages encrypted with XChaCha20-Poly1305
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import os
import hashlib

from .identity import NodeIdentity
from .protocol import Message, MessageType, hello_msg

log = logging.getLogger("megalan.peer")


@dataclass
class PeerInfo:
    node_id: str
    address: str  # ip:port
    pubkey_hex: str = ""
    exchange_pubkey_hex: str = ""
    hops: int = 1
    trust: float = 0.5
    capability: float = 0
    last_seen: float = field(default_factory=time.time)
    vouched_by: list[str] = field(default_factory=list)
    credit_balance: float = 0


class PeerConnection:
    """Encrypted TCP connection to a single peer."""

    def __init__(self, identity: NodeIdentity, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, is_initiator: bool = True):
        self.identity = identity
        self.reader = reader
        self.writer = writer
        self.is_initiator = is_initiator
        self.peer_info: PeerInfo | None = None
        self._cipher: ChaCha20Poly1305 | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and not self.writer.is_closing()

    async def handshake(self, capability: float = 0, listen_port: int = 0) -> PeerInfo:
        """Exchange HELLO messages and derive shared encryption key."""
        my_hello = hello_msg(
            self.identity.node_id,
            self.identity.public_key_bytes().hex(),
            self.identity.exchange_public_bytes().hex(),
            capability,
            listen_port,
        )
        my_hello.signature = self.identity.sign(my_hello.signing_data())
        await self._send_raw(my_hello.to_bytes())

        peer_data = await self._recv_raw()
        peer_hello = Message.from_bytes(peer_data)

        if peer_hello.type != MessageType.HELLO:
            raise ConnectionError(f"Expected HELLO, got {peer_hello.type}")

        peer_exchange_bytes = bytes.fromhex(peer_hello.payload["exchange_pubkey"])
        peer_exchange_pub = X25519PublicKey.from_public_bytes(peer_exchange_bytes)
        shared_secret = self.identity.derive_shared_secret(peer_exchange_pub)

        key = hashlib.sha256(shared_secret).digest()
        self._cipher = ChaCha20Poly1305(key)

        # Use the advertised listen_port for the peer address (not the ephemeral source port)
        peer_listen_port = peer_hello.payload.get("listen_port", 0)
        peername = self.writer.get_extra_info("peername")
        if peer_listen_port and peername:
            peer_addr = f"{peername[0]}:{peer_listen_port}"
        else:
            peer_addr = self._peer_address()

        self.peer_info = PeerInfo(
            node_id=peer_hello.sender,
            address=peer_addr,
            pubkey_hex=peer_hello.payload["pubkey"],
            exchange_pubkey_hex=peer_hello.payload["exchange_pubkey"],
            capability=peer_hello.payload.get("capability", 0),
        )
        self._connected = True
        log.info(f"Handshake complete with {self.peer_info.node_id[:12]}... at {self.peer_info.address}")
        return self.peer_info

    async def send(self, msg: Message):
        """Send an encrypted message."""
        if not self._cipher:
            raise ConnectionError("Handshake not completed")
        msg.signature = self.identity.sign(msg.signing_data())
        plaintext = msg.to_bytes()
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, plaintext, None)
        frame = nonce + ciphertext
        await self._send_raw(struct.pack("!I", len(frame)) + frame)

    async def recv(self) -> Message:
        """Receive and decrypt a message."""
        if not self._cipher:
            raise ConnectionError("Handshake not completed")
        frame_len_data = await self.reader.readexactly(4)
        frame_len = struct.unpack("!I", frame_len_data)[0]
        frame = await self.reader.readexactly(frame_len)
        nonce = frame[:12]
        ciphertext = frame[12:]
        plaintext = self._cipher.decrypt(nonce, ciphertext, None)
        # Strip the 4-byte length prefix from the inner message
        inner_len = struct.unpack("!I", plaintext[:4])[0]
        return Message.from_bytes(plaintext[4:4 + inner_len])

    async def close(self):
        self._connected = False
        if not self.writer.is_closing():
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass

    async def _send_raw(self, data: bytes):
        self.writer.write(data)
        await self.writer.drain()

    async def _recv_raw(self) -> bytes:
        len_data = await self.reader.readexactly(4)
        length = struct.unpack("!I", len_data)[0]
        return await self.reader.readexactly(length)

    def _peer_address(self) -> str:
        peername = self.writer.get_extra_info("peername")
        if peername:
            return f"{peername[0]}:{peername[1]}"
        return "unknown"


async def connect_to_peer(identity: NodeIdentity, host: str, port: int,
                          capability: float = 0, listen_port: int = 0) -> PeerConnection:
    """Initiate a connection to a peer."""
    reader, writer = await asyncio.open_connection(host, port)
    conn = PeerConnection(identity, reader, writer, is_initiator=True)
    await conn.handshake(capability, listen_port)
    return conn
