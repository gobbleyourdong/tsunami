"""chrome-extension delivery gate — manifest v3 + bundle check.

No browser launch. The 80% of what breaks a Chrome extension at load
time is catchable statically: manifest_version drift, missing files
referenced by the manifest, v2-only fields that Chrome rejects, and
unbundled TS source (esbuild/vite didn't actually emit to dist/).

Run after `npm run build`. Points at `<project>/dist/` by default.
"""

from __future__ import annotations

from pathlib import Path
import json

from ._probe_common import result, skip

# Fields that manifest v2 used but v3 rejects. Chrome will refuse to
# load the extension if any of these appear — blocks delivery silently
# in vision-gate (the popup just never opens).
V2_ONLY_FIELDS = {
    "background.scripts",      # v3 uses background.service_worker
    "background.persistent",   # v3 service workers are non-persistent
    "browser_action",          # v3 merged into `action`
    "page_action",             # v3 merged into `action`
    "web_accessible_resources.<string>",  # v3 wants objects, not bare strings
}

REQUIRED_TOP_LEVEL = ("manifest_version", "name", "version")


def _nested_exists(obj: dict, dotted: str) -> bool:
    cur: object = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return False
        if part not in cur:
            return False
        cur = cur[part]
    return True


def _collect_file_refs(manifest: dict) -> list[str]:
    """Paths the manifest references. If any is missing in dist/, the
    extension won't load. Order: background, action popup, options,
    content_scripts.
    """
    refs: list[str] = []
    bg = manifest.get("background") or {}
    sw = bg.get("service_worker")
    if isinstance(sw, str):
        refs.append(sw)
    action = manifest.get("action") or {}
    popup = action.get("default_popup")
    if isinstance(popup, str):
        refs.append(popup)
    icon_block = action.get("default_icon")
    if isinstance(icon_block, dict):
        refs.extend(v for v in icon_block.values() if isinstance(v, str))
    elif isinstance(icon_block, str):
        refs.append(icon_block)
    options = manifest.get("options_page") or manifest.get("options_ui", {}).get("page")
    if isinstance(options, str):
        refs.append(options)
    for cs in manifest.get("content_scripts") or []:
        if not isinstance(cs, dict):
            continue
        refs.extend(p for p in (cs.get("js") or []) if isinstance(p, str))
        refs.extend(p for p in (cs.get("css") or []) if isinstance(p, str))
    icons = manifest.get("icons") or {}
    if isinstance(icons, dict):
        refs.extend(v for v in icons.values() if isinstance(v, str))
    return refs


async def extension_probe(project_dir: Path, dist_subdir: str = "dist") -> dict:
    """Static check of a built Chrome extension.

    Checks, in priority order:
      1. dist/manifest.json exists and is valid JSON
      2. manifest_version == 3
      3. Required top-level fields present (name, version)
      4. No v2-only fields
      5. Every file referenced by the manifest exists in dist/
      6. At least one entry bundle (background/popup/content) is
         non-empty — catches silent esbuild emit failures.
    """
    dist = Path(project_dir) / dist_subdir
    if not dist.is_dir():
        return result(False, f"{dist_subdir}/ missing — did `npm run build` fail?",
                      raw=f"expected {dist}")

    manifest_path = dist / "manifest.json"
    if not manifest_path.is_file():
        return result(False, "dist/manifest.json missing — extension won't load",
                      raw=f"expected {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return result(False, f"manifest.json is not valid JSON: {e}",
                      raw=manifest_path.read_text(encoding="utf-8", errors="replace")[:400])

    issues: list[str] = []

    mv = manifest.get("manifest_version")
    if mv != 3:
        issues.append(f"manifest_version must be 3, got {mv!r}")

    for field in REQUIRED_TOP_LEVEL:
        if field not in manifest:
            issues.append(f"missing required field '{field}'")

    for dotted in V2_ONLY_FIELDS:
        if "<" in dotted:
            # Special-case: web_accessible_resources must be objects in v3.
            war = manifest.get("web_accessible_resources")
            if isinstance(war, list) and any(isinstance(x, str) for x in war):
                issues.append("web_accessible_resources uses v2 bare-string form (v3 wants {resources, matches} objects)")
        elif _nested_exists(manifest, dotted):
            issues.append(f"v2-only field '{dotted}' present — v3 rejects this")

    file_refs = _collect_file_refs(manifest)
    missing_refs: list[str] = []
    empty_bundles: list[str] = []
    for ref in file_refs:
        target = dist / ref
        if not target.is_file():
            missing_refs.append(ref)
        elif ref.endswith((".js", ".mjs")) and target.stat().st_size < 32:
            empty_bundles.append(ref)
    if missing_refs:
        issues.append(f"manifest references missing files: {', '.join(missing_refs[:5])}")
    if empty_bundles:
        issues.append(f"bundle(s) suspiciously small (<32 B, likely empty esbuild emit): {', '.join(empty_bundles)}")

    if not file_refs:
        issues.append("manifest references zero files — no background/popup/content — dead extension")

    passed = not issues
    return result(
        passed,
        issues="; ".join(issues) if issues else "",
        raw=json.dumps({"manifest_version": mv, "refs": file_refs,
                        "missing": missing_refs, "empty": empty_bundles}),
    )


__all__ = ["extension_probe"]
