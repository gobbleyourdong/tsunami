# MegaLAN

Decentralized compute mesh. Neighbor to neighbor.

## Quick Start

```bash
# Generate identity
python -m megalan init

# Start your node
python -m megalan start

# Deploy an app
python -m megalan deploy ./dist --name mystore

# Check status
python -m megalan status
```

## What It Does

Your laptop is a node. Your neighbor's laptop is a node. Connect them.
Deploy a Tsunami app on yours. Your neighbor serves it too. No cloud.
No server. No subscription. Just IPs and pipes.

## Architecture

```
Layer 0: Identity    — Ed25519 + X25519 keypair per node
Layer 1: Discovery   — mDNS (zero-config LAN) + manual IP + gossip
Layer 2: Connection  — encrypted TCP (XChaCha20-Poly1305)
Layer 3: Trust       — local scoring, decays with hop distance
Layer 4: Compute     — job dispatch, timecards, credit ledger
Layer 5: Naming      — plaintext names, no registrar, no .com
Layer 6: Hosting     — deploy static apps, HTTP server, content replication
Layer 7: Frontend    — PWA dashboard served by the mesh itself
```

## CLI

```
megalan init          Generate node identity (~/.megalan/)
megalan start         Start the node (mesh + HTTP server)
megalan benchmark     Score hardware capability
megalan deploy        Deploy an app directory with a name
megalan build         Send a build prompt to the mesh
megalan status        Show node state (works offline)
megalan peers         Show known peers (works offline)
megalan names         Show claimed/known names
megalan credits       Show credit balance
megalan reset         Clear saved state (keeps identity)
megalan test          Run local multi-node mesh test
```

## How Credits Work

- Run your node → accept compute jobs → earn credits
- Credits = (job_duration) x (your_capability) x (job_type_multiplier)
- Spend credits to claim names or request builds from the mesh
- No money. Compute is the currency.

## How Names Work

- Claim a plaintext name: `megalan deploy ./dist --name cards`
- Cost: 10-500 credits depending on length (short = premium)
- Names expire after 30 days of inactivity
- Transfer to anyone: owner signs, new owner claims. Payment (BTC, cash, beer) is between you.
- The protocol never touches money. It just sees a signed transfer.

## How Replication Works

- Deploy on your node → automatically offered to connected peers
- Peers accept → receive content chunks → serve it on their HTTP port
- Your neighbor can serve your app. The mesh IS the CDN.

## Testing

```bash
# Unit tests (28 tests, <1 second)
python -m pytest megalan/tests/ -v

# Local mesh test (3 nodes, full stack)
python -m megalan test

# Cross-network test
# Machine A: python -m megalan.test_mesh listen --port 9999
# Machine B: python -m megalan.test_mesh connect --peer A_IP:9999
```

## What This Does NOT Need

- Blockchain
- Mining
- Proof of stake
- Tokens / ICO
- Central servers
- Domain registrars
- SSL certificates
- Cloud infrastructure
- Money

## Files

```
megalan/
  identity.py       Ed25519/X25519 keypair generation + persistence
  protocol.py       21 message types, wire serialization
  peer.py           Encrypted peer connection + handshake
  peers.py          Peer persistence + reconnect logic
  node.py           Full mesh node runtime
  ledger.py         Credit tracking with timecards
  naming.py         Plaintext name registry
  hosting.py        Content store + HTTP server
  discovery.py      mDNS/zeroconf local peer discovery
  executor.py       Tsunami/inference job execution
  replication.py    Content replication between peers
  benchmark.py      Hardware capability scoring
  test_mesh.py      Cross-network test harness
  __main__.py       CLI entry point
  dashboard/        PWA frontend (served by the mesh)
```
