"""Browser tools — the window into the living internet.

The browser is the most powerful and most dangerous tool.
It touches the real world. Save key findings to files immediately —
multimodal context can be lost.

Uses Playwright for real Chromium automation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.browser")

# Shared browser instance — lazy init, reused across the session
_browser = None
_page = None


async def _ensure_browser(headless: bool = True):
    """Launch browser if not already running."""
    global _browser, _page
    if _browser is not None and _page is not None:
        return _page

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    pw = await async_playwright().start()
    _browser = await pw.chromium.launch(headless=headless)
    context = await _browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    _page = await context.new_page()
    return _page


async def _get_page_elements(page) -> str:
    """Extract interactive elements with index labels."""
    elements = await page.evaluate("""() => {
        const interactable = document.querySelectorAll(
            'a[href], button, input, textarea, select, [role="button"], [role="link"], [onclick]'
        );
        const results = [];
        let idx = 0;
        for (const el of interactable) {
            if (el.offsetParent === null) continue; // skip hidden
            const tag = el.tagName.toLowerCase();
            const text = (el.textContent || el.value || el.placeholder || el.alt || '').trim().slice(0, 80);
            const href = el.href || '';
            const type = el.type || '';
            let desc = `index[${idx}]:<${tag}`;
            if (type) desc += ` type="${type}"`;
            if (href) desc += ` href="${href.slice(0, 100)}"`;
            desc += `>${text}</${tag}>`;
            results.push(desc);
            idx++;
        }
        return results.join('\\n');
    }""")
    return elements


async def _extract_markdown(page) -> str:
    """Extract page content as readable text."""
    text = await page.evaluate("""() => {
        // Try to find main content
        const selectors = ['article', 'main', '[role="main"]', '.content', '#content', 'body'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.textContent.trim().length > 100) {
                return el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 8000);
            }
        }
        return document.body.textContent.trim().replace(/\\s+/g, ' ').slice(0, 8000);
    }""")
    return text


class BrowserNavigate(BaseTool):
    name = "browser_navigate"
    description = "Navigate to a URL. The step: move to where the information lives."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
                "wait_for": {"type": "string", "description": "CSS selector to wait for", "default": ""},
            },
            "required": ["url"],
        }

    async def execute(self, url: str, wait_for: str = "", **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)

            status = response.status if response else "unknown"
            title = await page.title()
            content = await _extract_markdown(page)

            result = f"Navigated to: {url}\nStatus: {status}\nTitle: {title}\n\n{content}"
            return ToolResult(result)
        except Exception as e:
            return ToolResult(f"Navigation error: {e}", is_error=True)


class BrowserView(BaseTool):
    name = "browser_view"
    description = "See the current state of the page — URL, title, content, and interactive elements."

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            url = page.url
            title = await page.title()
            content = await _extract_markdown(page)
            elements = await _get_page_elements(page)

            parts = [
                f"URL: {url}",
                f"Title: {title}",
                f"\n--- Content ---\n{content[:4000]}",
            ]
            if elements:
                parts.append(f"\n--- Interactive Elements ---\n{elements}")

            return ToolResult("\n".join(parts))
        except Exception as e:
            return ToolResult(f"View error: {e}", is_error=True)


class BrowserClick(BaseTool):
    name = "browser_click"
    description = "Click an interactive element by its index (from browser_view output)."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "Element index from browser_view"},
            },
            "required": ["index"],
        }

    async def execute(self, index: int, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)

            clicked = await page.evaluate(f"""(idx) => {{
                const interactable = document.querySelectorAll(
                    'a[href], button, input, textarea, select, [role="button"], [role="link"], [onclick]'
                );
                const visible = Array.from(interactable).filter(el => el.offsetParent !== null);
                if (idx >= visible.length) return null;
                const el = visible[idx];
                el.click();
                return el.tagName + ': ' + (el.textContent || '').trim().slice(0, 80);
            }}""", index)

            if clicked is None:
                return ToolResult(f"Element index {index} not found", is_error=True)

            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            title = await page.title()
            return ToolResult(f"Clicked: {clicked}\nPage now: {page.url} — {title}")
        except Exception as e:
            return ToolResult(f"Click error: {e}", is_error=True)


class BrowserInput(BaseTool):
    name = "browser_input"
    description = "Type text into a form field by its index."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "Element index from browser_view"},
                "text": {"type": "string", "description": "Text to type"},
                "press_enter": {"type": "boolean", "description": "Press Enter after typing", "default": False},
            },
            "required": ["index", "text"],
        }

    async def execute(self, index: int, text: str, press_enter: bool = False, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)

            filled = await page.evaluate(f"""(idx) => {{
                const interactable = document.querySelectorAll(
                    'a[href], button, input, textarea, select, [role="button"], [role="link"], [onclick]'
                );
                const visible = Array.from(interactable).filter(el => el.offsetParent !== null);
                if (idx >= visible.length) return null;
                const el = visible[idx];
                el.focus();
                el.value = '';
                return el.tagName + '[' + (el.type || '') + ']';
            }}""", index)

            if filled is None:
                return ToolResult(f"Element index {index} not found", is_error=True)

            # Type character by character for realistic input
            elements = await page.query_selector_all(
                'a[href], button, input, textarea, select, [role="button"], [role="link"], [onclick]'
            )
            visible = []
            for el in elements:
                if await el.is_visible():
                    visible.append(el)
            if index < len(visible):
                await visible[index].type(text, delay=20)
                if press_enter:
                    await visible[index].press("Enter")

            result = f"Typed into {filled}: '{text}'"
            if press_enter:
                result += " [Enter pressed]"
            return ToolResult(result)
        except Exception as e:
            return ToolResult(f"Input error: {e}", is_error=True)


class BrowserScroll(BaseTool):
    name = "browser_scroll"
    description = "Scroll the page up or down."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "amount": {"type": "integer", "description": "Pixels to scroll", "default": 500},
            },
        }

    async def execute(self, direction: str = "down", amount: int = 500, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            delta = amount if direction == "down" else -amount
            await page.evaluate(f"window.scrollBy(0, {delta})")
            scroll_y = await page.evaluate("window.scrollY")
            scroll_max = await page.evaluate("document.body.scrollHeight - window.innerHeight")
            return ToolResult(f"Scrolled {direction} {amount}px. Position: {scroll_y}/{scroll_max}")
        except Exception as e:
            return ToolResult(f"Scroll error: {e}", is_error=True)


class BrowserFindKeyword(BaseTool):
    name = "browser_find"
    description = "Search for text on the current page and return context around matches."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Text to search for on the page"},
            },
            "required": ["keyword"],
        }

    async def execute(self, keyword: str, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            text = await _extract_markdown(page)
            keyword_lower = keyword.lower()
            text_lower = text.lower()

            matches = []
            start = 0
            while True:
                idx = text_lower.find(keyword_lower, start)
                if idx == -1:
                    break
                context_start = max(0, idx - 100)
                context_end = min(len(text), idx + len(keyword) + 100)
                context = text[context_start:context_end]
                matches.append(f"...{context}...")
                start = idx + 1
                if len(matches) >= 10:
                    break

            if not matches:
                return ToolResult(f"'{keyword}' not found on page")

            return ToolResult(
                f"Found {len(matches)} matches for '{keyword}':\n\n" +
                "\n---\n".join(matches)
            )
        except Exception as e:
            return ToolResult(f"Find error: {e}", is_error=True)


class BrowserConsoleExec(BaseTool):
    name = "browser_console"
    description = "Execute JavaScript in the page. The override: reach into the page's machinery."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript code to execute"},
            },
            "required": ["script"],
        }

    async def execute(self, script: str, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            result = await page.evaluate(script)
            return ToolResult(f"JS result: {json.dumps(result, default=str)[:5000]}")
        except Exception as e:
            return ToolResult(f"JS error: {e}", is_error=True)


class BrowserFillForm(BaseTool):
    name = "browser_fill_form"
    description = "Complete multiple form fields at once. The efficiency: batch what can be batched."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "description": "Element index"},
                            "value": {"type": "string", "description": "Value to set"},
                        },
                        "required": ["index", "value"],
                    },
                    "description": "List of {index, value} pairs to fill",
                },
            },
            "required": ["fields"],
        }

    async def execute(self, fields: list[dict], **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            elements = await page.query_selector_all(
                'a[href], button, input, textarea, select, [role="button"], [role="link"], [onclick]'
            )
            visible = []
            for el in elements:
                if await el.is_visible():
                    visible.append(el)

            filled = []
            for field in fields:
                idx = field["index"]
                val = field["value"]
                if idx < len(visible):
                    await visible[idx].fill(val)
                    tag = await visible[idx].evaluate("el => el.tagName + '[' + (el.type||'') + ']'")
                    filled.append(f"{tag}={val[:50]}")
                else:
                    filled.append(f"index {idx}: NOT FOUND")

            return ToolResult(f"Filled {len(filled)} fields: {'; '.join(filled)}")
        except Exception as e:
            return ToolResult(f"Fill form error: {e}", is_error=True)


class BrowserPressKey(BaseTool):
    name = "browser_press_key"
    description = "Simulate a keyboard press. The keystroke: precise mechanical input."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key to press (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown', 'Control+a')",
                },
            },
            "required": ["key"],
        }

    async def execute(self, key: str, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            await page.keyboard.press(key)
            return ToolResult(f"Pressed key: {key}")
        except Exception as e:
            return ToolResult(f"Key press error: {e}", is_error=True)


class BrowserSelectOption(BaseTool):
    name = "browser_select"
    description = "Choose from a dropdown/select element. The decision: select from given options."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "Element index of the <select>"},
                "value": {"type": "string", "description": "Option value or visible text to select"},
            },
            "required": ["index", "value"],
        }

    async def execute(self, index: int, value: str, **kw) -> ToolResult:
        try:
            page = await _ensure_browser(self.config.browser_headless)
            elements = await page.query_selector_all(
                'a[href], button, input, textarea, select, [role="button"], [role="link"], [onclick]'
            )
            visible = []
            for el in elements:
                if await el.is_visible():
                    visible.append(el)

            if index >= len(visible):
                return ToolResult(f"Element index {index} not found", is_error=True)

            el = visible[index]
            tag = await el.evaluate("el => el.tagName")
            if tag.lower() != "select":
                return ToolResult(f"Element at index {index} is <{tag}>, not <select>", is_error=True)

            # Try by value first, then by label
            try:
                await el.select_option(value=value)
            except Exception:
                await el.select_option(label=value)

            return ToolResult(f"Selected '{value}' from dropdown at index {index}")
        except Exception as e:
            return ToolResult(f"Select error: {e}", is_error=True)


class BrowserSaveImage(BaseTool):
    name = "browser_save_image"
    description = "Download an image from the current page. The collector: preserve visual assets."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Image URL to download (or 'screenshot' for page screenshot)"},
                "save_path": {"type": "string", "description": "Local path to save the image"},
            },
            "required": ["save_path"],
        }

    async def execute(self, save_path: str, url: str = "screenshot", **kw) -> ToolResult:
        try:
            from pathlib import Path
            page = await _ensure_browser(self.config.browser_headless)
            p = Path(save_path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)

            if url == "screenshot":
                await page.screenshot(path=str(p), full_page=True)
                return ToolResult(f"Screenshot saved to {p}")
            else:
                # Download via page context
                import httpx
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    p.write_bytes(resp.content)
                return ToolResult(f"Image saved to {p} ({len(resp.content)} bytes)")
        except Exception as e:
            return ToolResult(f"Save image error: {e}", is_error=True)


class BrowserUploadFile(BaseTool):
    name = "browser_upload"
    description = "Upload a file to a web form. The offering: send files into the web."

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "Element index of the file input"},
                "file_path": {"type": "string", "description": "Local path of file to upload"},
            },
            "required": ["index", "file_path"],
        }

    async def execute(self, index: int, file_path: str, **kw) -> ToolResult:
        try:
            from pathlib import Path
            page = await _ensure_browser(self.config.browser_headless)
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return ToolResult(f"File not found: {file_path}", is_error=True)

            elements = await page.query_selector_all('input[type="file"]')
            visible = []
            for el in elements:
                visible.append(el)  # file inputs are often hidden

            if index >= len(visible):
                return ToolResult(
                    f"File input index {index} not found. Found {len(visible)} file inputs.",
                    is_error=True,
                )

            await visible[index].set_input_files(str(p))
            return ToolResult(f"Uploaded {p.name} to file input {index}")
        except Exception as e:
            return ToolResult(f"Upload error: {e}", is_error=True)


class BrowserClose(BaseTool):
    name = "browser_close"
    description = "Close the browser session. The departure: leave when done."

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kw) -> ToolResult:
        global _browser, _page
        try:
            if _browser:
                await _browser.close()
                _browser = None
                _page = None
            return ToolResult("Browser closed.")
        except Exception as e:
            _browser = None
            _page = None
            return ToolResult(f"Close error (cleaned up): {e}")
