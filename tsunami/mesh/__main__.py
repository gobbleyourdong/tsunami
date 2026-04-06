"""MegaLAN CLI — the entry point.

Usage:
  megalan init                              # generate identity
  megalan start                             # start node
  megalan start --port 9999 --peers IP:PORT # custom port + initial peers
  megalan benchmark                         # run capability benchmark
  megalan deploy ./dist --name mystore      # deploy an app
  megalan status                            # show saved node state
  megalan peers                             # show known peers
  megalan names                             # show claimed names
  megalan credits                           # show credit summary
  megalan test                              # run 3-node local mesh test
"""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from .identity import NodeIdentity, IDENTITY_FILE
from .node import Node, NodeConfig
from .benchmark import run_benchmark
from .hosting import ContentStore
from .peers import load_peers
from .naming import NameRegistry
from .ledger import Ledger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("megalan")


def cmd_init(args):
    identity = NodeIdentity.load_or_generate()
    print(f"Node ID: {identity.node_id}")
    print(f"Identity saved to ~/.megalan/identity.json")


def cmd_benchmark(args):
    score = run_benchmark()
    print(f"Capability score: {score}")


def cmd_deploy(args):
    identity = NodeIdentity.load_or_generate()
    store = ContentStore()
    manifest = store.deploy(args.name, args.source, identity.node_id)
    print(f"Deployed '{args.name}'")
    print(f"  Files: {manifest.file_count}")
    print(f"  Size:  {manifest.total_size:,} bytes")
    print(f"  Hash:  {manifest.content_hash[:16]}...")
    print(f"\nStart node to serve: python -m megalan start")


def cmd_status(args):
    """Show saved state without starting a node."""
    if not IDENTITY_FILE.exists():
        print("No identity found. Run: megalan init")
        return

    identity = NodeIdentity.load()
    peers = load_peers()
    store = ContentStore()
    names = NameRegistry(identity.node_id)
    ledger = Ledger(identity.node_id)

    connected_peers = [p for p in peers.values()
                       if time.time() - p.last_seen < 300]

    print(f"\nMegaLAN Node Status")
    print(f"  ID:       {identity.node_id}")
    print(f"  Peers:    {len(connected_peers)} recent / {len(peers)} known")
    print(f"  Apps:     {len(store.list_apps())}")
    print(f"  Names:    {len(names.my_names())}")
    print(f"  Credits:  {ledger.balance:.2f}")
    summary = ledger.summary()
    print(f"  Earned:   {summary['total_earned']:.2f}")
    print(f"  Spent:    {summary['total_spent']:.2f}")
    print(f"  Jobs:     {summary['jobs_completed']} completed, {summary['jobs_disputed']} disputed")


def cmd_peers(args):
    """Show known peers."""
    peers = load_peers()
    if not peers:
        print("No known peers. Connect to one: megalan start --peers IP:PORT")
        return

    print(f"\nKnown Peers ({len(peers)})")
    print(f"{'Node ID':<14} {'Address':<22} {'Trust':>6} {'Cap':>6} {'Last Seen':>12}")
    print(f"{'-'*14} {'-'*22} {'-'*6} {'-'*6} {'-'*12}")

    now = time.time()
    for info in sorted(peers.values(), key=lambda p: -p.trust):
        age = now - info.last_seen
        if age < 60:
            seen = f"{age:.0f}s ago"
        elif age < 3600:
            seen = f"{age/60:.0f}m ago"
        elif age < 86400:
            seen = f"{age/3600:.0f}h ago"
        else:
            seen = f"{age/86400:.0f}d ago"

        print(f"{info.node_id[:12]}.. {info.address:<22} {info.trust:>6.3f} {info.capability:>6.0f} {seen:>12}")


def cmd_names(args):
    """Show claimed names."""
    if not IDENTITY_FILE.exists():
        print("No identity found. Run: megalan init")
        return

    identity = NodeIdentity.load()
    names = NameRegistry(identity.node_id)

    if not names.names:
        print("No names claimed. Deploy an app: megalan deploy ./dist --name myapp")
        return

    print(f"\nNames ({len(names.names)})")
    print(f"{'Name':<20} {'Owner':<14} {'Hash':<14} {'Status':>8}")
    print(f"{'-'*20} {'-'*14} {'-'*14} {'-'*8}")

    for record in names.names.values():
        owner = "you" if record.owner_id == identity.node_id else record.owner_id[:12] + ".."
        status = "expired" if record.is_expired() else "active"
        print(f"{record.name:<20} {owner:<14} {record.content_hash[:12]}.. {status:>8}")


def cmd_credits(args):
    """Show credit summary."""
    if not IDENTITY_FILE.exists():
        print("No identity found. Run: megalan init")
        return

    identity = NodeIdentity.load()
    ledger = Ledger(identity.node_id)
    s = ledger.summary()

    print(f"\nCredit Summary")
    print(f"  Balance:        {s['balance']:>10.2f}")
    print(f"  Total earned:   {s['total_earned']:>10.2f}")
    print(f"  Total spent:    {s['total_spent']:>10.2f}")
    print(f"  Jobs completed: {s['jobs_completed']:>10}")
    print(f"  Jobs disputed:  {s['jobs_disputed']:>10}")
    print(f"  Transactions:   {s['transactions']:>10}")


