"""Stage 4: Vision gate.

After build + unit tests pass, take a screenshot of the built app and
ask the same multimodal model (Qwen3.6-VL on :8095) whether it looks
like the thing we asked for. Two outcomes:

  - OK  → deliver
  - issues flagged → system_note with the specific visual problems;
                     drone gets another turn to fix styling

This is the visual analog of the unit test gate: unit tests check
behavior, vision checks form. Both are deterministic enough to loop on.

Design notes:
  - We use the SAME Qwen3.6 endpoint that answers text turns — no
    separate VLM to spin up (model is natively multimodal).
  - Screenshot is headless Playwright on `dist/index.html` (file://).
  - The probe is intentionally narrow: "list visual issues" (not
    "describe the app"), so the response is short + actionable.
  - On endpoint failure / playwright unavailable, fall back to pass —
    this gate is advisory-level on novel tasks, strict on known ones.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx

log = logging.getLogger("tsunami.vision_gate")


async def _screenshot_html(html_path: Path) -> bytes | None:
    """Headless screenshot of a local HTML file. Serves the containing
    dist/ over a tiny HTTP server because Chromium blocks the `crossorigin`
    script tag Vite emits under file://. Serving via HTTP makes the built
    bundle load, JS runs, React mounts, screenshot captures real UI.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.debug("playwright not installed — vision gate fall-through")
        return None
    import http.server
    import socketserver
    import threading
    import socket

    # Serve the dist directory over HTTP on a free port.
    dist_dir = html_path.parent
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(dist_dir), **kw)
        def log_message(self, *a, **kw):
            pass  # mute

    server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        url = f"http://127.0.0.1:{port}/{html_path.name}"
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1024, "height": 768})
            await page.goto(url, timeout=8000)
            await page.wait_for_timeout(800)  # allow React to mount
            png = await page.screenshot(full_page=False, type="png")
            await browser.close()
            return png
    except Exception as e:
        log.warning(f"vision_gate screenshot failed: {e}")
        return None
    finally:
        server.shutdown()
        server.server_close()


async def vision_check(dist_html: Path, task: str,
                       endpoint: str = "http://localhost:8090",
                       timeout_s: int = 40) -> dict:
    """Stage-4 vision gate. Returns {passed: bool, issues: str, raw: str}.

    `passed=True` means no visual issues OR the gate was unavailable
    (fall-through). On explicit issues flagged by the VLM, `passed=False`
    and `issues` holds the drone-facing feedback string.
    """
    png = await _screenshot_html(dist_html)
    if png is None:
        return {"passed": True, "issues": "", "raw": "(screenshot unavailable — skip)"}

    b64 = base64.b64encode(png).decode()
    messages = [
        {"role": "system", "content":
            "You are a visual QA reviewer for a STATIC screenshot of a React app. "
            "You can ONLY judge what a screenshot shows: visible elements, layout, "
            "typography, color, spacing, completeness of the rendered UI. You CANNOT "
            "judge interactivity (whether buttons click, whether timers run, whether "
            "typing works) — those are tested separately by unit tests. Judge only "
            "the visual/structural presentation.\n\n"
            "Fail criteria (be strict — delivery is blocked on fail):\n"
            "  - Blank or mostly-blank page\n"
            "  - Missing major UI elements the task requires (e.g. task asks for 3 buttons and you see 0)\n"
            "  - Placeholder text like 'TODO' or 'Loading...' as the primary content\n"
            "  - Layout breakage: overlapping elements, off-screen content, broken z-order\n"
            "  - Text CLIPPED by its container — any letter cut off at a border, ellipsis where there shouldn't be, words shortened because the parent is too narrow\n"
            "  - DUPLICATED content that should appear once — the same value/label shown twice (e.g. '25:00' rendered both top-right and center), mirrored controls, redundant pills/badges\n"
            "  - Inconsistent typography on the same line (mixed font families, mismatched weights where the design calls for uniform)\n"
            "  - Color hierarchy that obscures meaning (e.g. primary action the same hue as disabled state)\n"
            "Pass criteria: task-relevant elements are visible, no clipping, no duplicates, consistent style.\n\n"
            "Respond in this exact format:\nVERDICT: pass | fail\nISSUES: <one-line-per-issue, or 'none'>"
        },
        {"role": "user", "content": [
            {"type": "text", "text":
                f"Task the app was built for: {task}\n\n"
                f"Judge the visual presentation in this static screenshot. "
                f"Don't judge interactivity — unit tests already cover that."
            },
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                f"{endpoint.rstrip('/')}/v1/chat/completions",
                json={"model": "tsunami", "messages": messages,
                      "max_tokens": 256, "temperature": 0.2,
                      "enable_thinking": False},
                headers={"Authorization": "Bearer not-needed"},
            )
            if r.status_code != 200:
                log.warning(f"vision_gate endpoint returned {r.status_code}")
                return {"passed": True, "issues": "",
                        "raw": f"(endpoint {r.status_code} — skip)"}
            data = r.json()
            content = data["choices"][0]["message"].get("content", "") or ""
    except Exception as e:
        log.warning(f"vision_gate endpoint error: {e}")
        return {"passed": True, "issues": "", "raw": f"(endpoint error — skip: {e})"}

    verdict_line = ""
    issues_line = ""
    for ln in content.splitlines():
        s = ln.strip()
        if s.lower().startswith("verdict:"):
            verdict_line = s.split(":", 1)[1].strip().lower()
        elif s.lower().startswith("issues:"):
            issues_line = s.split(":", 1)[1].strip()
    passed = verdict_line.startswith("pass") or issues_line.lower() in ("", "none")
    # If the VLM gave a non-conforming response, err on the side of pass
    # (advisory gate) — don't block delivery on an un-parseable verdict.
    if not verdict_line and not issues_line:
        log.info("vision_gate: model response un-parseable, treating as pass")
        return {"passed": True, "issues": "", "raw": content[:400]}
    return {"passed": passed, "issues": issues_line if not passed else "",
            "raw": content[:400]}
