"""Continuous learning — observe tool calls, extract patterns, evolve.

Inspired by ECC's instinct system. Every tool call gets logged to JSONL.
The 2B model periodically analyzes observations and extracts "instincts" —
atomic learned behaviors with confidence scores.

Instincts get injected into future sessions so the agent improves over time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("tsunami.observer")

# Secret scrubbing regex (from ECC)
SECRET_PATTERN = re.compile(
    r'(?i)(api[_-]?key|token|secret|password|authorization|credentials?|auth)'
    r'(["\'\s:=]+)([A-Za-z]+\s+)?([A-Za-z0-9_\-/.+=]{8,})'
)

MAX_FIELD_LEN = 5000
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _scrub_secrets(text: str) -> str:
    """Redact common secret patterns."""
    return SECRET_PATTERN.sub(r'\1\2\3[REDACTED]', text)


# QA-3 Fires 38 + 41: chat-template role boundaries and tool-call sigils
# must NOT land in observations.jsonl verbatim — memory_extract reads this
# file to build heuristics, and a poisoned tip like `<end_of_turn>...` can
# re-enter future system prompts. Replace with inert placeholders.
_ROLE_TOKEN_PATTERNS = [
    (re.compile(r'<end_of_turn>'), '[role-token]'),
    (re.compile(r'<start_of_turn>'), '[role-token]'),
    (re.compile(r'<\|tool_call>'), '[tool-call-sigil]'),
    (re.compile(r'<tool_call\|>'), '[tool-call-sigil]'),
    (re.compile(r'<\|tool_response>'), '[tool-call-sigil]'),
    (re.compile(r'<tool_response\|>'), '[tool-call-sigil]'),
    (re.compile(r'<\|"\|>'), '[str-delim]'),
]


def _scrub_role_tokens(text: str) -> str:
    """Replace chat-template role boundary tokens + Gemma tool-call sigils
    with inert placeholders so they can't re-enter a future session's
    system prompt via memory_extract → instincts propagation."""
    for pat, repl in _ROLE_TOKEN_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _truncate(text: str, max_len: int = MAX_FIELD_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... [truncated {len(text) - max_len} chars]"


def get_project_id(workspace_dir: str) -> str:
    """Derive project ID from git remote (portable across machines)."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
            cwd=workspace_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            return hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:12]
    except Exception:
        pass
    # Fallback: hash the workspace path
    return hashlib.sha256(workspace_dir.encode()).hexdigest()[:12]


