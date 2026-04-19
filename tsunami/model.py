"""LLM model — talks to serve_transformers.py on port 8090.

Single model, single endpoint, no backend abstraction.
Includes retry logic with exponential backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
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
    # When the model emits multiple <tool_call> blocks in one response
    # (Qwen3.6 does this for "research these files" style turns), the
    # full list lives here. `tool_call` is the first for back-compat
    # with every call site; batch-capable handlers use `tool_calls`.
    tool_calls: list[ToolCall] = field(default_factory=list)


class TsunamiModel:
    """Talks to serve_transformers.py via OpenAI-compatible /v1/chat/completions."""

    def __init__(self, model: str = "tsunami", endpoint: str = "http://localhost:8090",
                 temperature: float = 0.6, max_tokens: int = 81920,
                 top_p: float = 0.95, top_k: int = 20,
                 min_p: float = 0.0,
                 presence_penalty: float = 0.0,
                 repetition_penalty: float = 1.0,
                 preserve_thinking: bool = True,
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
        # Qwen3.6 preserve_thinking: wave=True (keeps reasoning across turns,
        # paired with scaffold-edit compact-history mode where only the last
        # 2 pairs are kept verbatim — preserving their <think> blocks gives
        # continuity without bloating context). Eddies bypass TsunamiModel
        # entirely so they naturally stay at server default False.
        self.preserve_thinking = preserve_thinking
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
        # Caller overrides skip the bump so deterministic harnesses + unit
        # tests don't get re-randomized. Opt-out condition (matches the check
        # below): temperature<0.5 OR presence_penalty>=1.0.
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
            #   preserve_thinking=True — keeps <think> blocks from prior turns
            #                          so multi-turn tool sessions don't lose
            #                          the agent's mental state mid-chain.
            # Both top-level (qwen36 ChatRequest field) AND chat_template_kwargs
            # are set because different inference paths consume different
            # fields — serve_qwen36_fp8.py reads top-level via Pydantic,
            # vLLM/SGLang read chat_template_kwargs. extra="allow" on the
            # proxy lets top-level pass through.
            "enable_thinking": enable_thinking,
            "preserve_thinking": self.preserve_thinking,
            "chat_template_kwargs": {
                "enable_thinking": enable_thinking,
                "preserve_thinking": self.preserve_thinking,
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

        # Opt-in trace of the exact outgoing payload. Enable by setting
        # TSUNAMI_TRACE=1 in the env; writes one JSONL record per call to
        # /tmp/prompt_trace.jsonl. Mirrors the FastAPI middleware but fires
        # at the client side so we can debug prompt drift without restarting
        # the server.
        import os as _os
        if _os.environ.get("TSUNAMI_TRACE") == "1":
            try:
                import time as _t
                msgs = payload.get("messages", [])
                text_bytes = 0
                img_count = 0
                for m in msgs:
                    c = m.get("content", "")
                    if isinstance(c, list):
                        for p in c:
                            if p.get("type") == "image_url":
                                img_count += 1
                            elif p.get("type") == "text":
                                text_bytes += len(p.get("text", ""))
                    elif isinstance(c, str):
                        text_bytes += len(c)
                rec = {
                    "ts": _t.time(),
                    "msg_count": len(msgs),
                    "text_bytes": text_bytes,
                    "img_count": img_count,
                    "tool_count": len(payload.get("tools", []) or []),
                    "max_tokens": payload.get("max_tokens"),
                    "enable_thinking": payload.get("enable_thinking"),
                    "messages": msgs,
                    "tools_names": [t.get("function", t).get("name", "?")
                                    for t in (payload.get("tools") or [])][:30],
                    "force_tool": force_tool,
                }
                with open("/tmp/prompt_trace.jsonl", "a") as _f:
                    _f.write(json.dumps(rec, default=str) + "\n")
            except Exception:
                pass

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

        # Parse ALL tool_calls the model emitted. Qwen3.6 routinely batches
        # 3-4 file_reads in a single turn; we used to drop everything after
        # [0], burning a full round-trip per extra call. Now callers get
        # the whole list and can execute them sequentially in one iter.
        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls", []) or []:
            parsed = _parse_tool_call_dict(tc)
            if parsed is not None:
                tool_calls.append(parsed)

        # Fallback: extract tool call(s) from text content
        if not tool_calls and content:
            parsed = _extract_tool_call(content)
            if parsed:
                tool_calls.append(parsed)
                log.info(f"Extracted text-mode tool call from content: {parsed.name}")

        tool_call = tool_calls[0] if tool_calls else None
        return LLMResponse(content=content, tool_call=tool_call,
                           tool_calls=tool_calls, raw=data)


def _parse_tool_call_dict(tc: dict) -> ToolCall | None:
    """Extract a ToolCall from one OpenAI-format tool_call dict. Handles
    string-JSON arguments, truncated-JSON recovery, and the Qwen3.6
    double-wrap `{"arguments": {...}}` idiom. Returns None on total failure.
    """
    try:
        func = tc.get("function", tc)
        name = func.get("name", "")
        if not name:
            return None
        args = func.get("arguments", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                import re as _re
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
        return ToolCall(name=name, arguments=args if isinstance(args, dict) else {})
    except Exception as e:
        log.warning(f"Tool call parse error: {e}")
        return None


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
                # Salvage drone JSON-key variants of XML-style parameters:
                #   (a) `{"parameter_path": X, "parameter_content": Y}` —
                #       multiple top-level keys prefixed with parameter_
                #   (b) `{"parameter": {"path": X, "content": Y}}` —
                #       singular parameter key holding the real arg dict
                if isinstance(args, dict) and not args:
                    pkeys = {k[len("parameter_"):]: v
                             for k, v in obj.items()
                             if k.startswith("parameter_")}
                    if pkeys:
                        args = pkeys
                    elif isinstance(obj.get("parameter"), dict):
                        args = obj["parameter"]
                    elif isinstance(obj.get("parameters"), dict):
                        args = obj["parameters"]
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
                # Same salvage as the main path — drones use parameter_X,
                # parameter, or parameters keys instead of `arguments`.
                if isinstance(args, dict) and not args:
                    pkeys = {k[len("parameter_"):]: v
                             for k, v in obj.items()
                             if k.startswith("parameter_")}
                    if pkeys:
                        args = pkeys
                    elif isinstance(obj.get("parameter"), dict):
                        args = obj["parameter"]
                    elif isinstance(obj.get("parameters"), dict):
                        args = obj["parameters"]
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
