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
from datetime import datetime
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

        obs = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool": tool_name,
            "input": _scrub_secrets(_truncate(json.dumps(arguments))),
            "output": _scrub_secrets(_truncate(result)),
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

    async def analyze_observations(self, fast_endpoint: str = os.environ.get("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8092")):
        """Use the 2B model to extract instincts from recent observations."""
        recent = self.get_recent_observations(50)
        if len(recent) < 5:
            return  # Not enough data

        # Group by error patterns
        errors = [o for o in recent if o.get("error")]
        successes = [o for o in recent if not o.get("error")]

        # Build analysis prompt
        obs_text = ""
        for o in recent[-30:]:
            status = "FAILED" if o.get("error") else "OK"
            obs_text += f"[{status}] {o['tool']}: {o.get('input', '')[:200]}\n"
            if o.get("error"):
                obs_text += f"  Error: {o.get('output', '')[:200]}\n"

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
                "timestamp": datetime.utcnow().isoformat() + "Z",
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