class Observer:
    """Observes tool calls and writes to JSONL."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.project_id = get_project_id(workspace_dir)
        self.obs_dir = Path(workspace_dir) / ".observations"
        self.obs_dir.mkdir(parents=True, exist_ok=True)
        self.obs_file = self.obs_dir / "observations.jsonl"
        self.instincts_dir = self.obs_dir / "instincts"
        self.instincts_dir.mkdir(parents=True, exist_ok=True)
        self._call_count = 0

    def observe_tool_call(self, tool_name: str, arguments: dict,
                          result: str, is_error: bool, session_id: str = ""):
        """Record a tool call observation."""
        self._call_count += 1

        # QA-3 Fire 41: refused tool-call INPUTS landed in observations.jsonl
        # verbatim, including chat-template-injection payloads + poison
        # markers. memory_extract reads this file as a heuristics source, so
        # attacker content could propagate into future sessions' instincts.
        # Fix: when a tool call is refused, preserve the tool NAME and the
        # refusal MESSAGE (both useful learning signals) but drop the raw
        # input — the specific bytes the attacker emitted aren't what the
        # agent should learn from, the pattern of refusal is.
        if is_error:
            input_record = "[REFUSED: input omitted per QA-3 Fire 41 policy]"
        else:
            input_record = _scrub_secrets(_truncate(json.dumps(arguments)))

        # QA-3 Fire 41 + 38: even on successful calls, strip chat-template
        # role boundary tokens and the `<|tool_call>` / `<|"|>` sigils from
        # the record. These have no legit reason to appear inside tool
        # inputs; when they do, it's either a parser artefact or an attack
        # echo. Replacing them keeps observation-sourced heuristics from
        # reproducing the tokens verbatim if memory_extract ever feeds this
        # data back into a system prompt.
        input_record = _scrub_role_tokens(input_record)
        output_record = _scrub_role_tokens(
            _scrub_secrets(_truncate(result))
        )

        obs = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "tool": tool_name,
            "input": input_record,
            "output": output_record,
            "error": is_error,
            "session": session_id,
            "project_id": self.project_id,
        }

        # Append to JSONL
        try:
            with open(self.obs_file, "a") as f:
                f.write(json.dumps(obs) + "\n")
        except Exception as e:
            log.warning(f"Failed to write observation: {e}")

        # Rotate if too large
        if self.obs_file.exists() and self.obs_file.stat().st_size > MAX_FILE_SIZE:
            archive_dir = self.obs_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.obs_file.rename(archive_dir / f"observations-{ts}.jsonl")

    @property
    def call_count(self) -> int:
        return self._call_count

    def get_recent_observations(self, n: int = 100) -> list[dict]:
        """Get last N observations."""
        if not self.obs_file.exists():
            return []
        try:
            lines = self.obs_file.read_text().strip().split("\n")
            return [json.loads(l) for l in lines[-n:] if l.strip()]
        except Exception:
            return []

    def load_instincts(self) -> list[dict]:
        """Load all instinct files."""
        instincts = []
        for f in self.instincts_dir.glob("*.json"):
            try:
                instincts.append(json.loads(f.read_text()))
            except Exception:
                continue
        return sorted(instincts, key=lambda x: x.get("confidence", 0), reverse=True)

    def save_instinct(self, instinct: dict):
        """Save an instinct to disk."""
        iid = instinct.get("id", f"instinct-{int(time.time())}")
        path = self.instincts_dir / f"{iid}.json"
        path.write_text(json.dumps(instinct, indent=2))
        log.info(f"Saved instinct: {iid} (confidence={instinct.get('confidence', 0)})")

    def learn_from_build(self, project_dir: str, iterations: int, success: bool, tools_used: list[str]):
        """Extract and save patterns from a completed build.

        Called after message_result. Records what worked so future
        builds of similar projects can skip the trial-and-error.
        """
        from pathlib import Path
        proj = Path(project_dir)
        if not proj.exists():
            return

        # What scaffold was used?
        scaffold = "unknown"
        pkg = proj / "package.json"
        if pkg.exists():
            try:
                import json as _json
                data = _json.loads(pkg.read_text())
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "@engine" in pkg.read_text() or "@webgpu/types" in deps:
                    scaffold = "game"
                elif "recharts" in deps and "express" not in deps:
                    scaffold = "data-viz"
                elif "express" in deps:
                    scaffold = "fullstack"
                elif "ws" in deps:
                    scaffold = "realtime"
                else:
                    scaffold = "react-app"
            except Exception:
                pass

        # Count file types
        src = proj / "src"
        tsx_count = len(list(src.rglob("*.tsx"))) if src.exists() else 0
        css_count = len(list(src.rglob("*.css"))) if src.exists() else 0

        # Tool frequency
        tool_freq = {}
        for t in tools_used:
            tool_freq[t] = tool_freq.get(t, 0) + 1

        pattern = {
            "id": f"build-{proj.name}-{int(time.time())}",
            "type": "build_pattern",
            "project": proj.name,
            "scaffold": scaffold,
            "iterations": iterations,
            "success": success,
            "tsx_files": tsx_count,
            "css_files": css_count,
            "top_tools": sorted(tool_freq.items(), key=lambda x: -x[1])[:5],
            "confidence": 0.6 if success else 0.3,
        }

        self.save_instinct(pattern)
        log.info(f"Learned from build: {proj.name} ({scaffold}, {iterations} iters, {'success' if success else 'failed'})")

    async def analyze_observations(self, fast_endpoint: str = os.environ.get("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8092")):
        """Use the 2B model to extract instincts from recent observations."""
        recent = self.get_recent_observations(50)
        if len(recent) < 5:
            return  # Not enough data

        # Group by error patterns
        errors = [o for o in recent if o.get("error")]
        successes = [o for o in recent if not o.get("error")]

        # Build analysis prompt. QA-3 Fire 41 noted observations.jsonl captures
        # tool-call inputs verbatim, including refused ones — so attacker content
        # planted via chat-template injection ends up here. Escape role tokens
        # before feeding to the 2B extractor: prevents observation content from
        # being interpreted as role boundaries in the extractor's tokenizer.
        from .chat_template_safety import escape_role_tokens as _esc
        obs_text = ""
        for o in recent[-30:]:
            status = "FAILED" if o.get("error") else "OK"
            obs_text += f"[{status}] {o['tool']}: {_esc(o.get('input', ''))[:200]}\n"
            if o.get("error"):
                obs_text += f"  Error: {_esc(o.get('output', ''))[:200]}\n"

        prompt = f"""Analyze these tool call observations and extract 1-3 learned patterns.

Observations:
{obs_text}

For each pattern, output EXACTLY this JSON format (one per line):
{{"id": "short-kebab-id", "trigger": "when X happens", "action": "do Y instead of Z", "confidence": 0.5, "domain": "workflow"}}

