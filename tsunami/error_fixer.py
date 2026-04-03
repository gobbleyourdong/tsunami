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


def try_auto_fix(project_dir: Path, errors: list[str]) -> bool:
    """Attempt deterministic fixes for common compile errors.

    Returns True if a fix was applied (caller should rebuild).
    Returns False if no fix was possible (fall through to LLM).
    """
    for error in errors:
        fix = _classify_and_fix(project_dir, error)
        if fix:
            log.info(f"Auto-fix applied: {fix}")
            return True
    return False


def _classify_and_fix(project_dir: Path, error: str) -> str | None:
    """Classify an error and attempt a fix. Returns description or None."""

    # 1. Missing module — file doesn't exist
    # "Cannot resolve entry module" or "Could not resolve './components/Sidebar'"
    m = re.search(r"Could not resolve ['\"]\./(components/\w+)['\"]", error)
    if not m:
        m = re.search(r"Could not resolve ['\"]\.\./(components/\w+)['\"]", error)
    if m:
        comp_path = m.group(1)
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

    # 2. Named vs default export mismatch
    # "'X' is not exported by 'src/components/Y.tsx'"
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
            # Check if it has default export but import uses named
            if f"export default" in content and f"export {{ {export_name}" not in content:
                # Add named re-export
                content += f"\nexport {{ default as {export_name} }} from './{resolved.stem}'\n"
                # Actually, fix the importing file instead
                # Find who imports this
                src_dir = project_dir / "src"
                for tsx in src_dir.rglob("*.tsx"):
                    tsx_content = tsx.read_text()
                    bad_import = f"{{ {export_name} }}"
                    if bad_import in tsx_content and file_path.replace(".tsx", "") in tsx_content:
                        fixed = tsx_content.replace(
                            f"{{ {export_name} }}",
                            export_name
                        )
                        # Also fix "from" to not use braces
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

    return None
