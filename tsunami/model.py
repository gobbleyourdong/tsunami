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
                 temperature: float = 0.7, max_tokens: int = 2048,
                 top_p: float = 0.8, top_k: int = 20, presence_penalty: float = 1.5,
                 **kwargs):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.presence_penalty = presence_penalty

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
                       tools: list[dict] | None = None) -> LLMResponse:
        """Generate with retry logic and exponential backoff."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._call(messages, tools)
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

    async def _call(self, messages, tools=None) -> LLMResponse:
        headers = {"Content-Type": "application/json"}

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "presence_penalty": self.presence_penalty,
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=900) as client:
            for attempt in range(3):
                resp = await client.post(
                    f"{self.endpoint}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code == 500:
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
                    path_m = _re.search(r'"path"\s*:\s*"([^"]+)"', args)
                    content_m = _re.search(r'"content"\s*:\s*"(.*)', args, _re.DOTALL)
                    if path_m and content_m:
                        raw_content = content_m.group(1)
                        raw_content = raw_content.rstrip().rstrip('}"').rstrip()
                        raw_content = raw_content.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                        args = {"path": path_m.group(1), "content": raw_content}
                        log.info(f"Recovered malformed JSON args: path={path_m.group(1)} content_len={len(raw_content)}")
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
