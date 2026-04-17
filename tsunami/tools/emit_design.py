"""emit_design — Python wrapper around the engine's TS design compiler.

Takes a DesignScript JSON (either a dict, a JSON string, or a file path),
runs it through `scaffolds/engine/src/design/cli.ts` under node+tsx, and
writes the resulting GameDefinition to
`deliverables/<project_name>/game_definition.json`.

Exposes a single `emit_design()` function and an `EmitDesignTool`
BaseTool subclass so agent.py can invoke it through the normal tool
registry. The tool is the unblocker for ship-gate #14 (Tsunami one-shot
arena-shooter emission with valid design ≥ 50% over N=20 runs).

Returns a structured result:
    {
      "ok": bool,
      "stage": "read" | "parse" | "validate" | "compile" | "emit" | "ok",
      "errors": [ValidationError, ...]       # only on stage=validate
      "message": str                          # only on other failures
      "output_path": str                      # only on ok
      "compiled": dict                        # only on ok (the GameDefinition)
    }

Never raises on design-level failures; agent.py's error_fixer.py consumes
the error structure and regenerates the offending design fragment.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseTool, ToolResult

# Absolute path to the TS cli entrypoint in the engine scaffold. Anchored
# on this file's location so relocating tsunami/ doesn't break invocation.
_ENGINE_CLI = (
    Path(__file__).resolve().parents[2]
    / "scaffolds" / "engine" / "src" / "design" / "cli.ts"
)


def _find_node_runner() -> List[str]:
    """Pick the node+tsx command line the scaffold supports.

    Prefers `npx tsx` (zero config, uses the engine's locally-installed
    tsx when available), falls back to `node --import tsx` for environments
    where tsx is global. Raises FileNotFoundError when neither is present.
    """
    if shutil.which("npx") is not None:
        return ["npx", "--yes", "tsx"]
    if shutil.which("node") is not None:
        return ["node", "--import", "tsx/esm"]
    raise FileNotFoundError(
        "Neither `npx` nor `node` is on PATH — install Node.js ≥ 18 to use emit_design"
    )


def emit_design(
    design: Union[Dict[str, Any], str, Path],
    *,
    project_name: str,
    deliverables_dir: Union[str, Path] = "deliverables",
    timeout_sec: int = 30,
) -> Dict[str, Any]:
    """Validate + compile a design, write to deliverables/<project_name>/.

    Args:
        design: DesignScript as dict, JSON string, or path to JSON file.
        project_name: directory under deliverables_dir to write to.
        deliverables_dir: parent dir; defaults to "deliverables" relative to
            the current working directory.
        timeout_sec: subprocess timeout; validator + compiler are both
            O(N) in design size so 30s is generous for v1 designs.
    """
    # Normalise design → JSON string on stdin.
    if isinstance(design, (str, Path)):
        p = Path(design)
        if p.exists():
            raw_json = p.read_text()
        else:
            raw_json = str(design)  # treat as raw JSON string
    else:
        try:
            raw_json = json.dumps(design)
        except Exception as e:
            return {"ok": False, "stage": "parse",
                    "message": f"design dict is not JSON-serialisable: {e}"}

    try:
        runner = _find_node_runner()
    except FileNotFoundError as e:
        return {"ok": False, "stage": "emit", "message": str(e)}

    cmd = [*runner, str(_ENGINE_CLI)]
    try:
        proc = subprocess.run(
            cmd,
            input=raw_json,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "emit",
                "message": f"compiler timed out after {timeout_sec}s"}
    except Exception as e:
        return {"ok": False, "stage": "emit",
                "message": f"failed to spawn compiler: {e}"}

    # The CLI emits structured JSON on stderr when something goes wrong.
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        try:
            payload = json.loads(stderr.splitlines()[-1])
        except Exception:
            return {"ok": False, "stage": "emit",
                    "message": f"compiler exited {proc.returncode}: {stderr[:500]}"}
        # Canonical shape: {stage, errors?, message?, ...}
        if payload.get("stage") == "validate":
            return {"ok": False, "stage": "validate",
                    "errors": payload.get("errors", [])}
        return {"ok": False, "stage": payload.get("stage", "emit"),
                "message": payload.get("message", stderr[:500])}

    # Success — parse stdout + write to disk.
    try:
        compiled = json.loads(proc.stdout)
    except Exception as e:
        return {"ok": False, "stage": "emit",
                "message": f"compiler output was not valid JSON: {e}"}

    out_dir = Path(deliverables_dir) / project_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "game_definition.json"
    out_path.write_text(json.dumps(compiled, indent=2))

    return {
        "ok": True,
        "stage": "ok",
        "output_path": str(out_path),
        "compiled": compiled,
    }


# ─────────────────────────────────────────────────────────────
#   Agent tool wrapper
# ─────────────────────────────────────────────────────────────

class EmitDesignTool(BaseTool):
    name = "emit_design"
    description = (
        "Validate and compile a DesignScript JSON into a GameDefinition, "
        "written to deliverables/<project_name>/game_definition.json. "
        "Invoke with a `design` dict (or JSON string) and a `project_name`. "
        "Returns {ok, stage, errors?, output_path?} — when ok=false and "
        "stage='validate', errors is a list of {kind, path, message, hint?}."
    )
    concurrent_safe = False

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "design": {
                    "type": ["object", "string"],
                    "description": "DesignScript JSON (object) or raw JSON string.",
                },
                "project_name": {
                    "type": "string",
                    "description": "Subdirectory of deliverables/ to write to.",
                },
            },
            "required": ["design", "project_name"],
        }

    async def execute(
        self,
        design: Optional[Union[Dict[str, Any], str]] = None,
        project_name: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        if design is None:
            return ToolResult("emit_design: 'design' is required", is_error=True)
        if not project_name:
            return ToolResult("emit_design: 'project_name' is required", is_error=True)
        deliverables = getattr(self.config, "deliverables_dir",
                               Path(getattr(self.config, "workspace_dir", ".")) / "deliverables")
        result = emit_design(
            design,
            project_name=project_name,
            deliverables_dir=deliverables,
        )
        if result["ok"]:
            return ToolResult(
                f"Compiled design → {result['output_path']}\n"
                f"Scenes: {len(result['compiled'].get('scenes', {}))}, "
                f"Flow steps: {len(result['compiled'].get('flow', []))}"
            )
        if result["stage"] == "validate":
            errs = result.get("errors", [])
            lines = [f"Validation failed ({len(errs)} errors):"]
            for e in errs[:10]:
                lines.append(f"  [{e.get('kind')}] {e.get('path')}: {e.get('message')}")
                if e.get("hint"):
                    lines.append(f"      hint: {e['hint']}")
            return ToolResult("\n".join(lines), is_error=True)
        return ToolResult(
            f"emit_design failed at stage={result['stage']}: "
            f"{result.get('message', '?')}",
            is_error=True,
        )
