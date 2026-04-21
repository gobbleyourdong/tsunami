"""Mobile delivery gate — Expo/React Native + PWA variants.

The mobile vertical covers two shipping shapes:

  - **Native** (Expo / React Native): package.json has `expo` or
    `react-native` dep; main entry (App.tsx / App.js / index.js)
    exists; for Expo, app.json parses and declares a name.
  - **PWA** (installable web app): public/manifest.json parses with
    the required fields (name, short_name, icons, start_url,
    display); index.html exists and references the manifest via
    `<link rel="manifest">`.

Probe is offline — no emulator, no browser, no metro bundler. Just
file-level plausibility checks. Actual device execution is out of
scope (separate e2e harness).

Failure modes caught:
  - Neither Expo/RN deps nor PWA markers present
  - Dangling main entry (package.json `main` or conventional App.*
    points at a file that doesn't exist)
  - PWA manifest missing required fields or malformed
  - PWA manifest exists but index.html doesn't <link rel="manifest">
  - app.json claims a name but malformed / unparseable
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ._probe_common import result


_PWA_REQUIRED_FIELDS = ("name", "short_name", "icons", "start_url", "display")
_MANIFEST_LINK_RE = re.compile(
    r'<link[^>]+rel=["\']manifest["\']',
    re.IGNORECASE,
)


def _detect_variant(project_dir: Path, pkg: dict) -> str | None:
    """Native (expo | react-native) vs PWA vs None.

    Native takes precedence when both sets of markers exist, since a
    mobile app that also has a PWA shell (web fallback) is fundamentally
    the native app — the PWA is the fallback.
    """
    deps = {**(pkg.get("dependencies") or {}),
            **(pkg.get("devDependencies") or {})}
    if "expo" in deps:
        return "expo"
    if "react-native" in deps:
        return "react-native"

    # PWA: manifest.json without manifest_version (chrome-extension
    # has manifest_version=3) AND an index.html that links to it.
    pub_manifest = project_dir / "public" / "manifest.json"
    root_manifest = project_dir / "manifest.json"
    manifest_path = pub_manifest if pub_manifest.is_file() else (
        root_manifest if root_manifest.is_file() else None)
    if manifest_path is None:
        return None
    try:
        mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if mdata.get("manifest_version"):
        return None  # chrome-extension, not PWA
    if any(k in mdata for k in ("name", "short_name", "icons", "start_url")):
        return "pwa"
    return None


async def mobile_probe(
    project_dir: Path,
    task_text: str = "",
) -> dict:
    """Dispatch to the native or PWA sub-check based on fingerprint."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return result(False, f"project dir not found: {project_dir}")

    pkg_path = project_dir / "package.json"
    pkg: dict = {}
    if pkg_path.is_file():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return result(False, "package.json exists but is malformed JSON")

    variant = _detect_variant(project_dir, pkg)
    if variant is None:
        return result(
            False,
            "no mobile fingerprint — expected one of: "
            "expo or react-native in package.json deps, OR a valid "
            "PWA manifest.json (with name/short_name/icons/start_url) "
            "in public/ or project root.",
        )

    if variant in ("expo", "react-native"):
        return _check_native(project_dir, pkg, variant)
    if variant == "pwa":
        return _check_pwa(project_dir)
    return result(False, f"unknown mobile variant: {variant}")


def _check_native(project_dir: Path, pkg: dict, variant: str) -> dict:
    """Expo or bare RN: main entry resolves + (for Expo) app.json parses."""
    # Main entry — package.json "main" or conventional fallbacks.
    main_rel = pkg.get("main")
    candidates: list[Path] = []
    if isinstance(main_rel, str):
        candidates.append(project_dir / main_rel)
    # Conventional entries in priority order
    for rel in ("App.tsx", "App.jsx", "App.js", "index.js", "index.tsx",
                "src/App.tsx", "src/App.jsx", "src/App.js",
                "src/index.tsx", "src/index.js"):
        candidates.append(project_dir / rel)

    entry_hit = next((c for c in candidates if c.is_file()), None)
    if entry_hit is None:
        tried = ", ".join(str(c.relative_to(project_dir))
                          for c in candidates[:6])
        return result(
            False,
            f"{variant}: no main entry found. Checked package.json "
            f"`main` and conventional paths ({tried}, ...).",
        )

    if variant == "expo":
        app_json = project_dir / "app.json"
        app_config_js = project_dir / "app.config.js"
        app_config_ts = project_dir / "app.config.ts"
        if app_json.is_file():
            try:
                data = json.loads(app_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return result(False, "expo: app.json is malformed JSON")
            # Expo SDK expects `expo` key with at least `name`. Accept
            # either {"expo": {"name": ...}} or {"name": ...} (older).
            declared = (data.get("expo") or {}) if isinstance(data.get("expo"), dict) else data
            if not declared.get("name"):
                return result(
                    False,
                    "expo: app.json parsed but declares no `name` — "
                    "Expo CLI rejects apps without a name field.",
                )
        elif app_config_js.is_file() or app_config_ts.is_file():
            # Dynamic config — can't statically verify without running it;
            # treat presence as sufficient plausibility signal.
            pass
        else:
            return result(
                False,
                "expo: neither app.json nor app.config.{js,ts} found. "
                "Expo requires one for metadata/routing.",
            )

    return result(
        True,
        "",
        raw=f"variant={variant}\nentry={entry_hit.relative_to(project_dir)}",
    )


def _check_pwa(project_dir: Path) -> dict:
    """PWA: manifest required fields + index.html <link rel=manifest>."""
    pub_manifest = project_dir / "public" / "manifest.json"
    root_manifest = project_dir / "manifest.json"
    manifest_path = pub_manifest if pub_manifest.is_file() else root_manifest
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return result(False, f"pwa: manifest malformed or unreadable: {e}")

    missing = [f for f in _PWA_REQUIRED_FIELDS if not m.get(f)]
    if missing:
        return result(
            False,
            f"pwa: manifest missing required field(s): {', '.join(missing)}. "
            "Installable PWA requires name + short_name + icons + "
            "start_url + display.",
        )
    # icons must be a non-empty list
    icons = m.get("icons")
    if not isinstance(icons, list) or not icons:
        return result(False, "pwa: manifest.icons must be a non-empty array")

    # index.html must <link rel="manifest">. Common paths:
    candidates = [
        project_dir / "index.html",
        project_dir / "public" / "index.html",
        project_dir / "dist" / "index.html",
    ]
    idx = next((c for c in candidates if c.is_file()), None)
    if idx is None:
        return result(
            False,
            "pwa: manifest.json present but no index.html found "
            "(checked root, public/, dist/).",
        )
    try:
        html = idx.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return result(False, f"pwa: index.html unreadable: {e}")
    if not _MANIFEST_LINK_RE.search(html):
        return result(
            False,
            f"pwa: index.html ({idx.relative_to(project_dir)}) has no "
            "<link rel='manifest'> — browsers won't install the PWA.",
        )

    return result(
        True,
        "",
        raw=f"variant=pwa\nmanifest={manifest_path.relative_to(project_dir)}\n"
            f"index={idx.relative_to(project_dir)}",
    )


__all__ = ["mobile_probe", "_detect_variant"]
