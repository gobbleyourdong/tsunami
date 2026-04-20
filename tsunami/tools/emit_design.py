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
import re
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


_PARSE_POS_RE = re.compile(r"at position (\d+)")


def _strip_json_comments(s: str) -> str:
    """Strip JS-style // line and /* */ block comments from a JSON-ish
    blob. Walks strings so `//` or `/*` inside a double-quoted value are
    preserved verbatim. Invariants: never touches characters between
    unescaped `"`s; always consumes full comment to EOL or closing `*/`.

    Extracted from _normalise_qwen_json so the normaliser (and its
    tests) can exercise this independently."""
    out_chars = []
    i = 0
    in_str = False
    esc = False
    while i < len(s):
        c = s[i]
        if esc:
            out_chars.append(c); esc = False; i += 1; continue
        if c == '\\' and in_str:
            out_chars.append(c); esc = True; i += 1; continue
        if c == '"':
            in_str = not in_str
            out_chars.append(c); i += 1; continue
        if not in_str and c == '/' and i + 1 < len(s) and s[i+1] == '/':
            while i < len(s) and s[i] != '\n':
                i += 1
            continue
        if not in_str and c == '/' and i + 1 < len(s) and s[i+1] == '*':
            i += 2
            while i + 1 < len(s) and not (s[i] == '*' and s[i+1] == '/'):
                i += 1
            i += 2  # consume closing */
            continue
        out_chars.append(c); i += 1
    return ''.join(out_chars)


def _normalise_qwen_json(text: str) -> tuple[str, bool]:
    """Patch common Qwen-generation drifts and retry json.loads.

    Drifts handled (in order): JS line/block comments, unquoted keys
    (incl. hyphenated), trailing commas, single-quoted string values.
    Only fires when strict json.loads fails. Conservative: never
    fabricates fields, just patches syntax. Returns (text_out, changed)
    where text_out is the normalised string (or original on unfixable)
    and changed indicates whether any patching took effect AND parsed."""
    try:
        json.loads(text)
        return text, False
    except Exception:
        pass
    out = _strip_json_comments(text)
    out = re.sub(
        r'([{,\s])([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)',
        r'\1"\2"\3',
        out,
    )
    out = re.sub(r',(\s*[}\]])', r'\1', out)
    out = re.sub(
        r"(?<=[:\[,\s])'([^'\\]*(?:\\.[^'\\]*)*)'",
        r'"\1"',
        out,
    )
    try:
        json.loads(out)
        return out, True
    except Exception:
        return text, False


def _annotate_parse_error(msg: str, raw_json: str) -> str:
    """Append a ±40-char excerpt around the error position to help the
    wave see the syntax drift (unquoted key, missing comma, etc.)."""
    import re as _re
    m = _re.search(r"at position (\d+)", msg)
    if not m or not raw_json:
        return msg
    pos = int(m.group(1))
    if pos < 0 or pos > len(raw_json):
        return msg
    lo = max(0, pos - 40)
    hi = min(len(raw_json), pos + 40)
    before = raw_json[lo:pos].replace("\n", "\\n")
    at = raw_json[pos:pos+1].replace("\n", "\\n") or "<EOF>"
    after = raw_json[pos+1:hi].replace("\n", "\\n")
    excerpt = f"...{before}⟦{at}⟧{after}..."
    return f"{msg}\nContext: {excerpt}"


