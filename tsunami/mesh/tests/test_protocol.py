"""Tests for wire protocol."""

from megalan.protocol import (
    Message, MessageType,
    hello_msg, ping_msg, pong_msg, job_offer_msg, claim_name_msg,
    transfer_name_msg, resolve_msg,
)


def test_message_roundtrip():
    msg = ping_msg("abc123", 42.5)
    data = msg.to_bytes()
    # Strip 4-byte length prefix
    import struct
    length = struct.unpack("!I", data[:4])[0]
    restored = Message.from_bytes(data[4:4 + length])
    assert restored.type == MessageType.PING
    assert restored.sender == "abc123"
    assert restored.payload["credit_balance"] == 42.5


def test_hello_msg():
    msg = hello_msg("node1", "pubkey_hex", "exchange_hex", 50.0, 9999)
    assert msg.type == MessageType.HELLO
    assert msg.payload["listen_port"] == 9999
    assert msg.payload["capability"] == 50.0


def test_signing_data_deterministic():
    msg = ping_msg("test", 10.0)
    assert msg.signing_data() == msg.signing_data()


def test_job_offer_msg():
    msg = job_offer_msg("node1", "job123", "tsunami_agent",
                        {"prompt": "build a counter"}, {"min_capability": 10},
                        100, 300)
    assert msg.type == MessageType.JOB_OFFER
    assert msg.payload["job_id"] == "job123"
    assert msg.payload["offered_credits"] == 100


def test_claim_name_msg():
    msg = claim_name_msg("node1", "mystore", "hash123")
    assert msg.type == MessageType.CLAIM_NAME
    assert msg.payload["name"] == "mystore"


def test_transfer_name_msg():
    msg = transfer_name_msg("owner1", "mystore", "new_owner")
    assert msg.type == MessageType.TRANSFER_NAME
    assert msg.payload["new_owner_id"] == "new_owner"


def test_all_message_types_exist():
    expected = [
        "HELLO", "PEERS_NEAR_ME", "PEERS_LIST",
        "PING", "PONG",
        "VOUCH",
        "JOB_OFFER", "JOB_ACCEPT", "CLOCK_IN", "CLOCK_OUT",
        "RESULT", "VERIFY", "CREDIT_TX",
        "CLAIM_NAME", "TRANSFER_NAME", "RESOLVE", "RESOLVE_RESPONSE",
        "FETCH", "CHUNK",
        "REPLICATE_OFFER", "REPLICATE_ACCEPT", "REPLICATE_DATA",
    ]
    for name in expected:
        assert hasattr(MessageType, name), f"Missing MessageType.{name}"
