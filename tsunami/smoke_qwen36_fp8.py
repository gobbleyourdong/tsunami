#!/usr/bin/env python3
"""Smoke test for serve_qwen36_fp8.py — /health + /v1/chat/completions."""
import argparse
import json
import sys
import time
import urllib.request


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def _post(url: str, body: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8095)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()

    base = f"http://{args.host}:{args.port}"
    print(f"[health] GET {base}/health")
    h = _get(f"{base}/health")
    print(json.dumps(h, indent=2))
    assert h.get("model_loaded"), "model not loaded"

    body = {
        "model": "qwen3.5-27b-fp8",
        "messages": [
            {"role": "user", "content": "Say 'ready' if you can read this, then count 1 to 5."},
        ],
        "max_tokens": 64,
        "temperature": 0.0,
        "user": "smoke",
    }
    t0 = time.time()
    print(f"[chat] POST {base}/v1/chat/completions")
    resp = _post(f"{base}/v1/chat/completions", body)
    dt = time.time() - t0
    print(json.dumps(resp, indent=2))
    content = resp["choices"][0]["message"]["content"]
    print(f"\n[ok] {dt:.1f}s, {resp['usage']['completion_tokens']} tok, "
          f"content={content[:120]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
