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

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    start = time.time()

    # Normalize messages — processor expects list content for multimodal
    messages = []
    images = []
    for msg in req.messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            # Text-only: wrap in list format for processor
            messages.append({"role": msg["role"], "content": [{"type": "text", "text": content}]})
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
            messages.append({"role": msg["role"], "content": parts})
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
    tool_calls = None
    content = text

    # Check for tool call tokens: <|tool_call>call:name{args}<tool_call|>
    import re
    tc_matches = re.findall(r'<\|tool_call>call:(\w+)\{(.*?)\}<tool_call\|>', text, re.DOTALL)
    if tc_matches:
        tool_calls = []
        for name, args_str in tc_matches:
            # Parse key:value pairs from the args
            args = {}
            for kv in re.findall(r'(\w+):<\|"\|>(.*?)<\|"\|>', args_str, re.DOTALL):
                args[kv[0]] = kv[1]
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
