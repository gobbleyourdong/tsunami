"""LLM abstraction layer — the reasoning core.

Supports Ollama, vLLM (OpenAI-compat), and any OpenAI-compatible API.
All backends normalize to a single response format with exactly one tool call.
Includes retry logic with exponential backoff for resilience.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("tsunami.model")

# Retry configuration (ts)
MAX_RETRIES = 5
BASE_DELAY_MS = 500
MAX_DELAY_MS = 32_000  # 32 seconds cap


def get_retry_delay(attempt: int, retry_after: str | None = None, max_delay_ms: int = MAX_DELAY_MS) -> float:
    """Exponential backoff with jitter .

    Returns delay in seconds.
    - Respects Retry-After header when present
    - Exponential: 0.5s, 1s, 2s, 4s, 8s... capped at max_delay_ms
    - Jitter: adds 0-25% random noise to prevent thundering herd
    """
    import random

    # Retry-After header takes priority
    if retry_after:
        try:
            return int(retry_after)  # already in seconds
        except (ValueError, TypeError):
            pass

    base_delay = min(BASE_DELAY_MS * (2 ** attempt), max_delay_ms)
    jitter = random.random() * 0.25 * base_delay
    return (base_delay + jitter) / 1000  # convert ms → seconds


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str  # reasoning text (may be empty)
    tool_call: ToolCall | None = None
    raw: dict | None = None


class LLMModel(ABC):
    """Abstract interface for the reasoning core."""

    @abstractmethod
    async def _call(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        ...

    async def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate with retry logic and exponential backoff.

        ts:
        - Exponential backoff with jitter (no thundering herd)
        - Respects Retry-After headers on 429
        - Retries on connection, timeout, 429, 5xx errors
        - Non-retryable errors (400, 401, 403) raise immediately
        """
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
                    # Extract Retry-After header for 429s
                    retry_after = e.response.headers.get("retry-after") if status == 429 else None
                    wait = get_retry_delay(attempt, retry_after=retry_after)
                    log.warning(f"Server error {status} (attempt {attempt+1}/{MAX_RETRIES}). Retrying in {wait:.1f}s...")
                    await asyncio.sleep(wait)
                else:
                    raise  # non-retryable HTTP error (400, 401, 403, etc.)
            except json.JSONDecodeError as e:
                last_error = e
                wait = get_retry_delay(attempt)
                log.warning(f"Invalid JSON from model (attempt {attempt+1}): {e}")
                await asyncio.sleep(wait)

        raise ConnectionError(f"Model unreachable after {MAX_RETRIES} attempts: {last_error}")


class OllamaModel(LLMModel):
    """Ollama backend — local models via HTTP."""

    def __init__(self, model: str, endpoint: str = "http://localhost:11434",
                 temperature: float = 0.7, max_tokens: int = 2048,
                 top_p: float = 0.8, top_k: int = 20, presence_penalty: float = 1.5,
                 **kwargs):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k

    async def _call(self, messages, tools=None) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "top_p": self.top_p,
                "top_k": self.top_k,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=900) as client:
            resp = await client.post(f"{self.endpoint}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        content = msg.get("content", "")
        tool_call = None

        tool_calls = msg.get("tool_calls")
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]  # enforce single tool call
            func = tc.get("function", {})
            tool_call = ToolCall(
                name=func.get("name", ""),
                arguments=func.get("arguments", {}),
            )

        # Fallback: some models (e.g. 31B) emit tool calls as text in content
        if tool_call is None and content:
            tool_call = CompletionModel._extract_tool_call(content)
            if tool_call:
                log.info(f"Extracted text-mode tool call from content: {tool_call.name}")

        return LLMResponse(content=content, tool_call=tool_call, raw=data)


