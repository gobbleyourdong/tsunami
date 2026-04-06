#!/usr/bin/env python3
"""MegaLAN mesh test — proves the full stack on real or local hardware.

Usage:
  # Local test (two nodes on same machine)
  python -m megalan.test_mesh local

  # Cross-network test (Spark ↔ Vast.ai)
  # On machine A (listener):
  python -m megalan.test_mesh listen --port 9999

  # On machine B (connector):
  python -m megalan.test_mesh connect --peer 154.54.102.13:9999

  # Full proving ground (3+ nodes)
  python -m megalan.test_mesh local --nodes 4
"""

import argparse
import asyncio
import json
import logging
import time

import httpx

from .identity import NodeIdentity
from .node import Node, NodeConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("megalan.test")


async def test_local(num_nodes: int = 3):
    """Spin up N nodes on localhost, connect them, test everything."""
    print(f"\n{'='*60}")
    print(f"  MegaLAN Local Mesh Test — {num_nodes} nodes")
    print(f"{'='*60}\n")

    nodes: list[Node] = []
    base_port = 9900

    # Start all nodes
    for i in range(num_nodes):
        identity = NodeIdentity.generate()
        port = base_port + (i * 2)  # mesh port, HTTP port is +1
        node = Node(identity, NodeConfig(port=port))
        await node.start()
        nodes.append(node)
        print(f"  Node {i}: {identity.node_id[:12]}... on :{port}/:{port+1}")

    # Connect in a chain: 0←1, 1←2, 2←3, etc.
    for i in range(1, num_nodes):
        prev_port = base_port + ((i - 1) * 2)
        await nodes[i].connect("127.0.0.1", prev_port)
    await asyncio.sleep(1)

    # Also connect last to first (ring topology)
    if num_nodes > 2:
        await nodes[0].connect("127.0.0.1", base_port + ((num_nodes - 1) * 2))
        await asyncio.sleep(0.5)

    print(f"\n--- Peer Connectivity ---")
    for i, node in enumerate(nodes):
        peers = node.peer_count
        known = len(node.peer_table)
        print(f"  Node {i}: {peers} connected, {known} known")

    # Test 1: Deploy content on node 0
    print(f"\n--- Test 1: Deploy + Serve ---")
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        index = os.path.join(tmpdir, "index.html")
        with open(index, "w") as f:
            f.write("<html><body><h1>MegaLAN Test</h1><p>Served from the mesh</p></body></html>")

        import random, string
        test_name = "test-" + "".join(random.choices(string.ascii_lowercase, k=6))
        url = await nodes[0].deploy(test_name, tmpdir)
        print(f"  Deployed: {url}")

        http_port = base_port + 1
        async with httpx.AsyncClient() as client:
            r = await client.get(f"http://localhost:{http_port}/mesh-test/")
            status = "PASS" if r.status_code == 200 else "FAIL"
            print(f"  HTTP fetch: {status} ({r.status_code})")

    # Test 2: Name resolution across peers
    print(f"\n--- Test 2: Name Witnessed ---")
    for i, node in enumerate(nodes):
        resolved = node.names.resolve(test_name)
        status = "PASS" if resolved else "FAIL"
        owner = resolved.owner_id[:12] if resolved else "none"
        print(f"  Node {i} resolves 'mesh-test': {status} (owner={owner}...)")

    # Test 3: Peer gossip — node 0 asks node 1 for peers
    print(f"\n--- Test 3: Gossip Discovery ---")
    from .protocol import peers_near_me_msg
    msg = peers_near_me_msg(nodes[0].identity.node_id)
    for nid, conn in nodes[0].peers.items():
        if conn.connected:
            await conn.send(msg)
    await asyncio.sleep(0.5)
    print(f"  Node 0 knows {len(nodes[0].peer_table)} peers after gossip")

    # Test 4: Status API
    print(f"\n--- Test 4: HTTP API ---")
    async with httpx.AsyncClient() as client:
        for i, node in enumerate(nodes):
            port = base_port + (i * 2) + 1
            r = await client.get(f"http://localhost:{port}/api/status")
            if r.status_code == 200:
                s = r.json()
                print(f"  Node {i}: cap={s['capability']:.0f} peers={s['peers_connected']} apps={s['apps_hosted']}")

    # Test 5: Credit ledger
    print(f"\n--- Test 5: Ledger ---")
    for i, node in enumerate(nodes):
        summary = node.ledger.summary()
        print(f"  Node {i}: balance={summary['balance']:.2f} jobs={summary['jobs_completed']}")

    # Cleanup
    print(f"\n--- Shutdown ---")
    for node in nodes:
        await node.stop()

    print(f"\n{'='*60}")
    print(f"  All tests complete. {num_nodes} nodes in mesh.")
    print(f"{'='*60}\n")


