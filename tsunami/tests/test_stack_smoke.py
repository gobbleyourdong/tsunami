"""Stack smoke: generation through the tsunami proxy + undertow QA on a
trivial HTML page.

Run with: python3 -m tsunami.tests.test_stack_smoke
(or via pytest for assertion-based pass/fail)

Confirms the three-tier serving stack is wired correctly:
  :8090  tsunami proxy   (forwards /v1/chat → :8095, /v1/embeddings → :8093)
  :8092  ERNIE-Image     (health only — image-gen smoke is heavier, skipped)
  :8093  Qwen3-Embedding (last-token pool + L2 norm)
  :8095  Qwen3.6-27B     (dense BF16, multimodal — replaces 35B-A3B-FP8)

And confirms the undertow QA harness can pull playwright levers end-to-end.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Point undertow's eddy-compare at the same proxy we're smoke-testing. Default
# in undertow is :8091 which isn't in our stack (legacy eddy port).
os.environ.setdefault("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8090")
# Point riptide's VL fallback chain at the proxy too. Default chain checks
# :8091 (legacy VL) → :8092 (ERNIE, not chat) → :8090 (proxy) — the proxy
# answers, but setting TSUNAMI_MODEL_ENDPOINT makes intent explicit.
os.environ.setdefault("TSUNAMI_MODEL_ENDPOINT", "http://localhost:8090")

from tsunami.undertow import Lever, pull_levers
from tsunami.tools.riptide import Riptide


def _section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def check_health() -> dict:
    _section("1. Health check — 4 tiers")
    endpoints = {
        "proxy :8090":  ("http://localhost:8090/health",  "status"),
        "ernie :8092":  ("http://localhost:8092/healthz", "status"),
        "embed :8093":  ("http://localhost:8093/health",  "status"),
        "qwen36 :8095": ("http://localhost:8095/health",  "status"),
    }
    results = {}
    for name, (url, key) in endpoints.items():
        try:
            r = httpx.get(url, timeout=3.0)
            ok = r.status_code == 200 and r.json().get(key) == "ok"
            results[name] = ok
            tag = "✓" if ok else "✗"
            print(f"  {tag}  {name:<15}  {r.status_code}  {r.text[:100]}")
        except Exception as e:
            results[name] = False
            print(f"  ✗  {name:<15}  error: {e}")
    return results


def gen_chat_through_proxy() -> dict:
    _section("2. Generation — /v1/chat/completions via :8090 proxy")
    prompt = "What is 7 times 13? Answer with just the number."
    t0 = time.time()
    r = httpx.post(
        "http://localhost:8090/v1/chat/completions",
        json={
            "model": "Qwen/Qwen3.6-27B",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 32,
            "temperature": 0.0,
            # qwen36 ChatRequest takes enable_thinking as a top-level field.
            # Proxy forwards unknown fields (extra="allow") so this threads
            # through to the qwen36 server, suppresses thinking, and gets a
            # clean one-token answer.
            "enable_thinking": False,
        },
        timeout=120.0,
    )
    dt = time.time() - t0
    out = {
        "status": r.status_code,
        "latency_s": round(dt, 2),
        "ok": False,
        "content": "",
    }
    print(f"  status: {r.status_code}  latency: {dt:.2f}s")
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"]["content"]
        out["content"] = content
        out["ok"] = "91" in content or "ninety" in content.lower()
        tag = "✓" if out["ok"] else "✗"
        print(f"  {tag}  content: {content!r}")
    else:
        print(f"  ✗  body: {r.text[:300]}")
    return out


def embed_through_proxy() -> dict:
    _section("3. Embedding — /v1/embeddings via :8090 proxy")
    t0 = time.time()
    r = httpx.post(
        "http://localhost:8090/v1/embeddings",
        json={
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "input": ["the quick brown fox", "jumps over the lazy dog"],
        },
        timeout=30.0,
    )
    dt = time.time() - t0
    out = {"status": r.status_code, "latency_s": round(dt, 2), "ok": False, "dim": None}
    print(f"  status: {r.status_code}  latency: {dt:.2f}s")
    if r.status_code == 200:
        data = r.json()["data"]
        out["dim"] = len(data[0]["embedding"])
        out["n"] = len(data)
        out["ok"] = out["dim"] > 0 and out["n"] == 2
        tag = "✓" if out["ok"] else "✗"
        print(f"  {tag}  {out['n']} vectors, dim={out['dim']}")
    else:
        print(f"  ✗  body: {r.text[:300]}")
    return out


def undertow_qa() -> dict:
    _section("4. Undertow QA — pull levers on a trivial HTML page")
    # Write a tiny HTML page with elements the undertow will interact with.
    tmp = Path(tempfile.mkdtemp(prefix="stack_smoke_"))
    html_path = tmp / "index.html"
    html_path.write_text(
        "<!doctype html><html><head><meta charset=utf-8>"
        "<title>stack smoke</title></head><body>"
        "<h1 id=title>tsunami stack smoke</h1>"
        "<button id=go onclick='document.getElementById(\"out\").innerText=\"clicked\"'>go</button>"
        "<div id=out>not-yet</div>"
        "<script>console.log('smoke-ready');</script>"
        "</body></html>"
    )
    # Mix of expect=-free levers (mechanics) and one expect= lever that
    # exercises undertow._eddy_compare end-to-end (LLM call to the stack).
    # The expect= path was broken until we fixed qwen36's enable_thinking
    # wiring via the proxy in the same batch of fixes as this smoke update.
    levers = [
        Lever(action="read_text", selector="#title"),
        Lever(action="read_text", selector="#out"),
        Lever(action="click",     selector="#go"),
        Lever(action="read_text", selector="#out", expect="clicked"),
        Lever(action="console"),
    ]
    report = asyncio.get_event_loop().run_until_complete(
        pull_levers(str(html_path), levers)
    )
    tag = "✓" if report.passed else "✗"
    print(f"  {tag}  overall passed={report.passed}")
    for i, res in enumerate(report.results):
        ok = "✓" if res.passed else "✗"
        action = res.lever.action
        sel = res.lever.selector
        exp = res.lever.expect
        saw = (res.saw or "")[:60]
        print(f"    {ok}  [{i}] {action} {sel or ''} expect={exp!r} saw={saw!r}")
    if report.console_errors:
        print(f"  console errors: {report.console_errors[:3]}")
    if report.screenshot_path:
        print(f"  screenshot: {report.screenshot_path}")
    return {"passed": report.passed, "results": report.results}


def riptide_vision_grounding() -> dict:
    _section("5. Riptide — vision grounding via proxy → qwen36 VLM")
    # Draw a 512×512 image with a red circle (top-left) + blue square
    # (bottom-right). Tiny scene the VLM can reliably locate.
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (512, 512), color="white")
    d = ImageDraw.Draw(img)
    d.ellipse((50, 50, 200, 200), fill="red")
    d.rectangle((300, 300, 460, 460), fill="blue")
    tmp = Path(tempfile.mkdtemp(prefix="riptide_"))
    img_path = tmp / "scene.png"
    img.save(img_path)

    # Riptide inherits BaseTool(config: TsunamiConfig). The tool itself reads
    # VL_ENDPOINT from env, not from config, so a minimal stub suffices.
    class _StubConfig:
        pass
    tool = Riptide(_StubConfig())
    t0 = time.time()
    result = asyncio.get_event_loop().run_until_complete(
        tool.execute(image_path=str(img_path), elements=["red circle", "blue square"])
    )
    dt = time.time() - t0
    content = getattr(result, "content", None) or getattr(result, "text", "") or str(result)
    is_error = bool(getattr(result, "is_error", False))
    has_red = "red circle" in content.lower()
    has_blue = "blue square" in content.lower()
    has_bbox = "bbox" in content.lower() or "%" in content
    ok = not is_error and has_red and has_blue and has_bbox
    tag = "✓" if ok else "✗"
    print(f"  {tag}  latency: {dt:.2f}s  is_error={is_error}")
    # Trim to fit terminal — grounding output can be long
    print(f"  content:")
    for line in content.splitlines()[:8]:
        print(f"    {line}")
    if len(content.splitlines()) > 8:
        print(f"    ... ({len(content.splitlines())} lines total)")
    return {"ok": ok, "latency_s": round(dt, 2), "is_error": is_error, "content": content}


def main():
    health = check_health()
    gen = gen_chat_through_proxy()
    emb = embed_through_proxy()
    qa = undertow_qa()
    rip = riptide_vision_grounding()

    _section("SUMMARY")
    all_healthy = all(health.values())
    print(f"  health:      {'✓' if all_healthy else '✗'}  {sum(health.values())}/4 tiers up")
    print(f"  generation:  {'✓' if gen.get('ok') else '✗'}  {gen.get('latency_s')}s  answer={gen.get('content', '')!r}")
    print(f"  embedding:   {'✓' if emb.get('ok') else '✗'}  {emb.get('latency_s')}s  dim={emb.get('dim')}")
    print(f"  undertow QA: {'✓' if qa.get('passed') else '✗'}  "
          f"{sum(1 for r in qa.get('results', []) if r.passed)}/{len(qa.get('results', []))} levers")
    print(f"  riptide:     {'✓' if rip.get('ok') else '✗'}  {rip.get('latency_s')}s  vision grounding")

    overall = all_healthy and gen.get("ok") and emb.get("ok") and qa.get("passed") and rip.get("ok")
    print(f"\n  {'✅ STACK HEALTHY' if overall else '❌ STACK BROKEN'}")
    return 0 if overall else 1


# pytest entry points -----------------------------------------------------
def test_stack_smoke():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
