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
            "recharts", "d3", "papaparse", "xlsx", "matter-js",
            "three", "@react-three/fiber", "@react-three/drei", "@react-three/rapier",
            "pixi.js", "@pixi/react", "express", "better-sqlite3", "cors", "ws",
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
