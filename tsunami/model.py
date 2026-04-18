"""LLM model — talks to serve_transformers.py on port 8090.

Single model, single endpoint, no backend abstraction.
Includes retry logic with exponential backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("tsunami.model")

MAX_RETRIES = 5
BASE_DELAY_MS = 500
MAX_DELAY_MS = 32_000


def get_retry_delay(attempt: int, retry_after: str | None = None, max_delay_ms: int = MAX_DELAY_MS) -> float:
    """Exponential backoff with jitter."""
    import random
    if retry_after:
        try:
            return int(retry_after)
        except (ValueError, TypeError):
            pass
    base_delay = min(BASE_DELAY_MS * (2 ** attempt), max_delay_ms)
    jitter = random.random() * 0.25 * base_delay
    return (base_delay + jitter) / 1000


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_call: ToolCall | None = None
    raw: dict | None = None


class TsunamiModel:
    """Talks to serve_transformers.py via OpenAI-compatible /v1/chat/completions."""

    def __init__(self, model: str = "tsunami", endpoint: str = "http://localhost:8090",
                 temperature: float = 0.6, max_tokens: int = 81920,
                 top_p: float = 0.95, top_k: int = 20,
                 min_p: float = 0.0,
                 presence_penalty: float = 0.0,
                 repetition_penalty: float = 1.0,
                 client_id: str = "", adapter: str = "", **kwargs):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k  # Qwen3.6 README: top_k=20 (Precise Coding)
        self.min_p = min_p  # Qwen3.6 README: min_p=0.0
        self.presence_penalty = presence_penalty
        self.repetition_penalty = repetition_penalty  # Qwen3.6 README: 1.0
        # Identity for the server's per-user fairness queue (TSUNAMI_USER env).
        # Kept nonempty if set; the server treats "" as a shared "default" user.
        self.client_id = client_id
        # LoRA adapter name for per-request server-side swap (TSUNAMI_ADAPTER env).
        # "" = leave server's current adapter; "none" = force base model; any other
        # string = select that preloaded adapter. Server serializes swaps via
        # gpu_sem so instances don't need to coordinate.
        self.adapter = adapter

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Ensure tools are in OpenAI function-calling format."""
        converted = []
        for t in tools:
            if "type" in t and t["type"] == "function":
                converted.append(t)
            else:
                converted.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {}),
                    },
                })
        return converted

    async def generate(self, messages: list[dict[str, str]],
                       tools: list[dict] | None = None,
                       force_tool: str | None = None,
                       enable_thinking: bool = True) -> LLMResponse:
        """Generate with retry logic and exponential backoff.

        force_tool: when set, forces the model to emit a tool_call for this
        specific tool name (used for deliver-gate intervention — #14 fix).

        enable_thinking: Qwen3.6 thinking mode. On (default) for planning
        turns where the model benefits from reasoning before emitting a
        tool call. Off for coding turns (file_write / file_edit against an
        existing scaffold) where the model just needs to emit the tool call
        quickly — thinking on mid-complexity coding adds 150-200s per turn
        that blows the budget. Agent.py flips this per-turn based on
        whether scaffolding has occurred yet.
        """
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._call(
                    messages, tools,
                    force_tool=force_tool,
                    enable_thinking=enable_thinking,
                )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                last_error = e
                wait = get_retry_delay(attempt)
                log.warning(f"Model call failed (attempt {attempt+1}/{MAX_RETRIES}): {e}. Retrying in {wait:.1f}s...")
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 500, 502, 503, 504):
                    last_error = e
                    retry_after = e.response.headers.get("retry-after") if status == 429 else None
                    wait = get_retry_delay(attempt, retry_after=retry_after)
                    log.warning(f"Server error {status} (attempt {attempt+1}/{MAX_RETRIES}). Retrying in {wait:.1f}s...")
                    await asyncio.sleep(wait)
                else:
                    raise
            except json.JSONDecodeError as e:
                last_error = e
                wait = get_retry_delay(attempt)
                log.warning(f"Invalid JSON from model (attempt {attempt+1}): {e}")
                await asyncio.sleep(wait)

        raise ConnectionError(f"Model unreachable after {MAX_RETRIES} attempts: {last_error}")

    async def _call(self, messages, tools=None, force_tool: str | None = None,
                    enable_thinking: bool = True) -> LLMResponse:
        headers = {"Content-Type": "application/json"}

        # Mode-aware sampling per the Qwen3.6 model card. Thinking turns
        # get the "Thinking / general" preset; non-thinking turns keep
        # the "Thinking / precise coding" instance defaults.
        #
        #   Thinking / general        : temp=1.0 top_p=0.95 presence=1.5
        #   Thinking / precise coding : temp=0.6 top_p=0.95 presence=0.0
        #
        # Caller overrides (temp<0.5 or presence<0.05) skip the bump so
        # deterministic harnesses + unit tests don't get re-randomized.
        if enable_thinking and self.temperature >= 0.5 and self.presence_penalty < 1.0:
            effective_temp = 1.0
            effective_top_p = 0.95
            effective_presence = 1.5
        else:
            effective_temp = self.temperature
            effective_top_p = self.top_p
            effective_presence = self.presence_penalty

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": effective_temp,
            "max_tokens": self.max_tokens,
            "top_p": effective_top_p,
            "top_k": self.top_k,
            "min_p": self.min_p,
            "presence_penalty": effective_presence,
            "repetition_penalty": self.repetition_penalty,
            # Qwen3.6 README — Thinking mode / Precise Coding recommends BOTH:
            #   enable_thinking      — default on for planning; off for
            #                          coding turns (caller controls this
            #                          per-turn via the generate() arg).
            #   preserve_thinking=True — keeps reasoning from prior turns so
            #                          multi-turn tool sessions don't lose
            #                          the agent's mental state mid-chain.
            # Both top-level (qwen36 ChatRequest field) AND chat_template_kwargs
            # are set because different inference paths consume different
            # fields. extra="allow" on the proxy lets top-level pass through.
            "enable_thinking": enable_thinking,
            "chat_template_kwargs": {
                "enable_thinking": enable_thinking,
                "preserve_thinking": True,
            },
        }
        if self.client_id:
            payload["user"] = self.client_id
        if self.adapter:
            payload["adapter"] = self.adapter
        if tools:
            payload["tools"] = self._convert_tools(tools)
            if force_tool:
                # #14 deliver-gate — force a specific tool call (e.g.,
                # message_result after BUILD PASSED to break the rebuild loop).
                payload["tool_choice"] = {
                    "type": "function",
                    "function": {"name": force_tool},
                }
            else:
                payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=900) as client:
            for attempt in range(3):
                resp = await client.post(
                    f"{self.endpoint}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                # Retry-with-backoff on any 5xx. Halve max_tokens so the
                # next attempt fits in a smaller response window — one
                # of qwen-code's retry heuristics (utils/retry.ts) +
                # our own T2 grind finding: 502s mid-stream are usually
                # oversized-generation timeouts, not real server faults.
                if resp.status_code in (500, 502, 503, 504):
                    await asyncio.sleep(2 * (attempt + 1))
                    if payload["max_tokens"] > 512:
                        payload["max_tokens"] = payload["max_tokens"] // 2
                    continue
                if resp.status_code == 400 and payload["max_tokens"] > 512:
                    payload["max_tokens"] = payload["max_tokens"] // 2
                    continue
                break
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content", "") or ""
        tool_call = None

        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            func = tc["function"]
            args = func.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    import re as _re
                    # Truncated-JSON recovery. Common pattern with large writes
                    # (Gemma-4-26B on llama-server emits {"content": "6KB...",
                    # "path": "..."} — the content string overflows the
                    # tool-call buffer before `path` is written). Extract what
                    # we can; if path is missing the agent's path-inference
                    # guard (agent.py:1497) fills it from the active project.
                    path_m = _re.search(r'"path"\s*:\s*"([^"]+)"', args)
                    content_m = _re.search(r'"content"\s*:\s*"(.*)', args, _re.DOTALL)
                    recovered: dict = {}
                    if content_m:
                        raw_content = content_m.group(1)
                        raw_content = raw_content.rstrip().rstrip('}"').rstrip()
                        raw_content = raw_content.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                        recovered["content"] = raw_content
                    if path_m:
                        recovered["path"] = path_m.group(1)
                    if recovered:
                        log.info(
                            f"Recovered malformed JSON args: "
                            f"{'path=' + recovered['path'] + ' ' if 'path' in recovered else ''}"
                            f"{'content_len=' + str(len(recovered['content'])) if 'content' in recovered else ''}"
                        )
                        args = recovered
                    else:
                        log.warning(f"Failed to parse tool args JSON: {args[:200]}")
                        args = {}
            if isinstance(args, dict) and "arguments" in args and len(args) == 1:
                args = args["arguments"]
            tool_call = ToolCall(name=func["name"], arguments=args)

        # Fallback: extract tool call from text content
        if tool_call is None and content:
            tool_call = _extract_tool_call(content)
            if tool_call:
                log.info(f"Extracted text-mode tool call from content: {tool_call.name}")

        return LLMResponse(content=content, tool_call=tool_call, raw=data)


def _extract_tool_call(text: str):
    """Extract a tool call JSON from text. Uses json.loads with progressive end search."""
    idx = text.find('"name"')
    if idx == -1:
        return None
    start = text.rfind('{', 0, idx)
    if start == -1:
        return None
    for end in range(start + 10, len(text) + 1):
        if text[end - 1] != '}':
            continue
        candidate = text[start:end]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and "name" in obj:
                args = obj.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                return ToolCall(name=obj["name"], arguments=args if isinstance(args, dict) else {})
        except json.JSONDecodeError:
            continue

    # Recovery: model truncated the JSON before closing all braces (common when
    # <turn|> token fires mid-emission). Count outstanding opens and try appending closes.
    candidate = text[start:]
    opens = closes = 0
    in_str = esc = False
    for c in candidate:
        if esc:
            esc = False
            continue
        if in_str:
            if c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                opens += 1
            elif c == '}':
                closes += 1
    deficit = opens - closes
    if 0 < deficit <= 5 and not in_str:
        try:
            obj = json.loads(candidate + '}' * deficit)
            if isinstance(obj, dict) and "name" in obj:
                args = obj.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                log.warning(f"Repaired truncated tool-call JSON (added {deficit} '}}'): name={obj['name']}")
                return ToolCall(name=obj["name"], arguments=args if isinstance(args, dict) else {})
        except json.JSONDecodeError:
            pass
    return None


# Backwards compat aliases — agent.py imports these
LLMModel = TsunamiModel
OpenAICompatModel = TsunamiModel


def create_model(backend: str = "api", model_name: str = "tsunami",
                 endpoint: str = "http://localhost:8090",
                 api_key: str | None = None, **kwargs) -> TsunamiModel:
    """Create the model. Backend arg is ignored — always uses serve_transformers.py."""
    return TsunamiModel(model=model_name, endpoint=endpoint, **kwargs)