def emit_design(
    design: Union[Dict[str, Any], str, Path],
    *,
    project_name: str,
    deliverables_dir: Union[str, Path] = "deliverables",
    timeout_sec: int = 30,
    auto_fix: bool = True,
) -> Dict[str, Any]:
    """Validate + compile a design, write to deliverables/<project_name>/.

    Args:
        design: DesignScript as dict, JSON string, or path to JSON file.
        project_name: directory under deliverables_dir to write to.
        deliverables_dir: parent dir; defaults to "deliverables" relative to
            the current working directory.
        timeout_sec: subprocess timeout; validator + compiler are both
            O(N) in design size so 30s is generous for v1 designs.
        auto_fix: when True (default), validation failures are run
            through error_fixer.fix_design_validation_errors for a
            single deterministic-patch pass, then re-compiled. Measurement
            harnesses can disable this to observe raw LLM one-shot
            validity. When the fix succeeds, the returned result has
            `auto_fixed: True`; when the fix leaves unresolved errors,
            those are returned as usual with `auto_fixed: False`.
    """
    # Normaliser is now at module level (_normalise_qwen_json); reuse it.

    # Normalise design → JSON string on stdin.
    if isinstance(design, (str, Path)):
        raw_json = str(design)
        # Path(str).exists() raises OSError[ENAMETOOLONG] on huge
        # strings — e.g., when the wave passes the whole design JSON
        # inline as a tool-call arg. Guard against that AND short-
        # circuit when the string is obviously-not-a-path (long,
        # or starts with '{' / '['). Live B-leg crash 2026-04-19:
        # 10-KB JSON string hit this branch and raised before we
        # could even try json.loads on it.
        is_file_path = False
        looks_like_path = (
            len(raw_json) < 1000
            and not raw_json.lstrip().startswith(("{", "["))
        )
        if looks_like_path:
            try:
                is_file_path = Path(raw_json).exists()
            except OSError:
                is_file_path = False
        if is_file_path:
            try:
                raw_json = Path(raw_json).read_text()
            except OSError:
                pass  # fall through; use raw_json as-is
        try:
            design_obj: Optional[Dict[str, Any]] = json.loads(raw_json)
        except Exception:
            # Try the normaliser — Qwen often ships unquoted keys /
            # trailing commas. If the normaliser succeeds, raw_json gets
            # re-assigned to the clean version so the Node CLI sees
            # valid JSON.
            normalised, changed = _normalise_qwen_json(raw_json)
            if changed:
                raw_json = normalised
                try:
                    design_obj = json.loads(raw_json)
                except Exception:
                    design_obj = None
            else:
                design_obj = None
    else:
        try:
            raw_json = json.dumps(design)
            design_obj = design if isinstance(design, dict) else None
        except Exception as e:
            return {"ok": False, "stage": "parse",
                    "message": f"design dict is not JSON-serialisable: {e}"}

    # Gap #26 (Round Q 2026-04-20): wave persistently emits
    # `entities: [...]` at root despite Fix #17a teaching the
    # schema-canonical `archetypes: {...}` shape. The compiler accepts
    # this, runs without validation errors, and produces a near-empty
    # default skeleton — entities silently dropped. emit_design returns
    # ok=true but the output has 0 entities.
    # Pre-compile shape normalizer: if design has entities but not
    # archetypes, lift entities → archetypes (dict keyed by id/name/idx).
    # Preserve original entities array (compiler ignores it harmlessly).
    # Round Q iter 6's wave entities also had hp/damage/speed as top-level
    # params — translate those to components so the ComponentSystem picks
    # them up (Health(hp), Damage(dmg), etc.) — preserves gameplay intent.
    def _lift_components_from_params(ent: dict) -> list:
        comps = list(ent.get("components", []) or [])
        # Case 1: entity has a `params` block with gameplay fields
        params = ent.get("params", {}) if isinstance(ent.get("params"), dict) else {}
        src = {**ent, **params}  # allow both top-level and nested
        has_health = any(c.startswith("Health(") for c in comps)
        # Translate common gameplay fields → schema-known component specs.
        if "hp" in src and isinstance(src["hp"], (int, float)) and not has_health:
            comps.append(f"Health({int(src['hp'])})")
            has_health = True
        if "max_hp" in src and isinstance(src["max_hp"], (int, float)) and not has_health:
            comps.append(f"Health({int(src['max_hp'])})")
        if "score" in src and not any(c == "Score" for c in comps):
            comps.append("Score")
        if src.get("inventory") is True or "items" in src:
            if not any(c == "Inventory" for c in comps):
                comps.append("Inventory")
        return comps

    # Gap #30 (Round S post-mortem 2026-04-20): wave emits
    # `{"id": "player_link", "name": "Link"}` — Fix #26 used id as the
    # archetype key, dropping the name "Link" from the compiled output.
    # The probe's content-adoption scan then misses "Link" entirely.
    # Preserve name as a tag so it survives compile AND shows up in
    # adoption metrics.
    def _ent_tags_with_name(ent: dict) -> list:
        tags = list(ent.get("tags", []) or [])
        name = ent.get("name")
        if isinstance(name, str) and name.strip():
            # Add as-is (e.g. "Link") — probe's variant matcher will
            # also catch lowercase/snake_case references.
            if name not in tags:
                tags.append(name)
        return tags

    if isinstance(design_obj, dict):
        if (design_obj.get("entities") and not design_obj.get("archetypes")):
            ents = design_obj["entities"]
            lifted: Dict[str, Any] = {}
            if isinstance(ents, list):
                for idx, ent in enumerate(ents):
                    if not isinstance(ent, dict):
                        continue
                    aid = (ent.get("id") or ent.get("name") or f"entity_{idx}")
                    if aid in lifted:
                        aid = f"{aid}_{idx}"
                    arch = {
                        "tags": _ent_tags_with_name(ent),
                        "components": _lift_components_from_params(ent),
                    }
                    # Carry across other schema-known fields if present.
                    for k in ("mesh", "controller", "ai", "trigger", "sprite_ref"):
                        if k in ent:
                            arch[k] = ent[k]
                    lifted[aid] = arch
            elif isinstance(ents, dict):
                for eid, ent in ents.items():
                    if not isinstance(ent, dict):
                        continue
                    arch = {
                        "tags": _ent_tags_with_name(ent),
                        "components": _lift_components_from_params(ent),
                    }
                    for k in ("mesh", "controller", "ai", "trigger", "sprite_ref"):
                        if k in ent:
                            arch[k] = ent[k]
                    lifted[eid] = arch
            if lifted:
                design_obj["archetypes"] = lifted

        # Flow-shape normalization: schema says `flow: FlowNode` (a
        # single tree node like `{kind: "scene", name: "overworld"}`).
        # Wave often emits `flow: ["overworld"]` (list of strings) or
        # `flow: ["overworld", "dungeon"]`. Convert to a linear FlowNode
        # so walkFlow at validate.ts:214 can traverse it.
        flow = design_obj.get("flow")
        if isinstance(flow, list) and flow:
            scene_names = [s for s in flow if isinstance(s, str)]
            if scene_names:
                if len(scene_names) == 1:
                    design_obj["flow"] = {
                        "kind": "scene",
                        "name": scene_names[0],
                    }
                else:
                    # Linear sequence of scenes
                    design_obj["flow"] = {
                        "kind": "linear",
                        "name": scene_names[0],
                        "steps": [{"scene": s} for s in scene_names],
                    }

        # Re-serialize if anything changed
        if isinstance(design_obj, dict):
            raw_json = json.dumps(design_obj)

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
            errors = payload.get("errors", [])
            # One-shot auto-repair: deterministic patches for the known
            # error classes (currently 14 across v1.0 + audio v1.1).
            if auto_fix and design_obj is not None and errors:
                try:
                    from tsunami.error_fixer import fix_design_validation_errors
                except Exception:
                    fix_design_validation_errors = None  # type: ignore[assignment]
                if fix_design_validation_errors is not None:
                    patched, unresolved = fix_design_validation_errors(
                        design_obj, errors,
                    )
                    if len(unresolved) < len(errors):
                        retry = emit_design(
                            patched,
                            project_name=project_name,
                            deliverables_dir=deliverables_dir,
                            timeout_sec=timeout_sec,
                            auto_fix=False,  # single pass only
                        )
                        retry["auto_fixed"] = retry.get("ok") is True
                        if not retry.get("ok"):
                            retry.setdefault("errors", unresolved)
                        return retry
            return {"ok": False, "stage": "validate",
                    "errors": errors, "auto_fixed": False}
        # Stage=parse errors benefit from a character-context excerpt so
        # the wave can self-correct faster. The Node CLI reports e.g.
        # "Expected ',' or ']' after array element in JSON at position
        # 5203" — the wave has to guess what's at pos 5203. Surface the
        # ±40 chars around the error position so it can see the drift.
        msg = payload.get("message", stderr[:500])
        if payload.get("stage") == "parse":
            msg = _annotate_parse_error(msg, raw_json)
        return {"ok": False, "stage": payload.get("stage", "emit"),
                "message": msg}

    # Success — parse stdout + write to disk.
    try:
        compiled = json.loads(proc.stdout)
    except Exception as e:
        return {"ok": False, "stage": "emit",
                "message": f"compiler output was not valid JSON: {e}"}

    # Write to public/ so Vite serves /game_definition.json — the game
    # scaffold's main.ts does `fetch('/game_definition.json')` and vite
    # maps public/ to the site root. Writing to the project root made
    # the fetch 404 and blank-canvased the game.
    out_dir = Path(deliverables_dir) / project_name / "public"
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

    def validate_input(self, **kwargs) -> str | None:
        """Gap #21 (Round N 2026-04-20): the wave often nests project_name
        INSIDE the design object (because the plan example shows project_name
        as a top-level key of the design JSON). Before rejecting with
        "Missing required parameter: 'project_name'", try to hoist it from
        design.project_name into kwargs. The base validator then sees a
        well-formed call and proceeds."""
        if not kwargs.get("project_name"):
            design = kwargs.get("design")
            nested = None
            if isinstance(design, dict):
                nested = design.get("project_name")
            elif isinstance(design, str):
                try:
                    parsed = json.loads(design)
                    if isinstance(parsed, dict):
                        nested = parsed.get("project_name")
                except Exception:
                    pass
            if isinstance(nested, str) and nested.strip():
                kwargs["project_name"] = nested.strip()
        return super().validate_input(**kwargs)

    async def execute(
        self,
        design: Optional[Union[Dict[str, Any], str]] = None,
        project_name: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        if design is None:
            return ToolResult("emit_design: 'design' is required", is_error=True)
        # Fallback hoist for execute() too — validate_input already tried
        # but defensive: if somehow project_name was lost, extract it again.
        if not project_name and isinstance(design, dict):
            nested = design.get("project_name")
            if isinstance(nested, str) and nested.strip():
                project_name = nested.strip()
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
