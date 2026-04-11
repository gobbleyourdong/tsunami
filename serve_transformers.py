#!/usr/bin/env python3
"""Serve Tsunami model via transformers — text + vision support.

Usage (inside nvcr.io/nvidia/pytorch container):
  python3 serve_transformers.py --model models/gemma-4-e4b-tsunami-v81r-merged --port 8090

Provides OpenAI-compatible /v1/chat/completions endpoint.
Supports both text-only and multimodal (image) requests.
"""
import argparse
import base64
import io
import json
import logging
import time
import uuid
from pathlib import Path

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoProcessor, AutoModelForImageTextToText
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("serve")

app = FastAPI()
model = None
processor = None

class ChatRequest(BaseModel):
    model: str = "tsunami"
    messages: list
    tools: list = []
    tool_choice: str = "auto"
    max_tokens: int = 2048
    temperature: float = 0.3
    top_p: float = 0.95
    top_k: int = 64

@app.get("/health")
def health():
    return {"status": "ok"}

import re

def _parse_gemma_args(args_str: str) -> dict:
    """Parse tool call arguments — handles both Gemma native AND JSON formats.

    Gemma native:  key:<|"|>value<|"|>, key:true, key:[<|"|>a<|"|>]
    JSON:          {"key": "value", "key2": true}

    The model sometimes outputs JSON args inside native tool_call tags,
    so we detect and handle both formats.
    """
    # Try JSON first — if it starts with { and is valid JSON, use that
    stripped = args_str.strip()
    if stripped.startswith('{'):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
    # Also try if the whole string is JSON without braces (unlikely but safe)
    if stripped.startswith('"') and ':' not in stripped[:20].replace('":"', ''):
        try:
            return json.loads('{' + stripped + '}')
        except (json.JSONDecodeError, ValueError):
            pass

    # Fall through to Gemma native parser
    args = {}
    i = 0
    n = len(args_str)

    while i < n:
        # Skip commas and whitespace between key:value pairs
        while i < n and args_str[i] in (',', ' ', '\n'):
            i += 1
        if i >= n:
            break

        # Read key (word characters)
        key_start = i
        while i < n and (args_str[i].isalnum() or args_str[i] == '_'):
            i += 1
        key = args_str[key_start:i]
        if not key:
            i += 1  # skip unrecognized char
            continue

        # Expect colon
        if i < n and args_str[i] == ':':
            i += 1
        else:
            continue

        # Parse value based on what follows
        if args_str[i:i+5] == '<|"|>':
            # String value
            val, i = _read_string(args_str, i)
            args[key] = val
        elif args_str[i] == '[':
            # Array value
            val, i = _read_array(args_str, i)
            args[key] = val
        elif args_str[i] == '{':
            # Nested object — read until matching }
            val, i = _read_object(args_str, i)
            args[key] = val
        elif args_str[i:i+4] == 'true':
            args[key] = True
            i += 4
        elif args_str[i:i+5] == 'false':
            args[key] = False
            i += 5
        elif args_str[i:i+4] == 'null':
            args[key] = None
            i += 4
        else:
            # Number or unknown — read until comma or end
            val_start = i
            while i < n and args_str[i] not in (',', '}', ']'):
                i += 1
            val_str = args_str[val_start:i].strip()
            try:
                args[key] = int(val_str)
            except ValueError:
                try:
                    args[key] = float(val_str)
                except ValueError:
                    args[key] = val_str  # keep as string

    return args


def _read_string(s: str, i: int) -> tuple:
    """Read a <|"|>...<|"|> quoted string starting at position i."""
    assert s[i:i+5] == '<|"|>', f"Expected <|\"|> at {i}, got {s[i:i+10]}"
    i += 5  # skip opening <|"|>
    start = i
    while i < len(s):
        if s[i:i+5] == '<|"|>':
            val = s[start:i]
            return val, i + 5  # skip closing <|"|>
        i += 1
    return s[start:], i  # unclosed string


def _read_array(s: str, i: int) -> tuple:
    """Read a [...] array starting at position i."""
    assert s[i] == '['
    i += 1  # skip [
    items = []
    while i < len(s):
        # Skip whitespace and commas
        while i < len(s) and s[i] in (',', ' ', '\n'):
            i += 1
        if i >= len(s) or s[i] == ']':
            i += 1  # skip ]
            return items, i
        # Read item
        if s[i:i+5] == '<|"|>':
            val, i = _read_string(s, i)
            items.append(val)
        elif s[i] == '{':
            val, i = _read_object(s, i)
            items.append(val)
        elif s[i] == '[':
            val, i = _read_array(s, i)
            items.append(val)
        elif s[i:i+4] == 'true':
            items.append(True); i += 4
        elif s[i:i+5] == 'false':
            items.append(False); i += 5
        else:
            # Number
            start = i
            while i < len(s) and s[i] not in (',', ']', '}'):
                i += 1
            val_str = s[start:i].strip()
            try:
                items.append(int(val_str))
            except ValueError:
                try:
                    items.append(float(val_str))
                except ValueError:
                    items.append(val_str)
    return items, i


