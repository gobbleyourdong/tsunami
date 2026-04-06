"""Integration tests — multi-node mesh operations.

Uses asyncio.run directly, no pytest-asyncio dependency.
"""

import asyncio
import os
import tempfile

from megalan.identity import NodeIdentity
from megalan.node import Node, NodeConfig


def _make_tmp_app():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "index.html"), "w") as f:
        f.write("<html><body><h1>Test</h1></body></html>")
    return d


def test_two_nodes_connect():
    async def _test():
        id_a = NodeIdentity.generate()
        node_a = Node(id_a, NodeConfig(port=9801))
        await node_a.start()

        id_b = NodeIdentity.generate()
        node_b = Node(id_b, NodeConfig(port=9803))
        await node_b.start()

        await node_b.connect("127.0.0.1", 9801)
        await asyncio.sleep(0.5)

        assert node_a.peer_count == 1
        assert node_b.peer_count == 1

        await node_a.stop()
        await node_b.stop()

    asyncio.run(_test())


def test_deploy_and_serve():
    async def _test():
        tmp_app = _make_tmp_app()
        id_a = NodeIdentity.generate()
        node_a = Node(id_a, NodeConfig(port=9801))
        await node_a.start()

        url = await node_a.deploy("test-deploy", tmp_app)
        assert url is not None

        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:9802/test-deploy/")
            assert r.status_code == 200
            assert "Test" in r.text

        await node_a.stop()

    asyncio.run(_test())


def test_name_witnessed():
    async def _test():
        tmp_app = _make_tmp_app()
        id_a = NodeIdentity.generate()
        node_a = Node(id_a, NodeConfig(port=9801))
        await node_a.start()

        id_b = NodeIdentity.generate()
        node_b = Node(id_b, NodeConfig(port=9803))
        await node_b.start()

        await node_b.connect("127.0.0.1", 9801)
        await asyncio.sleep(0.5)

        await node_a.deploy("witnessed", tmp_app)
        await asyncio.sleep(0.5)

        resolved = node_b.names.resolve("witnessed")
        assert resolved is not None
        assert resolved.owner_id == id_a.node_id

        await node_a.stop()
        await node_b.stop()

    asyncio.run(_test())


def test_content_replication():
    async def _test():
        tmp_app = _make_tmp_app()
        id_a = NodeIdentity.generate()
        node_a = Node(id_a, NodeConfig(port=9801))
        await node_a.start()

        id_b = NodeIdentity.generate()
        node_b = Node(id_b, NodeConfig(port=9803))
        await node_b.start()

        await node_b.connect("127.0.0.1", 9801)
        await asyncio.sleep(0.5)

        await node_a.deploy("repl-test", tmp_app)
        await asyncio.sleep(2)

        # B should have the content
        b_apps = [m.name for m in node_b.content.list_apps()]
        assert "repl-test" in b_apps

        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:9804/repl-test/")
            assert r.status_code == 200
            assert "Test" in r.text

        await node_a.stop()
        await node_b.stop()

    asyncio.run(_test())


def test_peer_address_listen_port():
    async def _test():
        id_a = NodeIdentity.generate()
        node_a = Node(id_a, NodeConfig(port=9801))
        await node_a.start()

        id_b = NodeIdentity.generate()
        node_b = Node(id_b, NodeConfig(port=9803))
        await node_b.start()

        await node_b.connect("127.0.0.1", 9801)
        await asyncio.sleep(0.5)

        b_info = node_a.peer_table.get(id_b.node_id)
        assert b_info is not None
        assert b_info.address.endswith(":9803")

        await node_a.stop()
        await node_b.stop()

    asyncio.run(_test())


def test_api_endpoints():
    async def _test():
        id_a = NodeIdentity.generate()
        node_a = Node(id_a, NodeConfig(port=9801))
        await node_a.start()

        import httpx
        async with httpx.AsyncClient() as client:
            for endpoint in ["/api/status", "/api/apps", "/api/peers", "/api/ledger", "/api/names"]:
                r = await client.get(f"http://localhost:9802{endpoint}")
                assert r.status_code == 200, f"{endpoint} returned {r.status_code}"

        await node_a.stop()

    asyncio.run(_test())
