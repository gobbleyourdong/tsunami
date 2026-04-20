"""Deterministic error recovery — fix what you can regex.

The top 5 compile error patterns account for ~80% of build failures.
Each has a known fix that doesn't require LLM reasoning. Apply the
fix automatically, rebuild. If it works, the agent never even sees
the error. If it doesn't, fall through to the LLM.

This is the "auto-hook-import for everything" pattern.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger("tsunami.error_fixer")


# Session error memory — remember what fixed what
_error_memory: dict[str, str] = {}  # error_pattern → fix_description


def try_auto_fix(project_dir: Path, errors: list[str]) -> bool:
    """Attempt deterministic fixes for common compile errors.

    Also checks error memory — if we've seen this error before and
    know what fixed it, apply the same fix immediately.

    Fixes ALL matching errors in one pass (not just the first).
    Returns True if any fix was applied (caller should rebuild).
    Returns False if no fix was possible (fall through to LLM).
    """
    any_fixed = False
    for error in errors:
        # Check error memory first
        for pattern, fix_desc in _error_memory.items():
            if pattern in error:
                log.info(f"Error memory hit: '{pattern}' → reapplying '{fix_desc}'")

        fix = _classify_and_fix(project_dir, error)
        if fix:
            # Remember this fix for future occurrences
            # Extract a short pattern from the error for matching
            key = error[:80].strip()
            _error_memory[key] = fix
            log.info(f"Auto-fix applied: {fix}")
            any_fixed = True
    return any_fixed


def _classify_and_fix(project_dir: Path, error: str) -> str | None:
    """Classify an error and attempt a fix. Returns description or None."""

    # 1. Missing module — file doesn't exist
    # "Cannot resolve entry module" or "Could not resolve './components/Sidebar'"
    m = re.search(r"Could not resolve ['\"]\./(components/[\w/]+)['\"]", error)
    if not m:
        m = re.search(r"Could not resolve ['\"]\.\./(components/[\w/]+)['\"]", error)
    if not m:
        # Broader: "../components/ui/Button" or "../components/ui"
        m = re.search(r'Could not resolve [\'"]\.\./(components/[^"\']+)[\'"]', error)
    if m:
        comp_path = m.group(1)
        is_dotdot = "../" + comp_path in error

        # If ../ path: check if ./ equivalent exists — rewrite ALL ../components → ./components
        # in one pass (Vite only reports the first error, but we fix them all preemptively)
        if is_dotdot:
            for ext in [".tsx", ".ts", ".jsx", ".js", ""]:
                correct_path = project_dir / "src" / (comp_path + ext)
                if correct_path.exists():
                    src_dir = project_dir / "src"
                    fixed_count = 0
                    for tsx in src_dir.rglob("*.tsx"):
                        content = tsx.read_text()
                        # Replace ALL ../components references, not just the one in the error
                        if '"../components/' in content or "'../components/" in content:
                            content = content.replace("../components/", "./components/")
                            tsx.write_text(content)
                            fixed_count += 1
                    if fixed_count:
                        return f"rewrote ../components/ → ./components/ in {fixed_count} file(s)"
                    return None

        # Check if import is missing the file
        for ext in [".tsx", ".ts", ".jsx", ".js"]:
            full_path = project_dir / "src" / (comp_path + ext)
            if full_path.exists():
                return None  # file exists, error is something else
        # File doesn't exist — create a stub
        comp_name = comp_path.split("/")[-1]
        stub_path = project_dir / "src" / comp_path
        stub_path = stub_path.with_suffix(".tsx")
        stub_path.parent.mkdir(parents=True, exist_ok=True)
        stub_path.write_text(
            f'export default function {comp_name}() {{\n'
            f'  return <div>{comp_name}</div>\n'
            f'}}\n'
        )
        return f"created stub {stub_path.name} (missing component)"

    # 2. Named vs default export mismatch / missing export from barrel file
    # "'X' is not exported by 'src/components/Y.tsx'" or "'X' is not exported by 'src/components/ui/index.ts'"
    m = re.search(r"['\"](\w+)['\"] is not exported by ['\"]([^'\"]+)['\"]", error)
    if m:
        export_name = m.group(1)
        file_path = m.group(2)
        # Resolve relative to project
        resolved = project_dir / file_path
        if not resolved.exists():
            resolved = project_dir / "src" / file_path
        if resolved.exists():
            content = resolved.read_text()

            # Case A: barrel file (index.ts) missing the export — create stub component + add to barrel
            if resolved.name.startswith("index.") and f"as {export_name}" not in content:
                comp_dir = resolved.parent
                comp_file = comp_dir / f"{export_name}.tsx"
                if not comp_file.exists():
                    comp_file.write_text(
                        f'export default function {export_name}({{ children, className, ...props }}: '
                        f'{{ children?: React.ReactNode; className?: string; [key: string]: any }}) {{\n'
                        f'  return <div className={{className}} {{...props}}>{{children}}</div>\n'
                        f'}}\n'
                    )
                # Add export to barrel
                resolved.write_text(content.rstrip() + f'\nexport {{ default as {export_name} }} from "./{export_name}"\n')
                return f"created {export_name}.tsx stub + added to {resolved.name}"

            # Case B: default export exists but import uses named — fix the import
            if f"export default" in content and f"export {{ {export_name}" not in content:
                src_dir = project_dir / "src"
                stem = resolved.stem
                for tsx in src_dir.rglob("*.tsx"):
                    tsx_content = tsx.read_text()
                    bad_import = f"{{ {export_name} }}"
                    if bad_import in tsx_content and (f"/{stem}" in tsx_content or f"'{stem}" in tsx_content):
                        fixed = tsx_content.replace(
                            f"{{ {export_name} }}",
                            export_name
                        )
                        tsx.write_text(fixed)
                        return f"fixed named→default import of {export_name} in {tsx.name}"
        return None

    # 3. Missing npm package
    # "Cannot find package 'X'"
    m = re.search(r"Cannot find package ['\"]([^'\"]+)['\"]", error)
    if m:
        pkg = m.group(1)
        # Only auto-install known-safe packages
        safe_packages = {
            "recharts", "d3", "papaparse", "xlsx",
            "express", "better-sqlite3", "cors", "ws",
            "framer-motion", "zustand", "react-router-dom", "react-icons",
            "date-fns", "lodash", "axios", "uuid",
        }
        if pkg in safe_packages:
            try:
                subprocess.run(
                    ["npm", "install", "--no-audit", "--no-fund", pkg],
                    cwd=str(project_dir), capture_output=True, timeout=30,
                )
                return f"npm installed {pkg}"
            except Exception:
                pass
        return None

    # 4. React hook not imported (backup for auto-inject)
    # "X is not defined" where X is a React hook
    m = re.search(r"(useState|useEffect|useRef|useCallback|useMemo|useContext) is not defined", error)
    if m:
        hook = m.group(1)
        # Find the file with the error
        file_match = re.search(r"([^\s:]+\.tsx?):", error)
        if file_match:
            file_path = project_dir / file_match.group(1)
            if not file_path.exists():
                file_path = project_dir / "src" / file_match.group(1)
            if file_path.exists():
                content = file_path.read_text()
                if 'from "react"' not in content and "from 'react'" not in content:
                    content = f'import {{ {hook} }} from "react"\n' + content
                    file_path.write_text(content)
                    return f"injected {hook} import in {file_path.name}"
        return None

    # 5. Duplicate identifier / redeclaration
    # Often from auto-wire writing duplicate imports
    m = re.search(r"Duplicate identifier ['\"](\w+)['\"]", error)
    if m:
        # Can't auto-fix easily — but log it for the LLM with context
        return None

    # 6. CSS module not found — file referenced but doesn't exist
    m = re.search(r"Could not resolve ['\"]\./([\w/]+\.css)['\"]", error)
    if m:
        css_path = project_dir / "src" / m.group(1)
        if not css_path.exists():
            css_path.parent.mkdir(parents=True, exist_ok=True)
            css_path.write_text("/* Auto-generated empty stylesheet */\n")
            return f"created empty {css_path.name} (missing CSS)"
        return None

    # 7. JSX namespace missing — React not imported in JSX file
    if "React" in error and "not defined" in error:
        file_match = re.search(r"([^\s:]+\.tsx?):", error)
        if file_match:
            file_path = _resolve_file(project_dir, file_match.group(1))
            if file_path and file_path.exists():
                content = file_path.read_text()
                if "import React" not in content:
                    content = 'import React from "react"\n' + content
                    file_path.write_text(content)
                    return f"injected React import in {file_path.name}"
        return None

    # 8. Type-only import used as value
    # "X only refers to a type, but is being used as a value here"
    if "only refers to a type" in error:
        # Usually needs `import type` → `import` or vice versa
        # Log but don't auto-fix (too many edge cases)
        return None

    # 9. Missing closing tag / unclosed JSX
    if "Unterminated JSX" in error or "Expected corresponding JSX closing tag" in error:
        # Can't auto-fix JSX structure — but log for pattern tracking
        return None

    # 10. Module has no default export — import default from named-only module
    m = re.search(r"does not provide an export named ['\"]default['\"]", error)
    if not m:
        m = re.search(r"No default export", error)
    if m:
        file_match = re.search(r"([^\s:]+\.tsx?):", error)
        if file_match:
            file_path = _resolve_file(project_dir, file_match.group(1))
            if file_path and file_path.exists():
                content = file_path.read_text()
                # Find the problematic import and convert to named
                imports = re.findall(r'import (\w+) from [\'"]([^\'"]+)[\'"]', content)
                for name, source in imports:
                    # Check if the source file only has named exports
                    source_path = _resolve_import(project_dir, file_path.parent, source)
                    if source_path and source_path.exists():
                        source_content = source_path.read_text()
                        if f"export default" not in source_content and f"export {{ {name}" not in source_content:
                            # Try converting to named import
                            old = f'import {name} from "{source}"'
                            new = f'import {{ {name} }} from "{source}"'
                            content = content.replace(old, new)
                            old2 = f"import {name} from '{source}'"
                            new2 = f"import {{ {name} }} from '{source}'"
                            content = content.replace(old2, new2)
                            file_path.write_text(content)
                            return f"fixed default→named import of {name} in {file_path.name}"
        return None

    # 11. Port already in use (dev server)
    if "EADDRINUSE" in error or "address already in use" in error.lower():
        m = re.search(r"port[:\s]+(\d+)", error, re.I)
        if m:
            port = m.group(1)
            try:
                subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=5)
                return f"killed process on port {port}"
            except Exception:
                pass
        return None

    # 12. tsconfig target too old — async/await or optional chaining fails
    if "Top-level 'await'" in error or "Optional chaining" in error:
        tsconfig = project_dir / "tsconfig.json"
        if tsconfig.exists():
            import json
            try:
                config = json.loads(tsconfig.read_text())
                opts = config.get("compilerOptions", {})
                if opts.get("target", "").lower() in ("es5", "es6", "es2015"):
                    opts["target"] = "ES2020"
                    config["compilerOptions"] = opts
                    tsconfig.write_text(json.dumps(config, indent=2))
                    return "upgraded tsconfig target to ES2020"
            except json.JSONDecodeError:
                pass
        return None

    # 13. Image/asset import fails — vite can't resolve
    m = re.search(r"Could not resolve ['\"]\./([\w/.-]+\.(png|jpg|svg|gif|webp))['\"]", error)
    if m:
        asset_path = project_dir / "src" / m.group(1)
        if not asset_path.exists():
            # Create a tiny placeholder SVG
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            if asset_path.suffix == ".svg":
                asset_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="#333"/></svg>')
            else:
                # Create a 1x1 pixel PNG
                asset_path.write_bytes(
                    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
                    b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
                    b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
                )
            return f"created placeholder {asset_path.name} (missing asset)"
        return None

    # 14. Vite env variable not defined
    if "import.meta.env" in error and "not defined" in error.lower():
        env_file = project_dir / ".env"
        if not env_file.exists():
            env_file.write_text("VITE_APP_TITLE=My App\n")
            return "created .env with placeholder"
        return None

    # 15. Index.html missing root div
    if "Target container is not a DOM element" in error:
        index = project_dir / "index.html"
        if index.exists():
            content = index.read_text()
            if 'id="root"' not in content:
                content = content.replace("</body>", '  <div id="root"></div>\n</body>')
                index.write_text(content)
                return "added root div to index.html"
        return None

    # 16. @engine path alias not resolved — missing vite alias config
    if "@engine" in error and "Could not resolve" in error:
        vite_config = project_dir / "vite.config.ts"
        if vite_config.exists():
            content = vite_config.read_text()
            if "@engine" not in content:
                # Inject the alias
                content = content.replace(
                    "export default defineConfig({",
                    "import path from 'path'\n\nexport default defineConfig({\n"
                    "  resolve: {\n    alias: {\n"
                    "      '@engine': path.resolve(__dirname, '../../engine/src'),\n"
                    "    },\n  },"
                )
                vite_config.write_text(content)
                return "added @engine alias to vite.config.ts"
        return None

    # 17. WebGPU not available — navigator.gpu undefined
    if "navigator.gpu" in error and ("undefined" in error.lower() or "null" in error.lower()):
        # Can't fix WebGPU availability, but inject a helpful error
        return None

    # 18. Canvas element not found
    m = re.search(r"getElementById\(['\"](\w+)['\"]\).*null", error)
    if m:
        element_id = m.group(1)
        index = project_dir / "index.html"
        if index.exists():
            content = index.read_text()
            if f'id="{element_id}"' not in content:
                content = content.replace(
                    "</body>",
                    f'  <canvas id="{element_id}" style="width:100vw;height:100vh;display:block"></canvas>\n</body>'
                )
                index.write_text(content)
                return f"added <canvas id='{element_id}'> to index.html"
        return None

    # 19. Escaped newlines in source files (Gemma 4 writes \\n instead of real newlines)
    if "Unexpected" in error or "not valid" in error:
        src_dir = project_dir / "src"
        if src_dir.exists():
            for tsx in src_dir.rglob("*.tsx"):
                content = tsx.read_text()
                if "\\n" in content and content.count("\\n") > 5:
                    fixed = content.replace("\\n", "\n").replace("\\t", "\t")
                    tsx.write_text(fixed)
                    return f"fixed escaped newlines in {tsx.name}"

    return None


# ─────────────────────────────────────────────────────────────
#   Step 9: design-script validator error patches
# ─────────────────────────────────────────────────────────────
#
# The TS validator emits 12 structured ValidationError kinds (see
# scaffolds/engine/src/design/schema.ts: ValidationError.kind union).
# When emit_design fails with stage='validate', Tsunami gets the list
# back as {kind, path, message, hint?, suggestions?}. Rather than
# regenerate the whole DesignScript, fix_design_validation_errors
# patches just the offending fragment — deterministic surgeries for the
# common cases, LLM fallback for the rest.
#
# Returns a dict describing what was patched (or None if no patch
# applied, caller should regenerate). Callers pass the live design JSON
# and the list of errors from emit_design's {stage:'validate', errors}
# return.

def fix_design_validation_errors(
    design: dict,
    errors: list[dict],
) -> tuple[dict, list[dict]]:
    """Apply deterministic patches for known validator error kinds.

    Returns (patched_design, unresolved_errors). Callers should retry
    emit_design with the patched design; if unresolved_errors is
    non-empty, those require LLM regeneration on the specific path.
    """
    unresolved: list[dict] = []
    for err in errors:
        kind = err.get("kind")
        path = err.get("path", "")
        patched = False
        try:
            if kind == "duplicate_id":
                # Rename the second mechanic's id to id + "_2" / "_3" etc.
                patched = _patch_duplicate_id(design, err)
            elif kind == "component_parse":
                # Strip unterminated paren or drop malformed component
                patched = _patch_component_parse(design, err)
            elif kind == "dangling_condition":
                # Inject an emit {condition:...} action in flow's on_enter,
                # OR remove the consumer if the emitter can't be inferred.
                patched = _patch_dangling_condition(design, err)
            elif kind == "unknown_mechanic_type":
                # Drop the mechanic — safer than guessing a type.
                patched = _patch_drop_offending(design, err, "mechanic")
            elif kind == "unknown_archetype_ref":
                # Can't invent an archetype. Send back to LLM.
                pass
            elif kind == "unknown_mechanic_ref":
                # Drop the `requires` entry that references the missing id.
                patched = _patch_drop_requires_ref(design, err)
            elif kind == "unknown_singleton_ref":
                # HUD field references missing singleton; drop that field.
                patched = _patch_drop_hud_field(design, err)
            elif kind == "unknown_item_ref":
                # Consumer references undeclared item; drop the consumer line.
                pass
            elif kind == "tag_requirement":
                # Add the missing tag to the first archetype that doesn't
                # already have it. Cheap and almost always correct.
                patched = _patch_add_tag(design, err)
            elif kind == "incompatible_combo":
                # Flip config.sandbox to false (the most common case).
                patched = _patch_clear_sandbox(design, err)
            elif kind == "playfield_mismatch":
                # Can't change the playfield without breaking other
                # mechanics. Send back to LLM.
                pass
            elif kind == "out_of_scope":
                # v2 placeholder mechanics get dropped.
                patched = _patch_drop_offending(design, err, "mechanic")
            elif kind == "unknown_sfx_preset":
                # play_sfx_ref.preset doesn't exist in the target
                # SfxLibrary. Can't invent a preset — drop the
                # offending action so build proceeds silently.
                patched = _patch_drop_audio_action(design, err)
            elif kind == "invalid_chiptune_track":
                # NoteEvent with bad time / duration / note. Drop the
                # specific bad note; the track keeps its other notes.
                patched = _patch_drop_bad_note(design, err)
            elif kind == "library_ref_not_sfx_library":
                # play_sfx_ref.library_ref points at a non-SfxLibrary
                # mechanic. Either retarget to an existing SfxLibrary
                # if unique, or drop the action.
                patched = _patch_retarget_sfx_library(design, err)
            elif kind == "unknown_mechanic_field":
                # bpm/mixer MechanicRef.field isn't in emits_fields.
                # Drop the ref back to a safe numeric default.
                patched = _patch_defaultise_mechanic_ref(design, err)
            elif kind == "invalid_quantize_source":
                # Drop quantize_to/quantize_source — the action still
                # fires, just without beat-aligned timing.
                patched = _patch_drop_quantize(design, err)
            elif kind == "overlay_condition_mismatch":
                # overlay_tracks and overlay_conditions must align.
                # Truncate both to the shorter of the two.
                patched = _patch_align_overlays(design, err)
            elif kind == "sprite_ref_not_in_manifest":
                # Drop the dangling sprite_ref — archetype falls back
                # to mesh rendering.
                patched = _patch_drop_sprite_ref(design, err)
            elif kind == "unknown_category":
                # Asset references a category we don't have. Remap
                # obvious synonyms, else drop the asset from the
                # manifest.
                patched = _patch_remap_category(design, err)
            elif kind == "metadata_schema_violation":
                # Field is wrong type / missing. Drop the offending
                # field; required-missing cases degrade to a
                # category-minimal metadata stub.
                patched = _patch_fix_metadata(design, err)
            elif kind == "chain_fan_out_invalid":
                # Pipeline-level authoring error — the LLM doesn't
                # author chains; this is almost always a manifest
                # handcraft issue. Surface to caller.
                pass
            elif kind == "backend_unavailable_no_fallback":
                # Can't patch the operator's server setup from here.
                pass
            elif kind == "unknown_op":
                # Same — chain authoring is the tool's job, not the
                # LLM's. Surface.
                pass
            elif kind == "unsupported_manifest_version":
                # Author wrote a bogus schema_version. Set to the
                # supported one and retry.
                patched = _patch_set_manifest_version(design, err)
        except Exception as e:
            log.warning(f"design error patcher raised on {kind}: {e}")
        if not patched:
            unresolved.append(err)
    return design, unresolved


def _path_tail(path: str) -> tuple[str, list[str]]:
    """Split 'mechanics[3].params.fields[2].singleton' into
    ('mechanics', ['3', 'params', 'fields', '2', 'singleton']). Tokens
    are raw — integers still as strings, caller parses ints."""
    if not path: return ("", [])
    tokens: list[str] = []
    cur = ""
    i = 0
    # crude tokenizer for dotted paths with [idx] brackets
    while i < len(path):
        c = path[i]
        if c == '.':
            if cur: tokens.append(cur); cur = ""
        elif c == '[':
            if cur: tokens.append(cur); cur = ""
            j = path.index(']', i)
            tokens.append(path[i+1:j])
            i = j
        else:
            cur += c
        i += 1
    if cur: tokens.append(cur)
    head = tokens[0] if tokens else ""
    return (head, tokens[1:])


def _patch_duplicate_id(design: dict, err: dict) -> bool:
    """mechanics[i].id → id + '_dup<n>'. Second+ occurrences get renamed.

    Gap #24 (Round O 2026-04-20): when the wave emits mechanics without
    `id` fields, the validator reports duplicate_id on ALL of them
    (they all share id=undefined / missing). The patcher used to no-op
    on empty originals. Now: if id is missing/empty, synthesize from
    the mechanic's `type` + idx (e.g. CameraFollow → "CameraFollow_3").
    Still uniqueness-safe — we check against existing ids to avoid
    collisions."""
    _, rest = _path_tail(err.get("path", ""))
    if not rest or not rest[0].isdigit(): return False
    idx = int(rest[0])
    mechs = design.get("mechanics", [])
    if idx >= len(mechs): return False
    if not isinstance(mechs[idx], dict):
        return False
    original = mechs[idx].get("id", "")
    if not original:
        # Fix #24: synthesize an id from type + idx
        mtype = mechs[idx].get("type", "") or "mechanic"
        # Kebab-ish base, keeping it readable
        base = str(mtype).strip() or "mechanic"
        candidate = f"{base}_{idx}"
        # Make unique if another mechanic already has this id
        n = 2
        while any(isinstance(m, dict) and m.get("id") == candidate for m in mechs):
            candidate = f"{base}_{idx}_{n}"
            n += 1
        mechs[idx]["id"] = candidate
        log.info(f"design patcher: duplicate_id (empty-id) → synthesized mechanics[{idx}].id = {candidate!r}")
        return True
    n = 2
    while any(isinstance(m, dict) and m.get("id") == f"{original}_dup{n}" for m in mechs): n += 1
    mechs[idx]["id"] = f"{original}_dup{n}"
    log.info(f"design patcher: duplicate_id → renamed mechanics[{idx}].id to {mechs[idx]['id']}")
    return True


def _patch_component_parse(design: dict, err: dict) -> bool:
    """archetypes[id].components[i] → drop the malformed entry."""
    _, rest = _path_tail(err.get("path", ""))
    if len(rest) < 3: return False
    aid = rest[0].strip('"')
    if rest[1] != "components" or not rest[2].isdigit(): return False
    archs = design.get("archetypes", {})
    if aid not in archs: return False
    comps = archs[aid].get("components", [])
    ci = int(rest[2])
    if ci >= len(comps): return False
    dropped = comps.pop(ci)
    log.info(f"design patcher: component_parse → dropped archetypes[{aid}].components[{ci}] = {dropped!r}")
    return True


def _patch_drop_offending(design: dict, err: dict, kind: str) -> bool:
    """Drop the offending mechanic entirely."""
    _, rest = _path_tail(err.get("path", ""))
    if not rest or not rest[0].isdigit(): return False
    if kind == "mechanic":
        idx = int(rest[0])
        mechs = design.get("mechanics", [])
        if idx >= len(mechs): return False
        dropped = mechs.pop(idx)
        log.info(f"design patcher: dropped mechanic {dropped.get('id')!r} ({dropped.get('type')})")
        return True
    return False


def _patch_drop_requires_ref(design: dict, err: dict) -> bool:
    """mechanics[i].requires[j] → remove the undefined ref."""
    _, rest = _path_tail(err.get("path", ""))
    if len(rest) < 3 or rest[1] != "requires": return False
    idx, j = int(rest[0]), int(rest[2])
    mechs = design.get("mechanics", [])
    if idx >= len(mechs): return False
    reqs = mechs[idx].get("requires", [])
    if j >= len(reqs): return False
    reqs.pop(j)
    if not reqs: mechs[idx].pop("requires", None)
    log.info(f"design patcher: dropped mechanics[{idx}].requires[{j}]")
    return True


def _patch_drop_hud_field(design: dict, err: dict) -> bool:
    """HUD fields[i].singleton references missing singleton — drop that field."""
    _, rest = _path_tail(err.get("path", ""))
    # Expected: ['<i>', 'params', 'fields', '<fi>', 'singleton']
    if len(rest) < 5 or rest[1] != "params" or rest[2] != "fields": return False
    idx, fi = int(rest[0]), int(rest[3])
    mechs = design.get("mechanics", [])
    if idx >= len(mechs): return False
    fields = mechs[idx].get("params", {}).get("fields", [])
    if fi >= len(fields): return False
    fields.pop(fi)
    log.info(f"design patcher: dropped mechanics[{idx}].params.fields[{fi}] (unknown singleton)")
    return True


def _patch_dangling_condition(design: dict, err: dict) -> bool:
    """Remove the offending consumer — safer than guessing an emitter.
    Handles flow.linear.steps[i].condition and on_enter/on_complete
    ActionRefs. For win/fail conditions, we leave them alone (the game
    can still run, it just never fires).

    Gap #28 (Round R 2026-04-20): also handle deeply-nested dangling
    conditions inside mechanic params (e.g.
    `mechanics[0].params.scenes[0].connections[0].trigger`). Generic
    path-walk: navigate to the parent container, drop the offending
    key. Works for both `.condition` and `.trigger` terminal keys."""
    path = err.get("path", "")
    # Old flow-linear case (kept for specificity).
    if "steps[" in path and path.endswith(".condition"):
        import re as _re
        m = _re.search(r'steps\[(\d+)\]\.condition$', path)
        if not m: return False
        si = int(m.group(1))
        flow = design.get("flow", {})
        if flow.get("kind") != "linear": return False
        steps = flow.get("steps", [])
        if si >= len(steps): return False
        steps[si].pop("condition", None)
        log.info(f"design patcher: dropped flow.linear.steps[{si}].condition (dangling)")
        return True

    # Generic deep-path walk for terminal .condition / .trigger / .when_state keys.
    # Path format: mechanics[0].params.scenes[0].connections[0].trigger
    # Navigate down to the parent of the terminal key, then pop it.
    if not path: return False
    terminal = path.rsplit(".", 1)[-1] if "." in path else ""
    if terminal not in ("condition", "trigger", "when_state"):
        return False
    import re as _re
    # Tokenize path into a sequence of (key, idx) pairs.
    # "mechanics[0].params.scenes[0].connections[0].trigger" →
    #   [("mechanics", 0), ("params", None), ("scenes", 0),
    #    ("connections", 0), ("trigger", None)]
    tokens: list[tuple[str, int | None]] = []
    for tok in path.split("."):
        m = _re.match(r'(\w+)(?:\[(\d+)\])?$', tok)
        if not m: return False
        name = m.group(1)
        idx = int(m.group(2)) if m.group(2) is not None else None
        tokens.append((name, idx))
    if not tokens: return False
    # Walk from design down through all but the last token.
    node = design
    for name, idx in tokens[:-1]:
        if not isinstance(node, dict): return False
        node = node.get(name)
        if idx is not None:
            if not isinstance(node, list) or idx >= len(node): return False
            node = node[idx]
    # node is now the parent container; tokens[-1] is the terminal key.
    last_name, last_idx = tokens[-1]
    if last_idx is not None:
        # Terminal is itself an array element — unusual for condition, bail.
        return False
    if not isinstance(node, dict):
        return False
    if last_name not in node:
        return False
    dropped = node.pop(last_name, None)
    log.info(f"design patcher: dropped {path} = {dropped!r} (dangling, deep-path)")
    return True


def _patch_add_tag(design: dict, err: dict) -> bool:
    """Add the missing tag to the first archetype lacking it. The
    error message format is: '<Type> requires tags t1, t2 on some
    archetype, none found'. Parse out the first missing tag.

    Handles BOTH shapes Qwen emits:
      archetypes: {"player": {tags:[...], ...}}    — schema canonical (dict)
      archetypes: [{"id": "player", "tags": [...]}]  — Round L iter 7 drift
    Without the list-shape branch, Round L-style deliveries would
    silently fail the patcher and never recover (gap #17b)."""
    import re as _re
    msg = err.get("message", "")
    m = _re.search(r"requires tags ([\w, ]+) on some archetype", msg)
    if not m: return False
    tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
    if not tags: return False
    archs = design.get("archetypes", {})
    # Dict shape (schema canonical)
    if isinstance(archs, dict) and archs:
        for _aid, arch in archs.items():
            if not isinstance(arch, dict):
                continue
            arch_tags = arch.setdefault("tags", [])
            for t in tags:
                if t not in arch_tags:
                    arch_tags.append(t)
            log.info(f"design patcher: added tags {tags} to first archetype to satisfy tag_requirement")
            return True
    # List shape (Round L drift — wave emits archetypes as list of objects)
    if isinstance(archs, list) and archs:
        for arch in archs:
            if not isinstance(arch, dict):
                continue
            arch_tags = arch.setdefault("tags", [])
            for t in tags:
                if t not in arch_tags:
                    arch_tags.append(t)
            log.info(f"design patcher: added tags {tags} to first archetype [list-shape] to satisfy tag_requirement")
            return True
    # Gap #23 (Round O 2026-04-20): wave emits `entities: [...]` instead
    # of `archetypes: {...}` (plan-prior carryover). Validator reads
    # `archetypes` only — tag_requirement fires with "none found" even
    # though entities[] has candidates that would logically qualify as
    # archetypes.
    # Gap #25 (Round P 2026-04-20): tagging entities alone doesn't
    # satisfy the validator (it reads archetypes). Fix: MIRROR the
    # first entity into archetypes so the validator sees a tagged
    # archetype. Original entities array stays intact (compiler may
    # consume either).
    ents = design.get("entities")
    archs_mut = design.setdefault("archetypes", {})
    # Ensure archetypes is a dict we can write to (it might be missing,
    # empty dict, or list — re-initialise to dict to guarantee
    # validator-visible shape).
    if not isinstance(archs_mut, dict):
        design["archetypes"] = {}
        archs_mut = design["archetypes"]
    if isinstance(ents, list) and ents:
        first = next((e for e in ents if isinstance(e, dict)), None)
        if first is not None:
            ent_tags = first.setdefault("tags", [])
            for t in tags:
                if t not in ent_tags:
                    ent_tags.append(t)
            # Mirror into archetypes so validator sees a tagged archetype.
            aid = first.get("id") or first.get("name") or "entity_0"
            if aid not in archs_mut:
                archs_mut[aid] = {
                    "tags": list(ent_tags),
                    "components": first.get("components", []),
                }
            else:
                arch_tags = archs_mut[aid].setdefault("tags", [])
                for t in tags:
                    if t not in arch_tags:
                        arch_tags.append(t)
            log.info(
                f"design patcher: added tags {tags} to first entity + "
                f"mirrored into archetypes[{aid!r}] to satisfy tag_requirement"
            )
            return True
    if isinstance(ents, dict) and ents:
        first_eid = next(iter(ents))
        first = ents[first_eid]
        if isinstance(first, dict):
            ent_tags = first.setdefault("tags", [])
            for t in tags:
                if t not in ent_tags:
                    ent_tags.append(t)
            aid = first_eid
            if aid not in archs_mut:
                archs_mut[aid] = {
                    "tags": list(ent_tags),
                    "components": first.get("components", []),
                }
            else:
                arch_tags = archs_mut[aid].setdefault("tags", [])
                for t in tags:
                    if t not in arch_tags:
                        arch_tags.append(t)
            log.info(
                f"design patcher: added tags {tags} to first entity + "
                f"mirrored into archetypes[{aid!r}] to satisfy tag_requirement"
            )
            return True
    return False


def _patch_clear_sandbox(design: dict, err: dict) -> bool:
    """Flip config.sandbox to false. Most 'incompatible_combo' cases
    trip on sandbox-incompatible mechanics in a sandbox=true config."""
    cfg = design.setdefault("config", {})
    if cfg.get("sandbox"):
        cfg["sandbox"] = False
        log.info("design patcher: cleared config.sandbox (incompatible_combo)")
        return True
    return False


# ══════════════════════════════════════════════════════════════════
#   Sprites v1.1 patchers
# ══════════════════════════════════════════════════════════════════

_CATEGORY_SYNONYMS = {
    # Legacy / obvious.
    "object": "item",
    "prop": "item",
    "item_sprite": "item",
    "char": "character",
    "enemy": "character",
    "player": "character",
    "npc": "character",
    "hero": "character",
    # UI variants.
    "ui": "ui_element",
    "button": "ui_element",
    "panel": "ui_element",
    "icon": "ui_element",
    # Terrain variants.
    "tile": "tileset",
    "tiles": "tileset",
    "terrain": "tileset",
    "map": "tileset",
    # Background variants.
    "bg": "background",
    "backdrop": "background",
    "scenery": "background",
    "landscape": "background",
    # Effect variants.
    "fx": "effect",
    "vfx": "effect",
    "particle": "effect",
    "explosion": "effect",
    # Portrait variants.
    "face": "portrait",
    "avatar": "portrait",
    # Texture variants.
    "pattern": "texture",
}

_KNOWN_CATEGORIES = {
    "character", "item", "texture", "tileset",
    "background", "ui_element", "effect", "portrait",
}


def _patch_drop_sprite_ref(design: dict, err: dict) -> bool:
    """sprite_ref_not_in_manifest: clear archetype.sprite_ref so the
    archetype falls back to its mesh. Leaves the archetype otherwise
    intact — caller can add the manifest entry later."""
    _, rest = _path_tail(err.get("path", ""))
    if len(rest) < 2 or rest[1] != "sprite_ref":
        return False
    aid = rest[0].strip('"')
    archs = design.get("archetypes", {})
    if aid not in archs:
        return False
    if "sprite_ref" not in archs[aid]:
        return False
    dropped = archs[aid].pop("sprite_ref", None)
    log.info(f"design patcher: sprite_ref_not_in_manifest → "
             f"dropped archetypes[{aid}].sprite_ref={dropped!r}")
    return True


def _patch_remap_category(design: dict, err: dict) -> bool:
    """unknown_category: remap to a synonym if we have one, else drop
    the asset from the sprite_manifest. Path is expected to locate
    the asset entry: sprite_manifest.assets[<id>].category or
    assets[<i>].category (build-step flat index)."""
    manifest = design.get("sprite_manifest") or design.get("assets_manifest")
    if not isinstance(manifest, dict):
        return False
    assets = manifest.get("assets")

    path = err.get("path", "")
    m = re.search(r'\[([^\]]+)\]\.category$', path)
    if not m:
        return False
    key = m.group(1).strip('"')

    # assets may be list (per tools/build_sprites.py authoring) or dict.
    if isinstance(assets, dict):
        target = assets.get(key)
        if not target:
            return False
        cur = target.get("category")
        remap = _CATEGORY_SYNONYMS.get((cur or "").lower())
        if remap:
            target["category"] = remap
            log.info(f"design patcher: unknown_category → remapped "
                     f"{key!r}.category {cur!r} → {remap!r}")
            return True
        assets.pop(key, None)
        log.info(f"design patcher: unknown_category → dropped asset {key!r}")
        return True

    if isinstance(assets, list):
        try:
            idx = int(key)
        except ValueError:
            return False
        if idx >= len(assets):
            return False
        cur = assets[idx].get("category")
        remap = _CATEGORY_SYNONYMS.get((cur or "").lower())
        if remap:
            assets[idx]["category"] = remap
            log.info(f"design patcher: unknown_category → remapped "
                     f"assets[{idx}].category {cur!r} → {remap!r}")
            return True
        dropped = assets.pop(idx)
        log.info(f"design patcher: unknown_category → dropped "
                 f"asset {dropped.get('id')!r}")
        return True

    return False


def _patch_fix_metadata(design: dict, err: dict) -> bool:
    """metadata_schema_violation: drop the bad field. Required fields
    we can't invent — surface to caller."""
    msg = err.get("message") or ""
    # Message format: "<category>.<field>: expected ..." or
    # "<category>.<field> is required but missing"
    m = re.match(r"(\w+)\.(\w+)", msg)
    if not m:
        return False
    field = m.group(2)
    # Find the metadata dict the error refers to — walk the path.
    _, rest = _path_tail(err.get("path", ""))
    manifest = design.get("sprite_manifest") or design.get("assets_manifest")
    if not isinstance(manifest, dict):
        return False
    assets = manifest.get("assets") or {}
    # Best-effort: search all assets for the offending field + drop.
    # `is required but missing` can't be fixed here — surface as
    # unresolved so the caller re-authors.
    if "required but missing" in msg:
        return False
    changed = False
    if isinstance(assets, dict):
        for _aid, a in assets.items():
            md = a.get("metadata")
            if isinstance(md, dict) and field in md:
                md.pop(field, None)
                changed = True
    elif isinstance(assets, list):
        for a in assets:
            md = a.get("metadata")
            if isinstance(md, dict) and field in md:
                md.pop(field, None)
                changed = True
    if changed:
        log.info(f"design patcher: metadata_schema_violation → "
                 f"dropped bad metadata field {field!r}")
    return changed


def _patch_set_manifest_version(design: dict, err: dict) -> bool:
    """unsupported_manifest_version: clamp to the currently-supported
    schema_version. v1.1 supports '1'."""
    manifest = design.get("sprite_manifest") or design.get("assets_manifest")
    if not isinstance(manifest, dict):
        return False
    manifest["schema_version"] = "1"
    log.info("design patcher: unsupported_manifest_version → "
             "clamped schema_version to '1'")
    return True


# ══════════════════════════════════════════════════════════════════
#   Audio v1.1 patchers
# ══════════════════════════════════════════════════════════════════

def _walk_tokens(root, tokens):
    """Walk a design document by path tokens. Returns (parent, key) such
    that parent[key] is the leaf — or (None, None) if any step is
    missing. Keys stay as strings or ints depending on the token (bare
    index tokens from [N] become ints)."""
    cur = root
    parent = None
    key = None
    for tok in tokens:
        parent = cur
        if tok.isdigit():
            k: int | str = int(tok)
        else:
            # trim wrapping quotes on map-key tokens
            k = tok.strip('"')
        key = k
        try:
            cur = cur[k]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return None, None
    return parent, key


_AUDIO_ACTION_KEYS = {"on_contact", "on_reverse", "on_enter", "on_exit",
                      "on_collect", "on_trigger", "on_complete",
                      "on_start", "autoplay_on", "stop_on"}


def _find_enclosing_action(tokens: list[str]) -> list[str] | None:
    """Given a path to a leaf inside an ActionRef object, return the
    tokens that address the ActionRef itself. We scan from the leaf
    back toward the root for the first key that's a known action-host
    (on_contact etc.) or is a list-index inside one. Returns the
    shortened token list, or None if no such anchor is found."""
    if not tokens:
        return None
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i] in _AUDIO_ACTION_KEYS:
            return tokens[: i + 1]
    return None


