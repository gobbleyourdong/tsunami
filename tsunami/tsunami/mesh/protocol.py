"""Wire protocol — message types and serialization.

Every message is: 4-byte length prefix + JSON payload.
Encrypted after handshake via XChaCha20-Poly1305.
"""

from __future__ import annotations

import json
import os
import struct
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    # Layer 1: Discovery
    HELLO = "HELLO"
    PEERS_NEAR_ME = "PEERS_NEAR_ME"
    PEERS_LIST = "PEERS_LIST"

    # Layer 2: Connection
    PING = "PING"
    PONG = "PONG"

    # Layer 3: Trust
    VOUCH = "VOUCH"

    # Layer 4: Compute
    JOB_OFFER = "JOB_OFFER"
    JOB_ACCEPT = "JOB_ACCEPT"
    CLOCK_IN = "CLOCK_IN"
    CLOCK_OUT = "CLOCK_OUT"
    RESULT = "RESULT"
    VERIFY = "VERIFY"
    CREDIT_TX = "CREDIT_TX"

    # Layer 5: Naming
    CLAIM_NAME = "CLAIM_NAME"
    TRANSFER_NAME = "TRANSFER_NAME"
    RESOLVE = "RESOLVE"
    RESOLVE_RESPONSE = "RESOLVE_RESPONSE"

    # Layer 6: Content
    FETCH = "FETCH"
    CHUNK = "CHUNK"
    REPLICATE_OFFER = "REPLICATE_OFFER"
    REPLICATE_ACCEPT = "REPLICATE_ACCEPT"
    REPLICATE_DATA = "REPLICATE_DATA"


@dataclass
class Message:
    type: MessageType
    sender: str  # node_id
    timestamp: float = field(default_factory=time.time)
    nonce: str = field(default_factory=lambda: os.urandom(8).hex())
    payload: dict[str, Any] = field(default_factory=dict)
    signature: bytes = b""  # Ed25519 signature of (type + sender + timestamp + nonce + payload)

    def signing_data(self) -> bytes:
        """Data that gets signed — deterministic serialization."""
        canonical = json.dumps(
            {"type": self.type, "sender": self.sender,
             "timestamp": self.timestamp, "nonce": self.nonce,
             "payload": self.payload},
            sort_keys=True, separators=(",", ":"),
        )
        return canonical.encode()

    def to_bytes(self) -> bytes:
        data = {
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "sender": self.sender,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "payload": self.payload,
            "signature": self.signature.hex(),
        }
        encoded = json.dumps(data, separators=(",", ":")).encode()
        return struct.pack("!I", len(encoded)) + encoded

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        parsed = json.loads(data)
        return cls(
            type=MessageType(parsed["type"]),
            sender=parsed["sender"],
            timestamp=parsed["timestamp"],
            nonce=parsed["nonce"],
            payload=parsed.get("payload", {}),
            signature=bytes.fromhex(parsed.get("signature", "")),
        )


# --- Convenience constructors ---

def hello_msg(node_id: str, pubkey_hex: str, exchange_pubkey_hex: str,
              capability: float = 0, listen_port: int = 0) -> Message:
    return Message(
        type=MessageType.HELLO,
        sender=node_id,
        payload={
            "pubkey": pubkey_hex,
            "exchange_pubkey": exchange_pubkey_hex,
            "capability": capability,
            "listen_port": listen_port,
        },
    )


def ping_msg(node_id: str, credit_balance: float = 0) -> Message:
    return Message(
        type=MessageType.PING,
        sender=node_id,
        payload={"credit_balance": credit_balance},
    )


def pong_msg(node_id: str, credit_balance: float = 0) -> Message:
    return Message(
        type=MessageType.PONG,
        sender=node_id,
        payload={"credit_balance": credit_balance},
    )


def peers_near_me_msg(node_id: str, lat: float = 0, lon: float = 0,
                      radius_km: float = 50) -> Message:
    return Message(
        type=MessageType.PEERS_NEAR_ME,
        sender=node_id,
        payload={"lat": lat, "lon": lon, "radius_km": radius_km},
    )


def peers_list_msg(node_id: str, peers: list[dict]) -> Message:
    return Message(
        type=MessageType.PEERS_LIST,
        sender=node_id,
        payload={"peers": peers},
    )


def job_offer_msg(node_id: str, job_id: str, job_type: str,
                  payload: dict, requirements: dict,
                  offered_credits: float, timeout_s: int = 300) -> Message:
    return Message(
        type=MessageType.JOB_OFFER,
        sender=node_id,
        payload={
            "job_id": job_id,
            "job_type": job_type,
            "job_payload": payload,
            "requirements": requirements,
            "offered_credits": offered_credits,
            "timeout_s": timeout_s,
        },
    )


def job_accept_msg(node_id: str, job_id: str) -> Message:
    return Message(
        type=MessageType.JOB_ACCEPT,
        sender=node_id,
        payload={"job_id": job_id},
    )


def clock_in_msg(node_id: str, job_id: str) -> Message:
    return Message(
        type=MessageType.CLOCK_IN,
        sender=node_id,
        payload={"job_id": job_id},
    )


def clock_out_msg(node_id: str, job_id: str, result_hash: str) -> Message:
    return Message(
        type=MessageType.CLOCK_OUT,
        sender=node_id,
        payload={"job_id": job_id, "result_hash": result_hash},
    )


def result_msg(node_id: str, job_id: str, data: Any) -> Message:
    return Message(
        type=MessageType.RESULT,
        sender=node_id,
        payload={"job_id": job_id, "data": data},
    )


def verify_msg(node_id: str, job_id: str, ok: bool, reason: str = "") -> Message:
    return Message(
        type=MessageType.VERIFY,
        sender=node_id,
        payload={"job_id": job_id, "ok": ok, "reason": reason},
    )


def credit_tx_msg(node_id: str, job_id: str, worker_id: str,
                  amount: float) -> Message:
    return Message(
        type=MessageType.CREDIT_TX,
        sender=node_id,
        payload={"job_id": job_id, "worker_id": worker_id, "amount": amount},
    )


def claim_name_msg(node_id: str, name: str, content_hash: str) -> Message:
    return Message(
        type=MessageType.CLAIM_NAME,
        sender=node_id,
        payload={"name": name, "content_hash": content_hash},
    )


def resolve_msg(node_id: str, name: str) -> Message:
    return Message(
        type=MessageType.RESOLVE,
        sender=node_id,
        payload={"name": name},
    )


def transfer_name_msg(node_id: str, name: str, new_owner_id: str) -> Message:
    return Message(
        type=MessageType.TRANSFER_NAME,
        sender=node_id,
        payload={"name": name, "new_owner_id": new_owner_id},
    )


def resolve_response_msg(node_id: str, name: str, owner_id: str,
                         address: str, content_hash: str) -> Message:
    return Message(
        type=MessageType.RESOLVE_RESPONSE,
        sender=node_id,
        payload={
            "name": name,
            "owner_id": owner_id,
            "address": address,
            "content_hash": content_hash,
        },
    )
