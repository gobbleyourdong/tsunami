"""Canary — scaffolds/mobile/chat (PWA)."""
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "mobile" / "chat"


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "main.tsx",
        "README.md",
        "public/manifest.json",
        "src/App.tsx",
        "src/index.css",
        "src/sw.ts",
        "src/lib/sw-register.ts",
        "src/lib/chat-store.ts",
        "src/components/MessageList.tsx",
        "src/components/Composer.tsx",
        "src/components/OfflineBanner.tsx",
        "src/components/index.ts",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_manifest_shape() -> None:
    manifest = json.loads((SCAFFOLD / "public" / "manifest.json").read_text())
    for key in ("name", "short_name", "start_url", "display", "theme_color", "icons"):
        assert key in manifest, f"manifest missing {key}"
    assert manifest["display"] in ("standalone", "fullscreen", "minimal-ui")
    assert isinstance(manifest["icons"], list) and len(manifest["icons"]) >= 2
    sizes = {i.get("sizes") for i in manifest["icons"]}
    assert "192x192" in sizes and "512x512" in sizes, "need both PWA icon sizes"


def test_index_html_links_manifest_and_viewport() -> None:
    html = (SCAFFOLD / "index.html").read_text()
    assert 'rel="manifest"' in html, "index.html must link the manifest"
    assert 'viewport' in html and 'width=device-width' in html
    assert 'apple-mobile-web-app-capable' in html, "iOS PWA meta needed"


def test_service_worker_caches_static_and_network_firsts_rest() -> None:
    sw = (SCAFFOLD / "src" / "sw.ts").read_text()
    assert "CACHE_VERSION" in sw
    assert "install" in sw and "activate" in sw and "fetch" in sw
    assert "/manifest.json" in sw, "SW static list should include manifest"
    # Rough network-first check: fetch(req) appears before a cache fallback
    assert "fetch(req).catch" in sw, "non-static GETs should try network first"


def test_sw_register_after_load() -> None:
    reg = (SCAFFOLD / "src" / "lib" / "sw-register.ts").read_text()
    assert "addEventListener(\"load\"" in reg, (
        "SW registration should happen after page load to avoid competing with first-paint"
    )
    assert "serviceWorker" in reg


def test_chat_store_message_shape() -> None:
    store = (SCAFFOLD / "src" / "lib" / "chat-store.ts").read_text()
    for field in ("id:", "body:", "sender:", "sent_at:"):
        assert field in store, f"Message type should declare {field}"


def test_components_barrel() -> None:
    barrel = (SCAFFOLD / "src" / "components" / "index.ts").read_text()
    for name in ("MessageList", "Composer", "OfflineBanner"):
        assert re.search(rf"\b{name}\b", barrel)


def test_safe_area_insets_used() -> None:
    """iOS notch/home-indicator should be respected via env(safe-area-inset-*)."""
    css = (SCAFFOLD / "src" / "index.css").read_text()
    assert "env(safe-area-inset-" in css, "mobile scaffold must use safe-area insets"


def test_tsconfig_includes_webworker_lib() -> None:
    """Service worker code needs the WebWorker lib typings."""
    tsc = json.loads((SCAFFOLD / "tsconfig.json").read_text())
    assert "WebWorker" in tsc["compilerOptions"]["lib"], (
        "tsconfig.lib must include WebWorker for src/sw.ts to typecheck"
    )