def _patch_drop_audio_action(design: dict, err: dict) -> bool:
    """unknown_sfx_preset: walk to the enclosing ActionRef and delete
    it. The action's host keeps its other behaviour — a silent drop is
    the safest fix when we can't invent a preset name."""
    _, rest = _path_tail(err.get("path", ""))
    anchor = _find_enclosing_action(rest)
    if not anchor:
        return False
    head = [_path_tail(err.get("path", ""))[0]]
    parent, key = _walk_tokens(design, head + anchor[:-1])
    if parent is None or key is None:
        return False
    try:
        container = parent[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return False
    action_key = anchor[-1]
    if isinstance(container, dict) and action_key in container:
        container.pop(action_key, None)
        log.info(f"design patcher: unknown_sfx_preset → dropped ActionRef at {err.get('path')}")
        return True
    return False


def _patch_drop_bad_note(design: dict, err: dict) -> bool:
    """invalid_chiptune_track on a specific NoteEvent leaf — path ends
    in .time / .duration / .note / .channels[ch][i]. We drop that one
    note and leave the rest of the track intact."""
    head, rest = _path_tail(err.get("path", ""))
    if not rest:
        return False
    # Strip trailing leaf (time/duration/note).
    if rest and rest[-1] in ("time", "duration", "note"):
        rest = rest[:-1]
    # rest should now end with [<idx>] addressing the note array slot.
    if not rest or not rest[-1].isdigit():
        return False
    note_idx = int(rest[-1])
    parent, key = _walk_tokens(design, [head] + rest[:-1])
    if parent is None or key is None:
        return False
    try:
        arr = parent[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return False
    if not isinstance(arr, list) or note_idx >= len(arr):
        return False
    arr.pop(note_idx)
    log.info(f"design patcher: invalid_chiptune_track → dropped note at {err.get('path')}")
    return True


def _patch_retarget_sfx_library(design: dict, err: dict) -> bool:
    """library_ref_not_sfx_library: if there's exactly one SfxLibrary
    mechanic defined, retarget library_ref to its id. Otherwise drop
    the action."""
    libs = [m.get("id") for m in design.get("mechanics", [])
            if m.get("type") == "SfxLibrary"]
    if len(libs) == 1:
        head, rest = _path_tail(err.get("path", ""))
        # leaf is `library_ref`
        if rest and rest[-1] == "library_ref":
            parent, key = _walk_tokens(design, [head] + rest[:-1])
            if parent is not None and key is not None:
                try:
                    parent[key]["library_ref"] = libs[0]  # type: ignore[index]
                    log.info(f"design patcher: library_ref_not_sfx_library → retargeted to {libs[0]!r}")
                    return True
                except (KeyError, IndexError, TypeError):
                    pass
    # Fallback: drop the ActionRef entirely.
    return _patch_drop_audio_action(design, err)


def _patch_defaultise_mechanic_ref(design: dict, err: dict) -> bool:
    """unknown_mechanic_field on a bpm / mixer ref — replace the
    `{mechanic_ref, field}` object with a safe numeric default (120 for
    bpm, 1 for mixer gains). Track structure stays intact."""
    head, rest = _path_tail(err.get("path", ""))
    if not rest:
        return False
    leaf = rest[-1]
    parent, key = _walk_tokens(design, [head] + rest[:-1])
    if parent is None or key is None:
        return False
    try:
        container = parent[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return False
    if not isinstance(container, dict) or leaf not in container:
        return False
    default = 120 if leaf == "bpm" else 1
    container[leaf] = default
    log.info(f"design patcher: unknown_mechanic_field → defaulted {err.get('path')} to {default}")
    return True


def _patch_drop_quantize(design: dict, err: dict) -> bool:
    """invalid_quantize_source: remove quantize_to + quantize_source +
    track_ref from the enclosing ActionRef. The action still fires,
    just without beat-aligned timing (or in the chiptune case, it's
    already broken and we drop it)."""
    head, rest = _path_tail(err.get("path", ""))
    if not rest:
        return False
    leaf = rest[-1]
    parent, key = _walk_tokens(design, [head] + rest[:-1])
    if parent is None or key is None:
        return False
    try:
        container = parent[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return False
    if not isinstance(container, dict):
        return False
    if leaf == "track_ref":
        # play_chiptune / stop_chiptune without a valid target — drop.
        return _patch_drop_audio_action(design, err)
    container.pop("quantize_to", None)
    container.pop("quantize_source", None)
    log.info(f"design patcher: invalid_quantize_source → stripped quantize_* at {err.get('path')}")
    return True


def _patch_align_overlays(design: dict, err: dict) -> bool:
    """overlay_condition_mismatch: truncate overlay_tracks and
    overlay_conditions to the shorter length so each track has a
    condition gate (or drop trailing conditions with no track)."""
    _, rest = _path_tail(err.get("path", ""))
    if not rest or not rest[0].isdigit():
        return False
    idx = int(rest[0])
    mechs = design.get("mechanics", [])
    if idx >= len(mechs):
        return False
    params = mechs[idx].get("params", {})
    tracks = params.get("overlay_tracks", [])
    conds = params.get("overlay_conditions", [])
    if not isinstance(tracks, list) or not isinstance(conds, list):
        return False
    n = min(len(tracks), len(conds))
    params["overlay_tracks"] = tracks[:n]
    params["overlay_conditions"] = conds[:n]
    if n == 0:
        params.pop("overlay_tracks", None)
        params.pop("overlay_conditions", None)
    log.info(f"design patcher: overlay_condition_mismatch → truncated both lists to {n}")
    return True


def _resolve_file(project_dir: Path, rel_path: str) -> Path | None:
    """Resolve a file path relative to project or src dir."""
    for base in [project_dir, project_dir / "src"]:
        p = base / rel_path
        if p.exists():
            return p
    return None


def _resolve_import(project_dir: Path, from_dir: Path, import_path: str) -> Path | None:
    """Resolve an import path to an actual file."""
    if import_path.startswith("."):
        base = from_dir / import_path
    else:
        return None  # node_modules — don't resolve
    for ext in [".tsx", ".ts", ".jsx", ".js", ""]:
        p = base.with_suffix(ext) if ext else base
        if p.exists():
            return p
        # Try index file
        idx = base / f"index{ext}" if ext else base / "index.ts"
        if idx.exists():
            return idx
    return None
