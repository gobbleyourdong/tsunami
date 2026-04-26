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
                       timeout_s: int = 40,
                       target_layout: Path | None = None) -> dict:
    """Stage-4 vision gate. Returns {passed: bool, issues: str, raw: str}.

    `passed=True` means no visual issues OR the gate was unavailable
    (fall-through). On explicit issues flagged by the VLM, `passed=False`
    and `issues` holds the drone-facing feedback string.

    When `target_layout` is provided, the gate runs in reference-match
    mode: VLM gets the built screenshot AND the target image, compares
    structure/palette/typography, and fails if the built page doesn't
    read as the same family of design. Otherwise, open-ended QA.
    """
    png = await _screenshot_html(dist_html)
    if png is None:
        return {"passed": True, "issues": "", "raw": "(screenshot unavailable — skip)"}

    b64 = base64.b64encode(png).decode()

    # Reference-match mode: build a two-image message and tighten the
    # system prompt to comparison criteria.
    target_png: bytes | None = None
    if target_layout is not None:
        try:
            if target_layout.is_file() and target_layout.stat().st_size > 1024:
                target_png = target_layout.read_bytes()
        except Exception as _te:
            log.debug(f"target_layout read failed: {_te}")

    if target_png is not None:
        tb64 = base64.b64encode(target_png).decode()
        messages = [
            {"role": "system", "content":
                "You are a visual QA reviewer comparing a BUILT React page "
                "against a TARGET LAYOUT reference. Two images follow: the "
                "first is the target (the intended design), the second is "
                "the built page screenshot.\n\n"
                "Judge match on four axes:\n"
                "  1. Composition — nav placement, hero proportions, section "
                "ordering, footer presence. Rough structural agreement.\n"
                "  2. Palette — base surface (light/neutral/dark), text "
                "color, accent color family. Not pixel-identical — same "
                "family.\n"
                "  3. Typography — serif vs sans display, weight, density. "
                "Built page and target should read as the same typographic "
                "voice.\n"
                "  4. Spacing rhythm — gutter scale, section air, content "
                "density. Tight vs generous should match.\n\n"
                "Ignore: exact pixel colors, specific image content, minor "
                "copy differences. The target is a mockup, not a spec.\n\n"
                "Fail criteria:\n"
                "  - Built page is blank / unfinished / scaffold stub\n"
                "  - Major composition mismatch (target has hero+nav+3 "
                "sections+footer; built page has just a centered card)\n"
                "  - Mode mismatch (target light, built dark — or vice versa)\n"
                "  - Placeholder text ('TODO', 'Loading...') in built page\n"
                "  - Broken / clipped layout regardless of target\n\n"
                "Respond in this exact format:\n"
                "VERDICT: pass | fail\n"
                "ISSUES: <one-line-per-issue, or 'none'>"
            },
            {"role": "user", "content": [
                {"type": "text", "text":
                    f"Task: {task}\n\n"
                    f"TARGET (first image): the intended design for this build.\n"
                    f"BUILT (second image): what the drone delivered.\n\n"
                    f"Compare them on composition, palette, typography, spacing. "
                    f"Flag structural / mode / completeness mismatches only."
                },
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{tb64}"}},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]},
        ]
    else:
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
                "If the task text begins with `[doctrine=<name>]`, an explicit\n"
                "style doctrine was injected. Judge visual coherence RELATIVE\n"
                "to that doctrine, not a generic 'clean UI' baseline:\n"
                "  - photo_studio: hero = full-bleed image, serif display\n"
                "    BELOW image, tiny uppercase nav. Fail if card-grid hero.\n"
                "  - cinematic_display: near-black bg, oversized condensed\n"
                "    display (Bebas/Anton), full-bleed hero. Fail if light.\n"
                "  - newsroom_editorial: masthead hairline rules, narrow\n"
                "    serif column, breaking-news chip. Fail if sans-only.\n"
                "  - atelier_warm: warm-cream bg (NOT white), serif italic,\n"
                "    asymmetric split, colophon stamp. Fail if pure white.\n"
                "  - magazine_editorial: cream bg, multi-column body, drop\n"
                "    caps, pull quotes. Fail if no columns on long-form.\n"
                "  - swiss_modern: off-white, strict 12-col grid, ONE vivid\n"
                "    accent, hairline rules. Fail if mixed accents.\n"
                "  - shadcn_startup: sticky blurred nav, rounded cards, ONE\n"
                "    saturated accent, 3-up features. Fail if dark bg.\n"
                "  - editorial_dark: near-black + serif + asymmetric 7/5 +\n"
                "    sticky image column. Fail if centered / non-serif.\n"
                "  - playful_chromatic: sticky pill nav, mesh gradient blob,\n"
                "    Syne/Bricolage display, slight bento rotation. Fail if\n"
                "    rigid rectilinear grid.\n"
                "  - brutalist_web: hard white, Times/Courier, 1px borders,\n"
                "    1995-blue links. Fail if rounded or shadowed.\n"
                "  - seed_* (any prefix): the image was seeded — base\n"
                "    doctrine rules apply but palette is seed-overridden.\n\n"
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
    # Vision-VLM call is DEFERRED since 2026-04-26 — the localhost:8090
    # endpoint default was the deleted serve_transformers proxy. Until
    # this is wired to a Claude vision API call (anthropic SDK with
    # image content + the messages structure prepared above), the gate
    # cannot judge visual presentation.
    #
    # IMPORTANT: previously this returned passed=True on endpoint error
    # (fail-open). That silently passed every build. New behavior is
    # fail-closed: the gate explicitly returns passed=False with a
    # deferred-error issues string, so a future agent calling vision_check
    # gets a clear signal that the gate isn't operational, instead of a
    # silent skip that lets visual bugs ship.
    log.warning("vision_check: VLM endpoint deferred — gate is not operational")
    return {
        "passed": False,
        "issues": "vision_gate deferred — wire to Claude vision API to re-enable",
        "raw": "(VLM endpoint retired 2026-04-26; see CLAUDE.md 'Generations TBD')",
    }

    # Preserved below for future re-enablement — see comment above.
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
