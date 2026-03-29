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

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]  # seconds between retries


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
        """Generate with retry logic. Retries on connection/timeout errors."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._call(messages, tools)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                last_error = e
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                log.warning(f"Model call failed (attempt {attempt+1}/{MAX_RETRIES}): {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 502, 503, 504):
                    last_error = e
                    wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                    log.warning(f"Server error {e.response.status_code} (attempt {attempt+1}). Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise  # non-retryable HTTP error
            except json.JSONDecodeError as e:
                last_error = e
                log.warning(f"Invalid JSON from model (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)

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
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=900) as client:
            resp = await client.post(
                f"{self.endpoint}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
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
                args = json.loads(args)
            tool_call = ToolCall(name=func["name"], arguments=args)

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
            parts.insert(1, f'<|im_start|>user\nRespond with exactly one JSON tool call. Format:\n{{"name": "tool_name", "arguments": {{"param": "value"}}}}\n\nTools:\n{tool_block}<|im_end|>\n')

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
            "stop": ["<|user|>", "<|system|>", "<|end|>"],
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

        # Try to parse tool call from response — find JSON with "name" and "arguments"
        try:
            # Find any JSON object that has "name" and "arguments"
            # Use greedy matching for arguments since they can contain nested braces
            for match in re.finditer(r'\{[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*"arguments"\s*:\s*\{', content):
                start = match.start()
                # Find the matching closing brace for arguments
                depth = 0
                i = content.index('"arguments"', start)
                i = content.index('{', i)
                for j in range(i, len(content)):
                    if content[j] == '{': depth += 1
                    elif content[j] == '}': depth -= 1
                    if depth == 0:
                        # Find the outer closing brace
                        end = content.index('}', j + 1) + 1 if j + 1 < len(content) and '}' in content[j+1:] else j + 1
                        try:
                            tc_json = json.loads(content[start:end])
                            tool_call = ToolCall(
                                name=tc_json["name"],
                                arguments=tc_json["arguments"] if isinstance(tc_json["arguments"], dict) else json.loads(tc_json["arguments"]),
                            )
                            content = content[:start].strip()
                            break
                        except (json.JSONDecodeError, KeyError):
                            # Try with just the inner part
                            try:
                                args_str = content[i:j+1]
                                name_match = re.search(r'"name"\s*:\s*"(\w+)"', content[start:])
                                if name_match:
                                    tool_call = ToolCall(
                                        name=name_match.group(1),
                                        arguments=json.loads(args_str),
                                    )
                                    content = content[:start].strip()
                                    break
                            except (json.JSONDecodeError, KeyError):
                                pass
                        break
        except (ValueError, IndexError):
            pass

        # Clean up any remaining thinking/reasoning text
        content = re.sub(r'^\s*I need to.*?(?=\n\n|\Z)', '', content, flags=re.DOTALL).strip()

        return LLMResponse(content=content, tool_call=tool_call, raw=data)


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