async def test_listen(port: int):
    """Start a node and wait for incoming connections (machine A)."""
    identity = NodeIdentity.load_or_generate()
    node = Node(identity, NodeConfig(port=port))
    await node.start()

    print(f"\n{'='*60}")
    print(f"  MegaLAN Listener")
    print(f"  Node ID: {identity.node_id}")
    print(f"  Mesh:    0.0.0.0:{port}")
    print(f"  HTTP:    0.0.0.0:{port + 1}")
    print(f"  Cap:     {node.capability}")
    print(f"{'='*60}")
    print(f"\n  Waiting for connections...")
    print(f"  On the other machine run:")
    print(f"    python -m megalan.test_mesh connect --peer YOUR_IP:{port}")
    print(f"\n  Press Ctrl+C to stop\n")

    try:
        prev_peers = 0
        while True:
            await asyncio.sleep(5)
            if node.peer_count != prev_peers:
                prev_peers = node.peer_count
                print(f"  Peers: {node.peer_count} | Known: {len(node.peer_table)} | Credits: {node.credits:.2f}")
    except KeyboardInterrupt:
        print("\nShutting down...")
        await node.stop()


async def test_connect(peer_addr: str, port: int):
    """Connect to a remote node and run tests (machine B)."""
    identity = NodeIdentity.load_or_generate()
    node = Node(identity, NodeConfig(port=port))
    await node.start()

    print(f"\n  Connecting to {peer_addr}...")
    await node.add_peer(peer_addr)
    await asyncio.sleep(2)

    if node.peer_count == 0:
        print(f"  FAIL: Could not connect to {peer_addr}")
        print(f"  Check: firewall, port forwarding, IP address")
        await node.stop()
        return

    print(f"  Connected! Peers: {node.peer_count}")

    # Deploy a test app
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "index.html"), "w") as f:
            f.write(f"<html><body><h1>Hello from {identity.node_id[:12]}</h1>"
                    f"<p>Cross-network MegaLAN test</p></body></html>")

        url = await node.deploy("cross-test", tmpdir)
        print(f"  Deployed: {url}")

    # Verify local HTTP
    async with httpx.AsyncClient() as client:
        r = await client.get(f"http://localhost:{port + 1}/cross-test/")
        print(f"  Local HTTP: {'PASS' if r.status_code == 200 else 'FAIL'}")

        r = await client.get(f"http://localhost:{port + 1}/api/status")
        if r.status_code == 200:
            s = r.json()
            print(f"  Status: cap={s['capability']:.0f} peers={s['peers_connected']}")

    print(f"\n  Cross-network connection verified!")
    print(f"  Press Ctrl+C to stop\n")

    try:
        while True:
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        await node.stop()


def main():
    parser = argparse.ArgumentParser(description="MegaLAN mesh test")
    sub = parser.add_subparsers(dest="mode")

    local_p = sub.add_parser("local", help="Local test with N nodes")
    local_p.add_argument("--nodes", type=int, default=3, help="Number of nodes")

    listen_p = sub.add_parser("listen", help="Listen for cross-network test")
    listen_p.add_argument("--port", type=int, default=9999)

    connect_p = sub.add_parser("connect", help="Connect to remote node")
    connect_p.add_argument("--peer", required=True, help="Remote address (ip:port)")
    connect_p.add_argument("--port", type=int, default=9997, help="Local port")

    args = parser.parse_args()

    if args.mode == "local":
        asyncio.run(test_local(args.nodes))
    elif args.mode == "listen":
        asyncio.run(test_listen(args.port))
    elif args.mode == "connect":
        asyncio.run(test_connect(args.peer, args.port))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