def _read_object(s: str, i: int) -> tuple:
    """Read a {...} object starting at position i."""
    assert s[i] == '{'
    # Find matching closing brace (handle nesting)
    depth = 1
    start = i
    i += 1
    while i < len(s) and depth > 0:
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    inner = s[start+1:i-1]
    return _parse_gemma_args(inner), i


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    start = time.time()

    # Normalize messages — preserve tool_calls/tool roles for multi-turn,
    # convert image_url to PIL for multimodal
    messages = []
    images = []
    for msg in req.messages:
        role = msg.get("role", "user")

        # Tool response messages — pass through with tool_call_id, wrap content
        if role == "tool":
            content_text = msg.get("content", "") or ""
            out = {"role": "tool", "content": [{"type": "text", "text": content_text}]}
            if "tool_call_id" in msg:
                out["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg:
                out["name"] = msg["name"]
            messages.append(out)
            continue

        # Assistant messages with tool_calls — preserve them, wrap content as list
        if role == "assistant" and "tool_calls" in msg:
            content_text = msg.get("content", "") or ""
            out = {"role": "assistant", "content": [{"type": "text", "text": content_text}], "tool_calls": msg["tool_calls"]}
            messages.append(out)
            continue

        # Regular messages — normalize content for multimodal
        content = msg.get("content", "")
        if isinstance(content, str):
            messages.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        b64 = url.split(",", 1)[1]
                        from PIL import Image
                        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                        images.append(img)
                        parts.append({"type": "image", "image": img})
                else:
                    parts.append(part)
            messages.append({"role": role, "content": parts})
        else:
            messages.append(msg)

    # Apply chat template
    inputs = processor.apply_chat_template(
        messages,
        tools=req.tools if req.tools else None,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    # Bug #5 fix: Gemma4 template skips <|turn>model\n after tool_response
    # because tool responses are embedded in the model turn. But we need the
    # model to CONTINUE generating after seeing the tool result. Detect this
    # case and append the model turn tokens manually.
    input_ids = inputs["input_ids"]
    # Decode last ~20 tokens to check if we're missing the generation prompt
    tail = processor.decode(input_ids[0, -20:], skip_special_tokens=False)
    if '<tool_response|>' in tail and '<|turn>model' not in tail.split('<tool_response|>')[-1]:
        # Append <|turn>model\n tokens
        model_turn_tokens = processor.tokenizer.encode("<|turn>model\n", add_special_tokens=False)
        import torch as _torch
        model_turn_ids = _torch.tensor([model_turn_tokens], device=input_ids.device)
        inputs["input_ids"] = _torch.cat([input_ids, model_turn_ids], dim=1)
        if "attention_mask" in inputs:
            extra_mask = _torch.ones(1, len(model_turn_tokens), device=input_ids.device, dtype=inputs["attention_mask"].dtype)
            inputs["attention_mask"] = _torch.cat([inputs["attention_mask"], extra_mask], dim=1)

    prompt_len = inputs["input_ids"].shape[1]

    # Generate
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=req.max_tokens,
            use_cache=True,
            temperature=req.temperature if req.temperature > 0 else 1.0,
            top_p=req.top_p,
            top_k=req.top_k,
            do_sample=req.temperature > 0,
        )

    # Decode response
    new_tokens = output[0][prompt_len:]
    text = processor.decode(new_tokens, skip_special_tokens=False)

    # Parse tool calls from native format
    log.info(f"RAW OUTPUT: {text!r}")
    tool_calls = None
    content = text

    # Check for tool call tokens: <|tool_call>call:name{args}<tool_call|>
    # Model may use JSON double-brace {{...}} OR Gemma native {key:<|"|>val<|"|>}
    tc_matches = re.findall(
        r'<\|tool_call>call:(\w+)(\{\{.+?\}\}|\{.+?\})<tool_call\|>', text, re.DOTALL
    )
    if tc_matches:
        tool_calls = []
        for name, args_raw in tc_matches:
            # Strip double-brace wrapper: {{"k":"v"}} -> {"k":"v"}
            if args_raw.startswith('{{') and args_raw.endswith('}}'):
                inner = args_raw[1:-1]
            else:
                inner = args_raw

            # Try JSON parse first (model often uses standard JSON)
            try:
                args = json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                # Fall back to Gemma native format parser
                args = _parse_gemma_args(inner.strip('{}'))

            tool_calls.append({
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
                "id": uuid.uuid4().hex[:16],
            })
        content = ""

    # Clean up content
    content = re.sub(r'<\|.*?\|>', '', content).strip()
    if content.endswith("<turn|>"):
        content = content[:-7].strip()

    elapsed = time.time() - start
    completion_tokens = len(new_tokens)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            },
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_len,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_len + completion_tokens,
        },
    }


def main():
    global model, processor

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/gemma-4-e4b-tsunami-v80-merged")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    log.info(f"Loading {args.model}...")
    processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    log.info(f"Loaded on {model.device}. Starting server on port {args.port}...")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