async def cmd_start(args):
    identity = NodeIdentity.load_or_generate()
    config = NodeConfig(port=args.port)
    node = Node(identity, config)
    await node.start()

    for peer_addr in (args.peers or []):
        await node.add_peer(peer_addr)

    status = node.status()
    print(f"\nMegaLAN node running")
    print(f"  ID:         {identity.node_id}")
    print(f"  Mesh port:  {config.port}")
    print(f"  HTTP port:  {config.port + 1}")
    print(f"  Capability: {node.capability}")
    print(f"  Peers:      {node.peer_count}")
    print(f"  Apps:       {status['apps_hosted']}")
    print(f"\n  Content: http://localhost:{config.port + 1}/<app-name>/")
    print(f"  API:     http://localhost:{config.port + 1}/api/status")
    print(f"\nPress Ctrl+C to stop\n")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await node.stop()


async def cmd_build(args):
    """Send a build prompt to the mesh. The dad-in-the-backyard flow."""
    identity = NodeIdentity.load_or_generate()
    config = NodeConfig(port=args.port)
    node = Node(identity, config)
    await node.start()

    # Connect to known peers
    for peer_addr in (args.peers or []):
        await node.add_peer(peer_addr)

    # Also reconnect saved peers
    await asyncio.sleep(2)

    if node.peer_count == 0:
        print("No peers connected. Building locally instead...")
        # Fall back to local Tsunami
        result = await node.executor.execute(
            job_id="local-" + str(int(time.time())),
            job_type="tsunami_agent",
            payload={"prompt": args.prompt},
        )
        if result.success and result.output_dir:
            name = args.name or "build-" + str(int(time.time()))
            url = await node.deploy(name, result.output_dir)
            print(f"\nBuilt and deployed: {url}")
        elif result.success:
            print(f"\nBuild completed ({result.duration_s:.1f}s)")
        else:
            print(f"\nBuild failed: {result.error}")
    else:
        print(f"Dispatching to mesh ({node.peer_count} peers)...")
        result = await node.request_build(args.prompt)
        if result:
            success = result.get("success", False)
            duration = result.get("duration_s", 0)
            if success:
                print(f"\nBuild completed by mesh ({duration:.1f}s)")
                if args.name and result.get("output_dir"):
                    url = await node.deploy(args.name, result["output_dir"])
                    print(f"Deployed: {url}")
            else:
                print(f"\nBuild failed: {result.get('error', 'unknown')}")
        else:
            print("\nNo response from mesh (timeout)")

    await node.stop()


def cmd_reset(args):
    """Reset MegaLAN state — remove all saved data except identity."""
    import shutil
    base = Path.home() / ".megalan"
    removed = []
    for name in ["peers.json", "ledger", "names", "content", "jobs"]:
        p = base / name
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            removed.append(name)
    if removed:
        print(f"Reset: removed {', '.join(removed)}")
    else:
        print("Nothing to reset")
    if args.identity:
        id_file = base / "identity.json"
        if id_file.exists():
            id_file.unlink()
            print("Identity removed — run 'megalan init' to generate a new one")


def cmd_test(args):
    from .test_mesh import test_local
    asyncio.run(test_local(args.nodes))


def main():
    parser = argparse.ArgumentParser(
        description="MegaLAN — decentralized compute mesh. Neighbor to neighbor.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Generate node identity")

    start_p = sub.add_parser("start", help="Start the node")
    start_p.add_argument("--port", type=int, default=9999, help="Mesh listen port")
    start_p.add_argument("--peers", nargs="*", help="Initial peers (ip:port)")

    sub.add_parser("benchmark", help="Run capability benchmark")

    deploy_p = sub.add_parser("deploy", help="Deploy an app to the mesh")
    deploy_p.add_argument("source", help="Source directory (e.g. ./dist)")
    deploy_p.add_argument("--name", required=True, help="Plaintext name for the app")

    build_p = sub.add_parser("build", help="Send a build prompt to the mesh")
    build_p.add_argument("prompt", help="What to build")
    build_p.add_argument("--name", default=None, help="Deploy with this name when done")
    build_p.add_argument("--port", type=int, default=9999, help="Local mesh port")
    build_p.add_argument("--peers", nargs="*", help="Peers to connect to")

    sub.add_parser("status", help="Show node state (offline)")
    sub.add_parser("peers", help="Show known peers (offline)")
    sub.add_parser("names", help="Show claimed names (offline)")
    sub.add_parser("credits", help="Show credit summary (offline)")

    reset_p = sub.add_parser("reset", help="Reset saved state (keeps identity)")
    reset_p.add_argument("--identity", action="store_true", help="Also remove identity keypair")

    test_p = sub.add_parser("test", help="Run local mesh test")
    test_p.add_argument("--nodes", type=int, default=3, help="Number of test nodes")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "benchmark": cmd_benchmark,
        "deploy": cmd_deploy,
        "status": cmd_status,
        "peers": cmd_peers,
        "names": cmd_names,
        "credits": cmd_credits,
        "reset": cmd_reset,
        "test": cmd_test,
    }

    if args.command == "start":
        asyncio.run(cmd_start(args))
    elif args.command == "build":
        asyncio.run(cmd_build(args))
    elif args.command in commands:
        commands[args.command](args)
    elif args.command is None:
        parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