Rules:
- Only extract patterns with clear evidence (error→fix, or repeated behavior)
- confidence: 0.3 (seen once), 0.5 (seen 2-3x), 0.7 (seen 5+x), 0.9 (always)
- domain: one of code-style, testing, workflow, debugging, file-patterns, security
- If no clear patterns, output nothing"""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{fast_endpoint}/v1/chat/completions",
                    json={
                        "model": "qwen",
                        "messages": [
                            {"role": "system", "content": "You extract patterns from tool call logs. Output JSON only."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 500,
                        "temperature": 0.3,
                    },
                    headers={"Authorization": "Bearer not-needed"},
                )
                if resp.status_code != 200:
                    return

                content = resp.json()["choices"][0]["message"]["content"]

                # Parse instinct JSON lines
                import re
                for line in content.split("\n"):
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        instinct = json.loads(line)
                        if "id" in instinct and "trigger" in instinct:
                            # Merge with existing (update confidence if higher)
                            existing = self.instincts_dir / f"{instinct['id']}.json"
                            if existing.exists():
                                old = json.loads(existing.read_text())
                                instinct["confidence"] = max(
                                    instinct.get("confidence", 0.5),
                                    old.get("confidence", 0) + 0.05
                                )
                            self.save_instinct(instinct)
                    except json.JSONDecodeError:
                        continue

                log.info(f"Instinct analysis complete on {len(recent)} observations")

        except Exception as e:
            log.debug(f"Instinct analysis skipped: {e}")

    def observe_llm_usage(self, prompt_tokens: int, completion_tokens: int,
                          model: str = "", latency_ms: float = 0):
        """Track LLM usage metrics per response."""
        metrics_file = self.obs_dir / "usage.jsonl"
        try:
            record = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": round(latency_ms),
                "session": "",
                "project_id": self.project_id,
            }
            with open(metrics_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def get_usage_stats(self) -> dict:
        """Get aggregate usage stats."""
        metrics_file = self.obs_dir / "usage.jsonl"
        if not metrics_file.exists():
            return {}
        try:
            records = [json.loads(l) for l in metrics_file.read_text().strip().split("\n") if l.strip()]
            total_prompt = sum(r.get("prompt_tokens", 0) for r in records)
            total_completion = sum(r.get("completion_tokens", 0) for r in records)
            total_calls = len(records)
            avg_latency = sum(r.get("latency_ms", 0) for r in records) / max(total_calls, 1)
            return {
                "total_calls": total_calls,
                "total_tokens": total_prompt + total_completion,
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "avg_latency_ms": round(avg_latency),
            }
        except Exception:
            return {}

    async def extract_session_memories(self, fast_endpoint: str = os.environ.get("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8092")):
        """Background memory extraction after session ends.

        Analyzes recent observations and writes structured memories to disk.
        Runs as a background task — doesn't block the agent loop.
        """
        recent = self.get_recent_observations(30)
        if len(recent) < 3:
            return

        # Build context from observations
        obs_summary = []
        for o in recent[-20:]:
            status = "ERROR" if o.get("error") else "OK"
            obs_summary.append(f"[{status}] {o['tool']}: {o.get('input', '')[:100]}")

        prompt = (
            "Analyze these tool call observations from a completed session. "
            "Extract 1-3 memories worth saving for future sessions.\n\n"
            "For each memory, output JSON: "
            '{"id": "short-id", "type": "feedback|project|user", '
            '"trigger": "when this situation occurs", '
            '"action": "do this", "confidence": 0.5}\n\n'
            "Observations:\n" + "\n".join(obs_summary) + "\n\n"
            "Only extract patterns with clear evidence. If nothing worth saving, output nothing."
        )

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{fast_endpoint}/v1/chat/completions",
                    json={
                        "model": "qwen",
                        "messages": [
                            {"role": "system", "content": "Extract memories from agent sessions. Output JSON only."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 500,
                        "temperature": 0.3,
                    },
                    headers={"Authorization": "Bearer not-needed"},
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    import re
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.startswith("{"):
                            try:
                                memory = json.loads(line)
                                if "id" in memory and "trigger" in memory:
                                    self.save_instinct(memory)
                            except json.JSONDecodeError:
                                continue
        except Exception:
            pass

    def format_instincts_for_prompt(self, max_tokens: int = 500) -> str:
        """Format top instincts for injection into system prompt."""
        instincts = self.load_instincts()
        if not instincts:
            return ""

        lines = ["# Learned Patterns (from previous sessions)"]
        chars = 0
        for inst in instincts[:10]:  # Top 10 by confidence
            line = f"- {inst.get('trigger', '')}: {inst.get('action', '')} (confidence: {inst.get('confidence', 0):.1f})"
            if chars + len(line) > max_tokens * 4:
                break
            lines.append(line)
            chars += len(line)

        return "\n".join(lines) if len(lines) > 1 else ""
