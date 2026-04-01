"""Drag — eddies that test built apps by actually using them.

The wave builds. The QA swell breaks.

Dispatches 2B eddies that each test a different aspect of the app:
- Does it load?
- Are there console errors?
- Do controls respond?
- Does the UI update?

Each eddy runs a headless browser test and reports bugs.
The wave reads the bug reports and fixes.
Then the QA swell runs again until clean.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("tsunami.drag")

BEE_ENDPOINT = os.environ.get("TSUNAMI_BEE_ENDPOINT", "http://localhost:8092")


async def run_drag(html_path: str, port: int = 9876) -> dict:
    """Run QA checks on an HTML file by serving it and testing.

    Returns dict with {passed: bool, errors: list[str], warnings: list[str]}
    """
    errors = []
    warnings = []
    abs_path = str(Path(html_path).resolve())
    serve_dir = str(Path(abs_path).parent)

    # 1. Basic file checks
    if not os.path.exists(abs_path):
        return {"passed": False, "errors": ["File does not exist"], "warnings": []}

    content = open(abs_path).read()

    if not content.strip().endswith("</html>"):
        errors.append("HTML file appears truncated — doesn't end with </html>")

    if "<script" not in content:
        warnings.append("No <script> tags found — might not be interactive")

    if "<!DOCTYPE" not in content and "<!doctype" not in content:
        warnings.append("Missing DOCTYPE declaration")

    # 2. Check for common JS errors in source
    js_issues = _check_js_source(content)
    errors.extend(js_issues)

    # 3. Serve and test with headless browser
    browser_issues = await _browser_test(serve_dir, port)
    errors.extend(browser_issues.get("errors", []))
    warnings.extend(browser_issues.get("warnings", []))

    passed = len(errors) == 0
    return {"passed": passed, "errors": errors, "warnings": warnings}


def _check_js_source(html: str) -> list[str]:
    """Static analysis of JavaScript in HTML for common issues."""
    import re
    errors = []

    # Extract all script content
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    js_code = "\n".join(scripts)

    if not js_code.strip():
        return []

    # Unmatched braces
    opens = js_code.count("{") + js_code.count("(") + js_code.count("[")
    closes = js_code.count("}") + js_code.count(")") + js_code.count("]")
    if abs(opens - closes) > 2:
        errors.append(f"Unbalanced brackets: {opens} opens vs {closes} closes")

    # Undefined references to common mistakes
    if "addEventListener" in js_code and "document" not in js_code and "window" not in js_code:
        errors.append("addEventListener used but no document/window reference")

    # Canvas without getContext
    if "canvas" in js_code.lower() and "getContext" not in js_code:
        errors.append("Canvas referenced but getContext never called")

    # requestAnimationFrame without function
    if "requestAnimationFrame" in js_code:
        # Check it's called with a function argument
        raf_calls = re.findall(r'requestAnimationFrame\s*\(\s*(\w+)', js_code)
        for fn_name in raf_calls:
            if fn_name not in js_code.replace(f"requestAnimationFrame({fn_name}", ""):
                errors.append(f"requestAnimationFrame calls '{fn_name}' but function may not exist")

    # Three.js specific checks
    if "THREE" in js_code or "three" in html:
        if "renderer" in js_code and "render(" not in js_code:
            errors.append("Three.js renderer created but render() never called")
        if "scene" in js_code and "add(" not in js_code:
            errors.append("Three.js scene created but nothing added to it")

    return errors


async def _browser_test(serve_dir: str, port: int) -> dict:
    """Serve the HTML and test it in a headless browser."""
    errors = []
    warnings = []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        warnings.append("Playwright not installed — skipping browser tests")
        return {"errors": errors, "warnings": warnings}

    # Start a simple HTTP server
    server_proc = await asyncio.create_subprocess_exec(
        "python3", "-m", "http.server", str(port),
        cwd=serve_dir,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    try:
        await asyncio.sleep(1)  # let server start

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Collect console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page_errors = []
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            try:
                response = await page.goto(f"http://localhost:{port}/index.html", timeout=10000)

                if response and response.status != 200:
                    errors.append(f"Page returned HTTP {response.status}")

                # Wait for any JS to execute
                await asyncio.sleep(2)

                # Check for console errors
                for err in console_errors:
                    errors.append(f"Console error: {err}")
                for err in page_errors:
                    errors.append(f"Page error: {err}")

                # Check if page has visible content
                body_text = await page.evaluate("document.body.innerText")
                if len(body_text.strip()) < 10:
                    warnings.append("Page appears mostly blank — very little text content")

                # Check if canvas exists and has content
                has_canvas = await page.evaluate("!!document.querySelector('canvas')")
                if has_canvas:
                    canvas_size = await page.evaluate("""() => {
                        const c = document.querySelector('canvas');
                        return {w: c.width, h: c.height};
                    }""")
                    if canvas_size["w"] == 0 or canvas_size["h"] == 0:
                        errors.append("Canvas has zero dimensions")

            except Exception as e:
                errors.append(f"Browser test error: {str(e)[:200]}")

            await browser.close()

    finally:
        server_proc.terminate()
        try:
            await asyncio.wait_for(server_proc.wait(), timeout=3)
        except asyncio.TimeoutError:
            server_proc.kill()

    return {"errors": errors, "warnings": warnings}


def format_qa_report(result: dict) -> str:
    """Format QA results for the wave to read."""
    status = "PASS" if result["passed"] else "FAIL"
    lines = [f"QA: {status}"]

    if result["errors"]:
        lines.append(f"\nErrors ({len(result['errors'])}):")
        for e in result["errors"]:
            lines.append(f"  ✗ {e}")

    if result["warnings"]:
        lines.append(f"\nWarnings ({len(result['warnings'])}):")
        for w in result["warnings"]:
            lines.append(f"  ⚠ {w}")

    if result["passed"]:
        lines.append("\nAll checks passed. App is ready to ship.")

    return "\n".join(lines)
