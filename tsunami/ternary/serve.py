"""Ternary model server — serve Gemma 4 31B in ternary with OpenAI-compatible API.

No llama.cpp. No GGUF. Pure Python + PyTorch.
Load the ternary-quantized model and serve it with a minimal HTTP API.

Usage:
    python -m tsunami.ternary.serve \
        --model models/gemma-4-31B-it \
        --port 8090 \
        --group-size 128
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

log = logging.getLogger("tsunami.ternary.serve")


def create_handler(model, tokenizer, model_name: str = "gemma-4-31B-ternary"):
    """Create an HTTP request handler with OpenAI-compatible endpoints."""
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/v1/models":
                self._json_response({
                    "object": "list",
                    "data": [{
                        "id": model_name,
                        "object": "model",
                        "owned_by": "tsunami",
                    }],
                })
            elif self.path == "/health":
                self._json_response({"status": "ok"})
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/v1/chat/completions":
                content_len = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(content_len))
                response = generate_chat(model, tokenizer, body)
                self._json_response(response)
            else:
                self.send_error(404)

        def _json_response(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            log.info("[serve] " + (fmt % args))

    return Handler


def generate_chat(model, tokenizer, request: dict) -> dict:
    """Generate a chat completion."""
    import torch

    messages = request.get("messages", [])
    max_tokens = request.get("max_tokens", 2048)
    temperature = request.get("temperature", 0.7)

    # Format messages using chat template
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    # Tokenize
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]

    # Generate
    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=max(temperature, 0.01),
            do_sample=temperature > 0,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )

    # Decode only new tokens
    new_tokens = outputs[0][input_len:]
    response_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    gen_time = time.time() - t0
    gen_tokens = len(new_tokens)

    log.info(f"Generated {gen_tokens} tokens in {gen_time:.1f}s ({gen_tokens/gen_time:.1f} tok/s)")

    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "gemma-4-31B-ternary",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": input_len,
            "completion_tokens": gen_tokens,
            "total_tokens": input_len + gen_tokens,
        },
        "timings": {
            "total": gen_time,
            "tokens_per_second": gen_tokens / max(gen_time, 0.001),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Serve ternary Gemma 4 31B")
    parser.add_argument("--model", type=str, required=True, help="Model path")
    parser.add_argument("--port", type=int, default=8090, help="Server port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    parser.add_argument("--group-size", type=int, default=128, help="Ternary group size")
    parser.add_argument("--quantize", action="store_true", help="Quantize on load")
    parser.add_argument("--no-quantize", action="store_true", help="Load fp16 without quantization")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    log.info(f"Loading tokenizer from {args.model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.quantize and not args.no_quantize:
        log.info("Loading and quantizing to ternary...")
        from .quantize import quantize_model
        model, stats = quantize_model(args.model, group_size=args.group_size)
        log.info(f"Quantized {len(stats)} layers")
    else:
        log.info(f"Loading model from {args.model}...")
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )

    model_device = next(model.parameters()).device
    log.info(f"Model loaded. Device: {model_device}")

    # Serve
    from http.server import HTTPServer
    handler = create_handler(model, tokenizer)
    server = HTTPServer((args.host, args.port), handler)
    log.info(f"Serving on http://{args.host}:{args.port}")
    log.info(f"  /v1/models — model list")
    log.info(f"  /v1/chat/completions — chat API")
    log.info(f"  /health — health check")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
