"""Layer 1: Discovery — find neighbors on the local network.

mDNS/DNS-SD via zeroconf. Zero config. Your laptop finds your
roommate's laptop automatically.

Service: _megalan._tcp.local.
TXT: node_id, port, capability
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass

log = logging.getLogger("megalan.discovery")

MDNS_SERVICE_TYPE = "_megalan._tcp.local."


@dataclass
class DiscoveredPeer:
    node_id: str
    host: str
    port: int
    capability: float
    discovered_at: float


class LocalDiscovery:
    """mDNS-based local network peer discovery."""

    def __init__(self, node_id: str, port: int, capability: float = 0):
        self.node_id = node_id
        self.port = port
        self.capability = capability
        self._zeroconf = None
        self._browser = None
        self._registration = None
        self.discovered: dict[str, DiscoveredPeer] = {}
        self._on_found: list[callable] = []

    def on_peer_found(self, callback):
        """Register a callback for when a new peer is discovered."""
        self._on_found.append(callback)

    async def start(self):
        """Start advertising this node and browsing for peers."""
        try:
            from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser
        except ImportError:
            log.warning("zeroconf not installed — mDNS discovery disabled. "
                        "pip install zeroconf to enable.")
            return

        self._zeroconf = Zeroconf()

        # Get local IP
        local_ip = _get_local_ip()

        # Register our service
        info = ServiceInfo(
            MDNS_SERVICE_TYPE,
            f"megalan-{self.node_id[:12]}.{MDNS_SERVICE_TYPE}",
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties={
                "node_id": self.node_id,
                "capability": str(self.capability),
            },
        )
        self._registration = info
        self._zeroconf.register_service(info)
        log.info(f"mDNS: advertising on {local_ip}:{self.port}")

        # Browse for peers
        self._browser = ServiceBrowser(
            self._zeroconf,
            MDNS_SERVICE_TYPE,
            handlers=[self._on_service_change],
        )
        log.info("mDNS: browsing for local peers...")

    async def stop(self):
        if self._zeroconf:
            if self._registration:
                self._zeroconf.unregister_service(self._registration)
            self._zeroconf.close()
            log.info("mDNS: stopped")

    def _on_service_change(self, zeroconf, service_type, name, state_change):
        from zeroconf import ServiceStateChange

        if state_change == ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if not info:
                return

            props = {k.decode(): v.decode() for k, v in info.properties.items()}
            peer_node_id = props.get("node_id", "")

            if peer_node_id == self.node_id:
                return  # that's us

            if peer_node_id in self.discovered:
                return  # already known

            addresses = info.parsed_addresses()
            if not addresses:
                return

            peer = DiscoveredPeer(
                node_id=peer_node_id,
                host=addresses[0],
                port=info.port,
                capability=float(props.get("capability", "0")),
                discovered_at=time.time(),
            )
            self.discovered[peer_node_id] = peer
            log.info(f"mDNS: found peer {peer_node_id[:12]}... at {peer.host}:{peer.port}")

            for cb in self._on_found:
                try:
                    cb(peer)
                except Exception as e:
                    log.error(f"Discovery callback error: {e}")

        elif state_change == ServiceStateChange.Removed:
            # Try to find which peer this was
            info = zeroconf.get_service_info(service_type, name)
            if info:
                props = {k.decode(): v.decode() for k, v in info.properties.items()}
                peer_node_id = props.get("node_id", "")
                if peer_node_id in self.discovered:
                    del self.discovered[peer_node_id]
                    log.info(f"mDNS: peer {peer_node_id[:12]}... left")


def _get_local_ip() -> str:
    """Get the local IP address (not 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