class OpenAICompatModel(LLMModel):
    """OpenAI-compatible API backend — works with vLLM, OpenAI, Together, Groq, etc."""

    def __init__(self, model: str, endpoint: str, api_key: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2048,
                 top_p: float = 0.8, top_k: int = 20, presence_penalty: float = 1.5,
                 **kwargs):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key or "not-needed"
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

    async def _call(self, messages, tools=None) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
            payload["tool_choice"] = "auto"  # "required" causes 500s on 9B with large schemas

        async with httpx.AsyncClient(timeout=900) as client:
            for attempt in range(3):
                resp = await client.post(
                    f"{self.endpoint}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code == 500:
                    # Server busy or generation failed — wait then retry
                    # (parallel=1 means only one request at a time)
                    await asyncio.sleep(2 * (attempt + 1))
                    if payload["max_tokens"] > 512:
                        payload["max_tokens"] = payload["max_tokens"] // 2
                    continue
                if resp.status_code == 400 and payload["max_tokens"] > 512:
                    # Context overflow — halve and retry
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
                    log.warning(f"Failed to parse tool args JSON: {args[:200]}")
                    args = {}
            # Handle Gemma 4 sometimes nesting args under "arguments"
            if isinstance(args, dict) and "arguments" in args and len(args) == 1:
                args = args["arguments"]
            tool_call = ToolCall(name=func["name"], arguments=args)

        # Fallback: some models (e.g. 31B) emit tool calls as text in content
        if tool_call is None and content:
            tool_call = CompletionModel._extract_tool_call(content)
            if tool_call:
                log.info(f"Extracted text-mode tool call from content: {tool_call.name}")

        return LLMResponse(content=content, tool_call=tool_call, raw=data)


class CompletionModel(LLMModel):
    """Raw completion endpoint — no chat template, no Jinja, no template errors.

    Formats the prompt manually and uses /completion instead of /v1/chat/completions.
    Works with any llama-server regardless of chat template issues.
    """

    def __init__(self, model: str, endpoint: str, api_key: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2048,
                 top_p: float = 0.8, top_k: int = 20, presence_penalty: float = 1.5,
                 **kwargs):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.presence_penalty = presence_penalty

    def _format_prompt(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """Format messages into Qwen3.5 chat template."""
        parts = []
        for m in messages:
            role = m["role"].lower()
            # Qwen3.5 doesn't have a "tool" role — map to "user"
            if role in ("tool", "tool_result"):
                role = "user"
            content = m.get("content", "")
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")

        if tools:
            tool_lines = []
            for t in tools:
                if t.get("type") != "function":
                    continue
                f = t["function"]
                params = f.get("parameters", {}).get("properties", {})
                required = f.get("parameters", {}).get("required", [])
                param_desc = ", ".join(
                    f'{k} ({"required" if k in required else "optional"}): {v.get("description", v.get("type", ""))}'
                    for k, v in params.items()
                )
                tool_lines.append(f'- {f["name"]}({param_desc}): {f["description"]}')
            tool_block = "\n".join(tool_lines)
            parts.insert(1, f'<|im_start|>user\nRespond with exactly one JSON tool call. Format:\n{{"name": "tool_name", "arguments": {{"param": "value"}}}}\n\nExample:\n{{"name": "file_write", "arguments": {{"path": "workspace/deliverables/test/hello.py", "content": "print(\'hello\')"}}}}\n\nTools:\n{tool_block}<|im_end|>\n')

        parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    async def _call(self, messages, tools=None) -> LLMResponse:
        prompt = self._format_prompt(messages, tools)

        payload = {
            "prompt": prompt,
            "temperature": self.temperature,
            "n_predict": self.max_tokens,
            "top_p": self.top_p,
            "presence_penalty": self.presence_penalty,
            "stop": ["<|im_start|>", "<|im_end|>", "<|endoftext|>"],
        }

        async with httpx.AsyncClient(timeout=900) as client:
            resp = await client.post(
                f"{self.endpoint}/completion",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data.get("content", "")
        tool_call = None

        import re

        # Strip <think>...</think> blocks (Qwen3.5 reasoning)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # Strip markdown code fences that wrap JSON
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)
        content = content.strip()

        # Strategy: find the outermost { } that contains "name" and parse it
        tool_call = self._extract_tool_call(content)
        if tool_call:
            # Remove the tool call JSON from content
            content = re.sub(r'\{[^{}]*"name".*', '', content, flags=re.DOTALL).strip()

        return LLMResponse(content=content, tool_call=tool_call, raw=data)

    @staticmethod
    def _extract_tool_call(text: str):
        """Extract a tool call JSON from text. Uses json.loads with progressive end search."""
        import json

        # Find the start of a JSON object containing "name"
        idx = text.find('"name"')
        if idx == -1:
            return None

        # Walk backwards to find the opening brace
        start = text.rfind('{', 0, idx)
        if start == -1:
            return None

        # Try parsing from start, extending end progressively
        # json.loads handles nested braces inside strings correctly
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
        return None


def create_model(backend: str, model_name: str, endpoint: str,
                 api_key: str | None = None, **kwargs) -> LLMModel:
    """Factory function to create the appropriate model backend."""
    if backend == "ollama":
        return OllamaModel(model=model_name, endpoint=endpoint, **kwargs)
    elif backend in ("vllm", "api", "openai"):
        return OpenAICompatModel(
            model=model_name, endpoint=endpoint, api_key=api_key, **kwargs
        )
    elif backend == "completion":
        return CompletionModel(
            model=model_name, endpoint=endpoint, api_key=api_key, **kwargs
        )
    else:
        raise ValueError(f"Unknown model backend: {backend}")
