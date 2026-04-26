"""Undertow — dumb QA that pulls levers.

The wave is the engineer. The undertow is the tester.
The wave says WHAT to test. The undertow just does it and reports.

The undertow doesn't know what Three.js is. It doesn't diagnose.
It pulls levers and says what happened. The wave reads the report
and figures out what's broken.

Lever types:
  screenshot  — take a screenshot, describe what's on screen
  press       — press a key, report if anything changed
  click       — click a selector, report if anything changed
  read_text   — read text content of a selector
  console     — report any console errors/output
  wait        — wait N ms then continue

The wave provides levers. The undertow pulls them all at once.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

log = logging.getLogger("tsunami.undertow")

BEE_ENDPOINT = os.environ.get("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8091")


# ──────────────────── data types ────────────────────


@dataclass
class Lever:
    """A single test action for the undertow to pull."""
    action: str          # screenshot, press, click, read_text, console, wait,
                         # ghost_classes, motion, sequence, type, autopilot
    expect: str = ""     # what the wave expects to see (eddy compares)
    key: str = ""        # for press
    selector: str = ""   # for click, read_text
    ms: int = 0          # for wait
    # Autopilot knobs — click through interactive elements unattended:
    max_clicks: int = 20         # cap on crawl length
    max_errors_tolerated: int = 2 # fail-if-exceeded runtime-error budget
    # Lever engine. "browser" (default) runs the action inside Playwright;
    # "static" runs against the built filesystem without launching a browser.
    # Static levers are dispatched before the browser boots so flaky
    # programmatic checks (ghost_classes file-scan, unused-dep scan) don't
    # depend on Playwright availability or load timing.
    engine: str = "browser"


@dataclass
class LeverResult:
    """What happened when we pulled the lever."""
    lever: Lever
    passed: bool
    saw: str             # what the undertow actually observed
    detail: str = ""     # extra context


@dataclass
class QAReport:
    """Full report from pulling all levers."""
    passed: bool
    results: list[LeverResult] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    screenshot_path: str = ""


# ──────────────────── the undertow ────────────────────


async def pull_levers(
    html_path: str,
    levers: list[Lever],
    port: int = 9876,
    system_note: str | None = None,
) -> QAReport:
    """Serve an HTML file and pull every lever the wave gave us.

    Returns a QAReport with pass/fail per lever.

    `system_note`, when provided, is a direction-set markdown body
    (from `pick_direction_set`) threaded into every eddy/VLM call
    this run makes. None preserves baseline behavior.
    """
    abs_path = str(Path(html_path).resolve())
    serve_dir = str(Path(abs_path).parent)
    filename = Path(abs_path).name

    if not os.path.exists(abs_path):
        return QAReport(passed=False, results=[
            LeverResult(lever=Lever(action="file"), passed=False, saw="file does not exist")
        ])

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return QAReport(passed=False, results=[
            LeverResult(lever=Lever(action="setup"), passed=False, saw="playwright not installed")
        ])

    # Auto-inject the default static levers FIRST so they route into
    # the static pre-pass below. Previously these were added inside the
    # live-DOM block which runs AFTER the pre-pass → the injected
    # Lever(engine="static") ended up in the dynamic list and _pull_one
    # raised "unknown lever action: unused_dep".
    if not any(l.action == "ghost_classes" for l in levers):
        levers.append(Lever(action="ghost_classes", engine="static"))
    if not any(l.action == "unused_dep" for l in levers):
        levers.append(Lever(action="unused_dep", engine="static"))
    if not any(l.action == "autopilot" for l in levers):
        levers.append(Lever(action="autopilot"))

    # Static lever pre-pass. Static checks run against the built
    # filesystem without Playwright; they're deterministic, ~100× faster
    # than the browser path, and don't fail from cross-origin / load-
    # timing quirks. Run them BEFORE starting the http.server so a
    # programmatic failure doesn't pay the browser launch cost.
    static_results: list[LeverResult] = []
    static_levers = [l for l in levers if getattr(l, "engine", "browser") == "static"]
    dynamic_levers = [l for l in levers if getattr(l, "engine", "browser") != "static"]
    for lever in static_levers:
        static_results.append(await _pull_static(lever, serve_dir))
    # If any static lever failed hard, we can still run dynamic ones —
    # callers decide whether to gate on the merged report. Keep flow.
    levers = dynamic_levers

    # Pick a free port to avoid conflicts with vite dev servers left
    # running by project_init (which defaults to port 9876, the same
    # port undertow used to default to). 2026-04-13 zero-shot smoke fix.
    import socket as _sock
    with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as _s:
        _s.bind(("127.0.0.1", 0))
        port = _s.getsockname()[1]

    # Start HTTP server
    server_proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "http.server", str(port),
        cwd=serve_dir,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    report = QAReport(passed=True)

    try:
        await asyncio.sleep(1)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Collect console output
            console_msgs = []
            page.on("console", lambda msg: console_msgs.append((msg.type, msg.text)))
            page_errors = []
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            try:
                resp = await page.goto(
                    f"http://localhost:{port}/{filename}", timeout=10000
                )
                # Wipe any persistent session state the app may have written
                # on mount — localStorage, sessionStorage, cookies, indexedDB.
                # Voting apps, onboarding wizards, and signup flows commonly
                # store "already did this" flags that would make the second+
                # undertow run see a post-action state and report click/input
                # levers as no-ops. Reload after clearing so the app re-mounts
                # against a truly fresh session.
                try:
                    await page.evaluate(
                        "() => { try { localStorage.clear(); sessionStorage.clear(); } catch(e) {} }"
                    )
                    await page.context.clear_cookies()
                    await page.reload(timeout=10000)
                except Exception as e:
                    log.debug(f"Storage reset skipped: {e}")
                await asyncio.sleep(2)  # let JS initialize
            except Exception as e:
                report.passed = False
                report.results.append(LeverResult(
                    lever=Lever(action="load"), passed=False,
                    saw=f"page failed to load: {str(e)[:200]}"
                ))
                await browser.close()
                return report

            # Record any page errors from loading
            report.console_errors = [e for e in page_errors]
            if page_errors:
                report.results.append(LeverResult(
                    lever=Lever(action="load"), passed=False,
                    saw=f"JS errors on load: {'; '.join(page_errors[:3])}"
                ))
                report.passed = False

            # React/Vue/etc SPAs render buttons and inputs via JS after load, so
            # the static HTML that generate_levers regex-scanned is empty. Query
            # the LIVE DOM here and inject interaction levers — clicks for
            # buttons, typing for text inputs — so the post-interaction
            # screenshot captures the app in its "used" state rather than its
            # initial placeholder state. (2026-04-13: dice-roller judgment ran
            # before Roll was pressed; typing-mirror was judged on empty input.)
            # Only treat click/type/fill as "real" interactions here. press
            # levers get added by the static-HTML regex scan when the bundled
            # JS contains key strings like 'Enter'/'ArrowDown' — those are
            # incidental (library code, event-map constants) and have nothing
            # to do with whether the app has clickable buttons to exercise.
            # Always run ghost_classes check — catches "model wrote Tailwind
            # but Tailwind isn't installed" and similar unstyled-class failure
            # modes, independent of whether the page has interactable elements.
            # Splice right before the final screenshot so the QA flow is
            # console → content screenshot → ghost-class audit → interactions
            # → final screenshot.
            # ghost_classes / unused_dep / autopilot auto-inject moved
            # upstream (just after the playwright-import guard) so the
            # static-pre-pass routing sees them. Keep this comment as a
            # breadcrumb for anyone diffing against the old layout.
            pass  # no-op — default levers injected at top

            already_interacts = any(
                l.action in ("click", "type", "fill") for l in levers
            )
            if not already_interacts:
                try:
                    # Enumerate live-DOM interactables. Counts only visible and
                    # not-disabled elements. Covers what Manus's clickability
                    # framework calls out: <button>, <a href>, role=button,
                    # role=link, and styled divs with cursor:pointer (the
                    # last is a visual affordance signal in shadcn-style UIs).
                    counts = await page.evaluate("""
                        () => {
                            const vis = el => {
                                if (el.offsetParent === null) return false;
                                if (el.disabled) return false;
                                if (el.getAttribute('aria-disabled') === 'true') return false;
                                return true;
                            };
                            const clickableSel = [
                                'button',
                                'a[href]',
                                '[role="button"]',
                                '[role="link"]',
                                'input[type="submit"]',
                                'input[type="button"]',
                                'input[type="reset"]'
                            ].join(', ');
                            const clickables = Array.from(document.querySelectorAll(clickableSel)).filter(vis).length;

                            // Styled-div clickables: cursor:pointer + some event
                            // affordance. Rare but catches React cards wired as
                            // click targets without role=button.
                            const divClickables = Array.from(document.querySelectorAll('div, span'))
                                .filter(el => vis(el)
                                    && getComputedStyle(el).cursor === 'pointer'
                                    && !el.closest('button,a,[role="button"],[role="link"]'))
                                .length;

                            const inputSel = 'input[type="text"], input[type="search"],'
                                + ' input[type="email"], input[type="url"], input[type="tel"],'
                                + ' input[type="password"], input[type="number"],'
                                + ' input:not([type]), textarea';
                            const inputs = Array.from(document.querySelectorAll(inputSel))
                                .filter(el => vis(el) && !el.readOnly)
                                .length;
                            return {clickables, divClickables, inputs};
                        }
                    """)
                    # Only click the FIRST clickable. Clicking multiple in
                    # sequence fights React state mutations (click 1 opens a
                    # modal, click 2 tries to hit a button that moved, click 3
                    # selects something no longer visible). A single click
                    # proves "interaction works" — which is all undertow needs
                    # to establish. Multi-step workflows (signup → next →
                    # submit) are outside undertow's scope; those are the
                    # wave's job to express in `expect`.
                    live_clickables = min(int(counts.get("clickables", 0) or 0), 1)
                    live_div_clicks = min(int(counts.get("divClickables", 0) or 0), 2)
                    live_inputs = min(int(counts.get("inputs", 0) or 0), 2)

                    # Combined clickable selector — matches anything semantically
                    # or visually signaling "I am clickable". Playwright's
                    # `>> nth=N` indexes across the full match set globally.
                    clickable_css = (
                        'button:not([disabled]):not([aria-disabled="true"]), '
                        'a[href], '
                        '[role="button"]:not([aria-disabled="true"]), '
                        '[role="link"], '
                        'input[type="submit"]:not([disabled]), '
                        'input[type="button"]:not([disabled])'
                    )
                    injected: list[Lever] = []
                    # Inputs first — typing triggers state that buttons may
                    # then read (typing-mirror apps, forms).
                    if live_inputs > 0:
                        injected.append(Lever(
                            action="type",
                            selector=(
                                "input:not([type='button']):not([type='submit'])"
                                ":not([type='checkbox']):not([type='radio'])"
                                ":not([readonly]):not([disabled]), "
                                "textarea:not([readonly]):not([disabled])"
                            ),
                            expect="hello world",  # reuse expect slot for the text to type
                        ))
                    for i in range(live_clickables):
                        injected.append(Lever(
                            action="click", selector=f"{clickable_css} >> nth={i}"
                        ))
                    # Styled-div clickables — click the first if semantic
                    # targets didn't cover all the interactables.
                    if live_clickables == 0 and live_div_clicks > 0:
                        injected.append(Lever(
                            action="click",
                            selector='div:has(> *), span:has(> *) >> nth=0',
                        ))
                    if injected:
                        # Animations (dice rolls, transitions, controlled inputs
                        # propagating state) often take 500–1500ms to settle.
                        injected.append(Lever(action="wait", ms=1500))
                        # Splice interactions in before the final screenshot
                        # (the one carrying user_request as its expect).
                        final_idx = None
                        for idx in range(len(levers) - 1, -1, -1):
                            if levers[idx].action == "screenshot" and levers[idx].expect:
                                final_idx = idx
                                break
                        if final_idx is not None:
                            levers = levers[:final_idx] + injected + levers[final_idx:]
                        else:
                            levers = levers + injected
                        log.info(
                            f"Undertow: injected {live_inputs} type + {live_clickables} click "
                            f"+ {live_div_clicks if live_clickables == 0 else 0} div-click "
                            f"levers from live DOM"
                        )
                except Exception as e:
                    log.debug(f"Live DOM interaction scan failed: {e}")

            # Pull each lever
            for lever in levers:
                result = await _pull_one(page, lever, console_msgs, system_note)
                report.results.append(result)
                if not result.passed:
                    report.passed = False

            await browser.close()

    finally:
        # ProcessLookupError fires when the http.server subprocess died on its
        # own (e.g. port collision with another undertow run). Don't let
        # cleanup mask the real failure further up the stack.
        try:
            server_proc.terminate()
            try:
                await asyncio.wait_for(server_proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                server_proc.kill()
        except ProcessLookupError:
            pass

    # Merge static-pass results (ran before the browser) into the final
    # report. Placed at the front so viewers see cheap checks first;
    # static failures feed into report.passed so the caller sees the
    # same boolean for static-only or mixed failures.
    if static_results:
        report.results = static_results + report.results
        if any(not r.passed for r in static_results):
            report.passed = False

    return report


async def _pull_one(
    page,
    lever: Lever,
    console_msgs: list,
    system_note: str | None = None,
) -> LeverResult:
    """Pull a single lever and report what happened."""

    try:
        if lever.action == "screenshot":
            return await _lever_screenshot(page, lever, system_note)

        elif lever.action == "press":
            return await _lever_press(page, lever, system_note)

        elif lever.action == "click":
            return await _lever_click(page, lever)

        elif lever.action == "ghost_classes":
            return await _lever_ghost_classes(page, lever)

        elif lever.action == "read_text":
            return await _lever_read_text(page, lever, system_note)

        elif lever.action == "console":
            errors = [text for typ, text in console_msgs if typ == "error"]
            if errors:
                return LeverResult(
                    lever=lever, passed=False,
                    saw=f"{len(errors)} console errors: {'; '.join(errors[:5])}"
                )
            return LeverResult(lever=lever, passed=True, saw="no console errors")

        elif lever.action == "motion":
            return await _lever_motion(page, lever)

        elif lever.action == "sequence":
            return await _lever_sequence(page, lever, console_msgs)

        elif lever.action == "wait":
            await asyncio.sleep(lever.ms / 1000)
            return LeverResult(lever=lever, passed=True, saw=f"waited {lever.ms}ms")

        elif lever.action == "type":
            return await _lever_type(page, lever)

        elif lever.action == "autopilot":
            return await _lever_autopilot(page, lever, console_msgs)

        else:
            return LeverResult(
                lever=lever, passed=False,
                saw=f"unknown lever action: {lever.action}"
            )

    except Exception as e:
        return LeverResult(lever=lever, passed=False, saw=f"error: {str(e)[:200]}")


# ──────────────────── lever implementations ────────────────────


async def _lever_screenshot(page, lever: Lever, system_note: str | None = None) -> LeverResult:
    """Take a screenshot, describe it, and judge on OBSERVABLE facts only.

    Pass/fail rule (2026-04-13, post-tension-removal):
      PASS if the page has visible content (not blank, not solid-color).
      FAIL if the page is blank / near-empty / entirely one color — those are
        the real failure modes (App.tsx crashed, CSS broke, wrong mount point).

    The wave's `expect` string is still compared to what the VLM sees, but the
    verdict is surfaced as `detail` for the model to read. It does NOT gate
    pass/fail. Eddy-compare was producing false negatives on working apps
    (e.g. "saw shows '2' but expect says '?' initially" — both correct, one is
    post-click, one is pre-click — and wedged the agent in edit loops).
    """
    screenshot_bytes = await page.screenshot()
    stats, pixel_desc = _describe_screenshot(screenshot_bytes)

    vlm_desc = await _vlm_describe_screenshot(screenshot_bytes, system_note=system_note)
    desc = vlm_desc or pixel_desc

    # Observable pass criterion: page isn't blank. A blank page is a real
    # failure (mount crash, white screen of death). Signals:
    #   unique_colors < 5       — near-monochrome image, no content rendered
    #   dominant_pct > 0.985    — one color owns ~all pixels (solid fill)
    # Anti-aliasing and font rendering push a real app well above these
    # thresholds, so these only trip on genuinely empty pages.
    unique_colors = stats.get("unique_colors", 0)
    dominant_pct = stats.get("dominant_pct", 0.0)
    is_blank = unique_colors < 5 or dominant_pct > 0.985

    verdict = ""
    if lever.expect:
        verdict = await _eddy_compare(desc, lever.expect, system_note=system_note)

    if is_blank:
        return LeverResult(
            lever=lever, passed=False,
            saw=desc,
            detail=f"page appears blank ({unique_colors} colors, dominant {dominant_pct:.0%})"
        )
    return LeverResult(lever=lever, passed=True, saw=desc, detail=verdict)


async def _lever_press(page, lever: Lever, system_note: str | None = None) -> LeverResult:
    """Press a key, check if pixels or DOM changed."""
    dom_before = await page.evaluate("document.body.innerText")
    before = await page.screenshot()
    await page.keyboard.press(lever.key)
    await asyncio.sleep(0.5)
    after = await page.screenshot()
    dom_after = await page.evaluate("document.body.innerText")

    pixels_changed = _screenshots_differ(before, after)
    dom_changed = dom_before != dom_after
    changed = pixels_changed or dom_changed

    parts = []
    if pixels_changed:
        parts.append("pixels changed")
    if dom_changed:
        parts.append("DOM text changed")
    if not changed:
        parts.append("nothing changed")

    saw = f"pressed {lever.key}, {', '.join(parts)}"

    if lever.expect:
        verdict = await _eddy_compare(saw, lever.expect, system_note=system_note)
        passed = verdict.startswith("PASS")
        return LeverResult(lever=lever, passed=passed, saw=saw, detail=verdict)

    return LeverResult(lever=lever, passed=changed, saw=saw)


async def _lever_ghost_classes(page, lever: Lever) -> LeverResult:
    """Catch 'model wrote Tailwind but Tailwind isn't installed' failure mode.

    Collect every className token in the live DOM, then every class selector
    defined in every loaded stylesheet, and flag tokens that are declared in
    markup but never styled. If a deliverable uses 20+ className tokens and
    most of them don't resolve to any CSS rule, the page LOOKS rendered but
    looks bland/boxy because the utility classes the model reached for (the
    Tailwind training prior) were silently no-ops.

    Threshold: more than 30% ghost classes among tokens the model wrote →
    fail. The 30% tolerance accommodates BEM-style per-component classes
    that legitimately don't exist in the bundled CSS (they're declared on
    the element but styled by a parent selector, e.g. `.Card .Card-header`).
    Tailwind's usual spread is hundreds of utility tokens — when Tailwind is
    missing, ghost rate runs 70–95%, well above the floor.
    """
    result = await page.evaluate(r"""
        () => {
            // Every class token used in the live DOM
            const used = new Set()
            for (const el of document.querySelectorAll('*')) {
                for (const c of el.classList) used.add(c)
            }
            // Every class token DEFINED in any loaded stylesheet. Extract
            // `.foo` segments from each rule's selectorText (including
            // :hover, > child, etc.). Cross-origin sheets raise on access —
            // swallow and treat their contents as defined-unknown.
            const defined = new Set()
            const classRe = /\.([A-Za-z_][-\w]*)/g
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        const sel = rule.selectorText
                        if (!sel) continue
                        let m
                        classRe.lastIndex = 0
                        while ((m = classRe.exec(sel)) !== null) defined.add(m[1])
                    }
                } catch (e) { /* CORS-blocked sheet, ignore */ }
            }
            const ghosts = [...used].filter(c => !defined.has(c))
            return {
                used_count: used.size,
                defined_count: defined.size,
                ghost_count: ghosts.length,
                ghosts: ghosts.slice(0, 15),
            }
        }
    """)
    used = result.get("used_count", 0) or 0
    ghost = result.get("ghost_count", 0) or 0
    ghosts = result.get("ghosts", [])
    if used < 5:
        return LeverResult(lever=lever, passed=True,
                           saw=f"only {used} class tokens in DOM — too few to judge")
    ghost_rate = ghost / used
    if ghost_rate > 0.30:
        return LeverResult(
            lever=lever, passed=False,
            saw=(f"{ghost}/{used} class tokens ({ghost_rate:.0%}) don't match any CSS rule — "
                 f"the page uses Tailwind-style utilities without Tailwind installed, "
                 f"or classes with typos"),
            detail=f"unresolved: {', '.join(ghosts[:10])}",
        )
    return LeverResult(lever=lever, passed=True,
                       saw=f"{used} class tokens, {ghost} unresolved ({ghost_rate:.0%}) — styling wired up")


async def _lever_click(page, lever: Lever) -> LeverResult:
    """Click a selector, report if anything changed (pixels or DOM).

    Uses page.locator() (modern playwright API) which handles both plain CSS
    and combined selectors like "button >> nth=0". query_selector does CSS
    only — and CSS :nth-of-type is parent-scoped, which misfires on any
    layout where buttons live in sibling containers (NES d-pad, action rows).
    """
    try:
        locator = page.locator(lever.selector)
        count = await locator.count()
        if count == 0:
            return LeverResult(
                lever=lever, passed=False,
                saw=f"selector '{lever.selector}' not found on page"
            )
        # Use the first match; for "button >> nth=N" syntax this already
        # resolves to exactly one element, so .first is a no-op there.
        el = locator.first
        if not await el.is_visible():
            return LeverResult(
                lever=lever, passed=False,
                saw=f"'{lever.selector}' exists but is not visible"
            )
        # Two-phase baseline → the click has to cause a change BEYOND
        # whatever the page does on its own (setInterval tickers, CSS
        # transitions, auto-advancing carousels). A crypto dash with a 15s
        # price refresh used to fool us: dom_before != dom_after was true
        # purely from the timer tick, so the 'View Chart' dead button passed
        # QA. Measure the noise floor first, then require the click to
        # introduce lines the baseline didn't.
        def _lines(text: str) -> set[str]:
            return {l for l in text.split("\n") if l.strip()}

        dom_t0 = await page.evaluate("document.body.innerText")
        before = await page.screenshot()
        await asyncio.sleep(0.5)
        dom_t05 = await page.evaluate("document.body.innerText")
        noise_added = _lines(dom_t05) - _lines(dom_t0)
        noise_removed = _lines(dom_t0) - _lines(dom_t05)
        # First try a normal click. If playwright's actionability check times
        # out (button covered by overlay / absolutely-positioned sibling /
        # tight-packed UI like a NES d-pad), retry with force=True which
        # bypasses actionability. Injected exploratory clicks care only that
        # the onClick fires, not that the pointer path is perfectly clear.
        try:
            await el.click(timeout=2500)
        except Exception:
            await el.click(timeout=2500, force=True)
        await asyncio.sleep(0.5)
        after = await page.screenshot()
        dom_after = await page.evaluate("document.body.innerText")

        click_added = _lines(dom_after) - _lines(dom_t05)
        click_removed = _lines(dom_t05) - _lines(dom_after)
        # Credit the click only for changes that aren't explained by the
        # baseline drift. A ticker cycling "$65021.34" → "$64988.12" will
        # land in both noise and click sets — subtract it off.
        specific_added = click_added - noise_added
        specific_removed = click_removed - noise_removed
        dom_changed_by_click = bool(specific_added or specific_removed)
        pixels_changed = _screenshots_differ(before, after)
        changed = pixels_changed or dom_changed_by_click

        parts = []
        if pixels_changed:
            parts.append("pixels changed")
        if dom_changed_by_click:
            parts.append(f"DOM text changed (+{len(specific_added)} -{len(specific_removed)} beyond baseline)")
        elif click_added or click_removed:
            parts.append("DOM change matched background ticker noise — click likely dead")
        if not changed:
            parts.append("nothing changed")

        saw = f"clicked '{lever.selector}', {', '.join(parts)}"
        return LeverResult(lever=lever, passed=changed, saw=saw)
    except Exception as e:
        return LeverResult(lever=lever, passed=False, saw=f"click failed: {e}")


async def _lever_type(page, lever: Lever) -> LeverResult:
    """Type a string into the first matching input/textarea.

    Uses page.locator(...).first so we don't fight with nth-of-type when
    inputs and non-inputs share parents (common in React component libraries
    where <input> is wrapped in <div>). The text to type lives in lever.expect
    since Lever has no dedicated text field — a small repurposing, documented
    at the injection site.
    """
    text = lever.expect or "hello world"
    try:
        # Grab the first visible input or textarea on the page. This is more
        # forgiving than a strict nth-of-type selector — React libraries often
        # wrap inputs in divs, which throws off document-level nth counts.
        locator = page.locator(
            'input:not([type="button"]):not([type="submit"]):not([type="checkbox"]):not([type="radio"])'
            ', textarea'
        ).first
        if await locator.count() == 0:
            return LeverResult(
                lever=lever, passed=False, saw="no fillable input found"
            )
        dom_before = await page.evaluate("document.body.innerText")
        before = await page.screenshot()
        # fill is one-shot; type is character-by-character. For "mirrors my
        # typing" apps the onChange-per-keystroke matters, so use type().
        await locator.click(timeout=2500, force=True)
        await locator.type(text, delay=15, timeout=5000)
        await asyncio.sleep(0.5)
        after = await page.screenshot()
        dom_after = await page.evaluate("document.body.innerText")

        pixels_changed = _screenshots_differ(before, after)
        dom_changed = dom_before != dom_after
        changed = pixels_changed or dom_changed
        parts = []
        if pixels_changed:
            parts.append("pixels changed")
        if dom_changed:
            parts.append("DOM text changed")
        if not changed:
            parts.append("nothing changed")
        saw = f"typed {text!r}, {', '.join(parts)}"
        return LeverResult(lever=lever, passed=changed, saw=saw)
    except Exception as e:
        return LeverResult(lever=lever, passed=False, saw=f"type failed: {e}")


async def _pull_static(lever: Lever, serve_dir: str) -> LeverResult:
    """Dispatch a static (non-browser) lever by action name. Static levers
    run against the filesystem — src/, dist/, package.json — without
    launching Playwright. Deterministic, ~100× faster than the browser
    path, and immune to load-timing / CORS quirks that bite the dynamic
    levers."""
    if lever.action == "ghost_classes":
        return _lever_ghost_classes_static(lever, serve_dir)
    if lever.action == "unused_dep":
        return _lever_unused_dep_static(lever, serve_dir)
    return LeverResult(
        lever=lever, passed=False,
        saw=f"unknown static lever action: {lever.action}",
    )


def _lever_ghost_classes_static(lever: Lever, serve_dir: str) -> LeverResult:
    """File-based ghost_classes — scan the built CSS bundle for class
    definitions, scan source TSX for className tokens, flag the delta.

    Why this is better than the browser version for most cases:
      - Deterministic (no DOM-ready / Tailwind-JIT race)
      - Fast (~10ms vs ~1000ms)
      - Sees the REAL compiled stylesheet (Tailwind JIT materialises
        utilities into dist/ at build time; source CSS doesn't have
        them, which is what tripped the browser version when the sheet
        access CORSed out)

    Tolerance: same 30% threshold as the dynamic version, for symmetry."""
    import re as _re
    from pathlib import Path as _P

    serve = _P(serve_dir).resolve()
    # dist/ usually sits one level up from the serve dir when we're
    # pointed at dist/assets/*.html, or inside serve_dir when we're
    # pointed at dist/ directly. Cover both.
    candidates = [serve, serve / "dist", serve.parent, serve.parent / "dist"]
    project_root = next((c for c in candidates if (c / "src").exists()), serve)

    src_dir = project_root / "src"
    dist_dir = project_root / "dist"
    if not src_dir.exists() or not dist_dir.exists():
        return LeverResult(
            lever=lever, passed=True,
            saw=f"static ghost_classes skipped (src={src_dir.exists()}, dist={dist_dir.exists()})",
        )

    # 1. className tokens from every .tsx / .ts / .jsx / .js / .html
    class_re = _re.compile(r'className\s*=\s*["\']([^"\']+)["\']')
    used: set[str] = set()
    for path in src_dir.rglob("*"):
        if path.suffix not in (".tsx", ".ts", ".jsx", ".js", ".html"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in class_re.finditer(text):
            for tok in m.group(1).split():
                # drop Tailwind modifiers for analysis — `hover:bg-red-500`
                # registers under `bg-red-500` in the output CSS.
                bare = tok.split(":")[-1]
                if bare: used.add(bare)

    # 2. class selectors from every dist/**/*.css (Tailwind JIT output)
    defined: set[str] = set()
    selector_re = _re.compile(r"\.([A-Za-z_][-\w\\/:\[\]%.]*)")
    for path in dist_dir.rglob("*.css"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in selector_re.finditer(text):
            # Tailwind v4 emits `.bg-red-500\/15` with escaped slashes for
            # opacity modifiers; normalise to the source token form.
            raw = m.group(1).replace("\\", "")
            # Strip pseudo-class / state suffix that leaked from selectors.
            bare = raw.split(":")[0].strip(".")
            if bare: defined.add(bare)

    ghosts = sorted(used - defined)
    if len(used) < 5:
        return LeverResult(
            lever=lever, passed=True,
            saw=f"static ghost_classes: only {len(used)} tokens found in src — too few to judge",
        )
    rate = len(ghosts) / len(used)
    preview = ", ".join(ghosts[:10])
    if rate > 0.30:
        return LeverResult(
            lever=lever, passed=False,
            saw=f"{len(ghosts)}/{len(used)} class tokens ({rate*100:.0f}%) don't match any CSS rule in dist/",
            detail=f"ghosts: {preview}",
        )
    return LeverResult(
        lever=lever, passed=True,
        saw=f"{len(ghosts)}/{len(used)} ghost classes ({rate*100:.0f}%) — within tolerance",
    )


def _lever_unused_dep_static(lever: Lever, serve_dir: str) -> LeverResult:
    """Flag any package.json dependency that isn't imported from src/.
    Catches scaffold-bundled libs the app never uses (e.g. pomodoro-
    timer ships recharts from the react-app template but never charts).

    Lever config:
      lever.selector = dependency name to check (e.g. "recharts"). If
      empty, every runtime dep is scanned and unused ones listed.
    """
    import json as _json
    from pathlib import Path as _P

    project_root = _P(serve_dir).resolve()
    while project_root != project_root.parent and not (project_root / "package.json").exists():
        project_root = project_root.parent
    pkg_path = project_root / "package.json"
    if not pkg_path.exists():
        return LeverResult(lever=lever, passed=True, saw="no package.json — skipped")

    try:
        pkg = _json.loads(pkg_path.read_text())
    except Exception:
        return LeverResult(lever=lever, passed=True, saw="package.json unparseable — skipped")

    deps = dict(pkg.get("dependencies") or {})
    if not deps:
        return LeverResult(lever=lever, passed=True, saw="no runtime deps")

    src_dir = project_root / "src"
    if not src_dir.exists():
        return LeverResult(lever=lever, passed=True, saw="no src/ — skipped")

    # Concatenate all source code for a single grep pass.
    blob_parts: list[str] = []
    for path in src_dir.rglob("*"):
        if path.suffix not in (".tsx", ".ts", ".jsx", ".js"):
            continue
        try:
            blob_parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    blob = "\n".join(blob_parts)

    unused: list[str] = []
    target = lever.selector.strip() if lever.selector else ""
    for name in deps:
        if target and name != target:
            continue
        # Match `from 'name'` / `from "name"` / `require('name')` /
        # dynamic import(). We only need ONE of these to say "used".
        if name in blob:
            # Broad check; follow up with a tighter regex only if needed.
            continue
        unused.append(name)

    if unused:
        return LeverResult(
            lever=lever, passed=False,
            saw=f"{len(unused)} dependency unused: {', '.join(unused)}",
            detail="remove from package.json, or use it",
        )
    return LeverResult(
        lever=lever, passed=True,
        saw=f"all {len(deps)} deps referenced in src/",
    )


async def _lever_autopilot(page, lever: Lever, console_msgs: list) -> LeverResult:
    """Interactive visual QA: exercise every clickable the deliverable
    exposes, verify the app stays alive and error-free across every
    reachable state.

    Intent (per operator): make sure the FINAL RESULT is correct — when
    the user clicks around, does the page keep rendering and responding?
    Back-nav is a nice-to-have for multi-screen apps (games, navs); for
    a single-view app, cycling through its buttons is enough. We try
    history.back() after a route change opportunistically but don't
    require it.

    Design:
      1. Enumerate visible clickables (buttons, links, role=button/
         menuitem/tab/link, nav a, [data-testid]). Skip disabled +
         zero-size + visually hidden.
      2. For up to `max_clicks`:
           - Pick first un-visited fingerprint (role|text|href).
           - Click. Wait for networkidle (capped 1.5s) + ~300ms.
           - Count new console.errors since pre-click.
           - Dismiss an open [role=dialog|alertdialog] via Esc.
           - If URL changed, try history.back() to continue exploring
             the original viewport; silent if back isn't available.
           - Re-enumerate — new menus/modals may have surfaced.
      3. Fail if total new errors exceed `max_errors_tolerated`.

    Passes when: every clicked element produced no new runtime errors
    and the page remained alive. Zero clickables is neutral (some apps
    are single-output views — a timer display with no buttons is still
    a valid deliverable shape, though rare).

    Future: graduate this to play the games the engine scaffolds
    produce. That needs input beyond clicks (WASD, pointer lock, mouse
    move), game-state introspection (score, alive flag, scene name),
    and long-horizon playthrough verification. Today's autopilot is a
    forms/dashboards-grade first pass — the clickable-walk bones
    generalise.
    """
    max_clicks = lever.max_clicks or 20
    err_budget = lever.max_errors_tolerated
    visited: set[str] = set()
    routes: list[str] = []
    clicked: list[str] = []
    errors_by_click: list[tuple[str, int]] = []

    # Snapshot the error baseline.
    baseline_errors = len(
        [t for typ, t in console_msgs if typ == "error"]
    )

    CANDIDATE_SELECTORS = (
        "button:not([disabled]):not([aria-disabled='true']), "
        "a[href]:not([href='#']):not([href='']), "
        "[role='button']:not([aria-disabled='true']), "
        "[role='menuitem']:not([aria-disabled='true']), "
        "[role='tab']:not([aria-disabled='true']), "
        "[role='link'], "
        "nav a, "
        "[data-testid]:is(button,a,[role='button'])"
    )

    async def _fingerprints() -> list[dict]:
        try:
            return await page.evaluate(r"""
                (sel) => {
                    const out = []
                    for (const el of document.querySelectorAll(sel)) {
                        const r = el.getBoundingClientRect()
                        if (r.width < 2 || r.height < 2) continue
                        // skip visually hidden
                        const cs = getComputedStyle(el)
                        if (cs.visibility === 'hidden' || cs.display === 'none') continue
                        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 60)
                        const role = el.getAttribute('role') || el.tagName.toLowerCase()
                        const href = el.getAttribute('href') || ''
                        out.push({
                            role, text, href,
                            fp: role + '|' + text + '|' + href,
                        })
                        if (out.length >= 50) break
                    }
                    return out
                }
            """, CANDIDATE_SELECTORS)
        except Exception:
            return []

    async def _click_first(fp: str) -> bool:
        """Locate an element by fingerprint and click it. Returns True
        if the click dispatched, False if the element vanished."""
        try:
            ok = await page.evaluate(r"""
                ({sel, fp}) => {
                    for (const el of document.querySelectorAll(sel)) {
                        const r = el.getBoundingClientRect()
                        if (r.width < 2 || r.height < 2) continue
                        const cs = getComputedStyle(el)
                        if (cs.visibility === 'hidden' || cs.display === 'none') continue
                        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 60)
                        const role = el.getAttribute('role') || el.tagName.toLowerCase()
                        const href = el.getAttribute('href') || ''
                        if ((role + '|' + text + '|' + href) === fp) {
                            el.scrollIntoView({block: 'center', inline: 'center'})
                            el.click()
                            return true
                        }
                    }
                    return false
                }
            """, {"sel": CANDIDATE_SELECTORS, "fp": fp})
            return bool(ok)
        except Exception:
            return False

    # --- Crawl loop ------------------------------------------------------
    pre_url = page.url
    routes.append(pre_url)
    for step in range(max_clicks):
        fps = await _fingerprints()
        # Pick the first unseen fingerprint.
        target = next((f for f in fps if f["fp"] not in visited), None)
        if target is None:
            # Exhausted. Try popping a nav: go back and see if anything new.
            try:
                if page.url != pre_url:
                    await page.go_back(timeout=3000)
                    await asyncio.sleep(0.3)
                    continue
            except Exception:
                pass
            break
        visited.add(target["fp"])

        pre_count = len(console_msgs)
        ok = await _click_first(target["fp"])
        if not ok:
            continue
        clicked.append(target["fp"])
        # Let the page settle. Cap aggressively — some SPAs fire infinite
        # animations on load and networkidle never lands.
        try:
            await page.wait_for_load_state("networkidle", timeout=1500)
        except Exception:
            pass
        await asyncio.sleep(0.3)

        # New console/page errors since the click?
        new_errs = [t for typ, t in console_msgs[pre_count:] if typ == "error"]
        if new_errs:
            errors_by_click.append((target["fp"], len(new_errs)))

        # Track route transitions.
        if page.url not in routes:
            routes.append(page.url)

        # Dismiss any modal/dialog that may have opened. Esc is the
        # canonical close for well-behaved ARIA dialogs.
        try:
            has_dialog = await page.evaluate(
                "document.querySelector('[role=\"dialog\"],[role=\"alertdialog\"]') !== null"
            )
            if has_dialog:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
        except Exception:
            pass

        # If we're on a different route now, hop back so the next iter
        # enumerates the same viewport's clickables.
        try:
            if page.url != pre_url:
                await page.go_back(timeout=3000)
                await asyncio.sleep(0.3)
        except Exception:
            pass

    # --- Tally -----------------------------------------------------------
    total_errs = sum(n for _, n in errors_by_click)
    route_count = len(routes)
    saw = (
        f"clicked {len(clicked)} unique elements, "
        f"visited {route_count} route(s), "
        f"{total_errs} new console error(s) across {len(errors_by_click)} "
        f"clicks (budget {err_budget})"
    )
    if total_errs > err_budget:
        err_preview = "; ".join(
            f"{fp}→{n}err" for fp, n in errors_by_click[:3]
        )
        return LeverResult(
            lever=lever, passed=False,
            saw=f"AUTOPILOT FAIL: {saw}",
            detail=f"First offenders: {err_preview}",
        )
    if len(clicked) == 0:
        return LeverResult(
            lever=lever, passed=True,
            saw=f"autopilot found no clickables (single-view, non-interactive)",
        )
    return LeverResult(
        lever=lever, passed=True,
        saw=saw,
        detail=f"routes: {routes[:5]}",
    )


async def _lever_motion(page, lever: Lever) -> LeverResult:
    """Check if the scene is alive — take screenshots over time, compare.

    If nothing moves in 3 seconds, physics aren't running.
    This is the tension between "should be animated" and "is static."
    """
    frames = []
    for i in range(4):
        frames.append(await page.screenshot())
        if i < 3:
            await asyncio.sleep(1)

    # Compare consecutive frames
    changes = 0
    for i in range(len(frames) - 1):
        if _screenshots_differ(frames[i], frames[i + 1], threshold=0.005):
            changes += 1

    total_comparisons = len(frames) - 1
    saw = f"{changes}/{total_comparisons} frames showed motion over {total_comparisons}s"

    if changes == 0:
        return LeverResult(
            lever=lever, passed=False,
            saw=f"STATIC: {saw} — nothing is moving, physics may not be running"
        )
    elif changes < total_comparisons:
        return LeverResult(
            lever=lever, passed=True,
            saw=f"PARTIAL: {saw} — some animation detected"
        )
    else:
        return LeverResult(
            lever=lever, passed=True,
            saw=f"ALIVE: {saw} — scene is animated"
        )


async def _lever_sequence(page, lever: Lever, console_msgs: list) -> LeverResult:
    """Execute a sequence of actions and check the outcome.

    lever.expect contains a pipe-separated sequence like:
    "press Space|wait 2000|motion"

    Each step runs in order. Fails if any step fails.
    """
    steps = lever.expect.split("|") if lever.expect else []
    if not steps:
        return LeverResult(lever=lever, passed=False, saw="sequence has no steps")

    results = []
    for step in steps:
        step = step.strip()
        if step.startswith("press "):
            key = step.split(" ", 1)[1]
            sub = await _pull_one(page, Lever(action="press", key=key), console_msgs)
        elif step.startswith("wait "):
            ms = int(step.split(" ", 1)[1])
            await asyncio.sleep(ms / 1000)
            sub = LeverResult(lever=Lever(action="wait"), passed=True, saw=f"waited {ms}ms")
        elif step == "motion":
            sub = await _lever_motion(page, Lever(action="motion"))
        elif step.startswith("screenshot"):
            sub = await _lever_screenshot(page, Lever(action="screenshot"))
        else:
            sub = LeverResult(lever=Lever(action=step), passed=False, saw=f"unknown step: {step}")
        results.append(sub)

    failed = [r for r in results if not r.passed]
    all_saw = " → ".join(r.saw[:60] for r in results)

    if failed:
        return LeverResult(
            lever=lever, passed=False,
            saw=f"sequence failed at: {failed[0].saw}",
            detail=all_saw
        )
    return LeverResult(lever=lever, passed=True, saw=all_saw)


async def _lever_read_text(page, lever: Lever, system_note: str | None = None) -> LeverResult:
    """Read text content from a selector."""
    try:
        text = await page.evaluate(
            f"(() => {{ const el = document.querySelector('{lever.selector}'); "
            f"if (!el) return '(not found)'; "
            f"return el.value || el.innerText || el.textContent || '(empty)'; }})()"
        )
        saw = f"'{lever.selector}' says: {text[:200]}"

        if lever.expect:
            verdict = await _eddy_compare(saw, lever.expect, system_note=system_note)
            passed = verdict.startswith("PASS")
            return LeverResult(lever=lever, passed=passed, saw=saw, detail=verdict)

        return LeverResult(lever=lever, passed=text != "(not found)", saw=saw)
    except Exception as e:
        return LeverResult(lever=lever, passed=False, saw=f"read failed: {e}")


# ──────────────────── helpers ────────────────────


def _describe_screenshot(screenshot_bytes: bytes) -> tuple[dict, str]:
    """Convert screenshot to text description. Pure pixels, no opinions."""
    stats = {}
    lines = []

    try:
        from PIL import Image
        from collections import Counter
        import io

        img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        w, h = img.size
        pixels = list(img.getdata())
        total = len(pixels)
        stats["width"] = w
        stats["height"] = h

        step = max(1, total // 10000)
        sampled = pixels[::step]
        n = len(sampled)

        color_counts = Counter(sampled)
        unique = len(color_counts)
        top_color, top_count = color_counts.most_common(1)[0]
        dominant_pct = top_count / n

        near_black = sum(1 for r, g, b in sampled if r < 20 and g < 20 and b < 20) / n
        near_white = sum(1 for r, g, b in sampled if r > 240 and g > 240 and b > 240) / n
        avg_brightness = sum(sum(c) / 3 for c in sampled) / n

        stats.update({
            "unique_colors": unique,
            "dominant_color": top_color,
            "dominant_pct": dominant_pct,
            "near_black_pct": near_black,
            "avg_brightness": avg_brightness,
        })

        lines.append(f"{w}x{h}, {unique} unique colors, avg brightness {avg_brightness:.0f}/255")
        lines.append(f"{near_black:.0%} near-black, {near_white:.0%} near-white")
        lines.append(f"dominant color: rgb{top_color} at {dominant_pct:.0%}")

        # Quadrant breakdown
        for name, box in [
            ("top-left", (0, 0, w // 2, h // 2)),
            ("top-right", (w // 2, 0, w, h // 2)),
            ("center", (w // 4, h // 4, 3 * w // 4, 3 * h // 4)),
            ("bottom-left", (0, h // 2, w // 2, h)),
            ("bottom-right", (w // 2, h // 2, w, h)),
        ]:
            region = img.crop(box)
            rpx = list(region.getdata())
            ravg = sum(sum(c) / 3 for c in rpx) / len(rpx) if rpx else 0
            rblack = sum(1 for r, g, b in rpx if r < 20 and g < 20 and b < 20) / len(rpx) if rpx else 0
            runiq = len(set(rpx[::max(1, len(rpx) // 500)]))
            lines.append(f"  {name}: brightness={ravg:.0f}, {rblack:.0%} black, {runiq} colors")

        img.save("/tmp/undertow_screenshot.png")

    except ImportError:
        lines.append("(PIL not available)")
    except Exception as e:
        lines.append(f"(error: {e})")

    return stats, "\n".join(lines)


def _screenshots_differ(before_bytes: bytes, after_bytes: bytes, threshold: float = 0.01) -> bool:
    """Do two screenshots differ by more than threshold?"""
    try:
        from PIL import Image
        import io

        img_a = Image.open(io.BytesIO(before_bytes)).convert("RGB")
        img_b = Image.open(io.BytesIO(after_bytes)).convert("RGB")

        px_a = list(img_a.getdata())
        px_b = list(img_b.getdata())

        if len(px_a) != len(px_b):
            return True

        step = max(1, len(px_a) // 5000)
        diffs = sum(
            1 for i in range(0, len(px_a), step)
            if px_a[i] != px_b[i]
        )
        ratio = diffs / (len(px_a) // step)
        return ratio > threshold

    except Exception:
        return False  # can't tell, assume no change


async def _vlm_describe_screenshot(
    screenshot_bytes: bytes,
    system_note: str | None = None,
) -> str | None:
    """Ask the eddy (which is multimodal Gemma-4) to describe the screenshot.

    Returns a short semantic description ("A note-taking app with a textarea
    and two buttons") or None on failure. The pixel-stats description is kept
    as a fallback — if this VLM path succeeds, the caller should prefer it
    because the downstream _eddy_compare() judges semantic match, not pixel
    match.

    `system_note`, when provided, is a direction-set markdown body appended
    to the system prompt. It steers the VLM toward specific questions
    (brand cohesion, bug symptoms, game juice, …) rather than the generic
    one-sentence describe. See `pick_direction_set`.
    """
    # VLM-based screenshot description is DEFERRED since 2026-04-26.
    # Was POSTing to BEE_ENDPOINT (Qwen3.6/Gemma multimodal) which was
    # retired with the local-LLM stack. Short-circuit to None so the
    # caller falls back to _describe_screenshot() pixel-stats without
    # burning a 120s timeout. Re-enable by replacing this body with a
    # Claude vision API call (anthropic.Anthropic().messages.create with
    # image content + the system_content prompt below).
    log.debug("_vlm_describe_screenshot: skipped (VLM endpoint deferred)")
    return None

    # Preserved below for future re-enablement — see docstring above.
    import base64
    b64 = base64.b64encode(screenshot_bytes).decode()
    system_base = (
        "You are a UI describer. One sentence: what is visible on screen "
        "(page title, main elements, layout). Be concrete."
    )
    system_content = (
        f"{system_base}\n\nWhen forming the sentence, let the following "
        f"direction set bias what you mention:\n\n{system_note}"
        if system_note else system_base
    )
    try:
        # 120s timeout — under heavy QA load the gpu_sem queue can delay
        # multimodal calls 2-3 min. Better to wait than fall back to pixel
        # stats (which will fail the semantic compare). If the VLM call
        # genuinely dies, the fallback to _describe_screenshot() still works.
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{BEE_ENDPOINT}/v1/chat/completions",
                json={
                    "model": "tsunami",
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": [
                            {"type": "text", "text": "Describe this screenshot in one sentence."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ]},
                    ],
                    "max_tokens": 120,
                    "temperature": 0.1,
                    "adapter": "none",  # base-model chat; no lora for describe
                    # Qwen3.6 thinking mode eats budget on short QA — disable.
                    # qwen36 ChatRequest accepts enable_thinking as a
                    # top-level field, not nested in chat_template_kwargs.
                    "enable_thinking": False,
                },
                headers={"Authorization": "Bearer not-needed"},
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                # Collapse to one line
                return content.split("\n")[0][:300]
    except Exception as e:
        log.debug(f"VLM describe failed: {e}")
    return None


async def _eddy_compare(
    saw: str,
    expected: str,
    system_note: str | None = None,
) -> str:
    """Ask the eddy: does what we saw match what was expected?

    The eddy is dumb. It just says PASS or FAIL and what it noticed.

    `system_note`, when provided, is a direction-set markdown body
    (Questions + PASS/FAIL criteria) appended to the system prompt.
    The eddy still emits PASS/FAIL on the single expected-vs-saw
    comparison, but is now primed to weigh the checklist. See
    `pick_direction_set`.
    """
    # Eddy/VLM compare is DEFERRED since 2026-04-26. Was POSTing to
    # BEE_ENDPOINT (Qwen3.6) which was retired with the local-LLM stack.
    # Short-circuit to UNCLEAR so callers know the semantic compare is
    # unavailable, without burning a 20s timeout. Re-enable by replacing
    # this body with a Claude API call using the prompt structure below.
    log.debug("_eddy_compare: skipped (VLM endpoint deferred)")
    return "UNCLEAR: VLM compare deferred (Generations TBD)"

    # Preserved below for future re-enablement — see docstring above.
    prompt = f"""Expected: {expected}
Saw: {saw}

Does what was seen satisfy what was expected? Be reasonable — if the expectation is "score display visible" and you see "SCORE: 0", that's a PASS.

One line:
PASS: [why it matches]
FAIL: [what's wrong]"""

    system_base = "You are QA. One line answers only."
    system_content = (
        f"{system_base}\n\nApply the following direction set as the rubric "
        f"for your yes/no:\n\n{system_note}"
        if system_note else system_base
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{BEE_ENDPOINT}/v1/chat/completions",
                json={
                    "model": "qwen",
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 80,
                    "temperature": 0.1,
                    # Qwen3.6 thinking eats short QA budget — disable.
                    # qwen36 ChatRequest accepts enable_thinking as a
                    # top-level field, not nested in chat_template_kwargs.
                    "enable_thinking": False,
                },
                headers={"Authorization": "Bearer not-needed"},
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                # Take first line only
                return content.split("\n")[0]
    except Exception as e:
        log.debug(f"Eddy compare failed: {e}")

    return "UNCLEAR: eddy unavailable"


# ──────────────────── direction sets ────────────────────


@dataclass
class _DirectionSet:
    """Parsed undertow_scaffolds/*.md file."""
    path: Path
    name: str
    applies_to: tuple[str, ...]
    phase: str
    weight: str
    body: str


def _parse_direction_set(path: Path) -> _DirectionSet | None:
    """Parse an undertow_scaffolds/*.md file.

    Frontmatter is a YAML-ish block bounded by `---` lines at top. Keys:
      name        : str
      applies_to  : [scaffold, scaffold, ...] or ["*"]
      phase       : deliver|polish|fix|audit  (or "*")
      weight      : strict|advisory

    Body is everything after the second `---`. Files without frontmatter
    are rejected — we want the schema contract to be explicit.
    """
    try:
        text = path.read_text()
    except Exception:
        return None
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return None
    head, body = m.group(1), m.group(2).strip()

    fields: dict[str, str] = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fields[k.strip().lower()] = v.strip()

    name = fields.get("name", path.stem)
    phase = fields.get("phase", "deliver") or "deliver"
    weight = fields.get("weight", "advisory") or "advisory"

    raw_applies = fields.get("applies_to", "")
    # Accept JSON-style list, bare word, or comma-list.
    raw_applies = raw_applies.strip()
    if raw_applies.startswith("[") and raw_applies.endswith("]"):
        raw_applies = raw_applies[1:-1]
    applies = tuple(
        tok.strip().strip('"').strip("'")
        for tok in raw_applies.split(",")
        if tok.strip()
    ) or ("*",)

    return _DirectionSet(
        path=path,
        name=name,
        applies_to=applies,
        phase=phase,
        weight=weight,
        body=body,
    )


def _load_direction_sets(scaffold_dir: Path) -> list[_DirectionSet]:
    if not scaffold_dir.is_dir():
        return []
    out: list[_DirectionSet] = []
    for path in sorted(scaffold_dir.glob("*.md")):
        ds = _parse_direction_set(path)
        if ds is not None:
            out.append(ds)
    return out


def pick_direction_set(
    task: str,
    scaffold: str,
    phase: str = "deliver",
    scaffold_dir: Path | None = None,
    allow_fallback: bool = True,
    style_name: str | None = None,
) -> str | None:
    """Pick the undertow_scaffolds/*.md body matching (scaffold, phase).

    Returns the markdown body (Questions + PASS/FAIL sections) that the
    caller passes as `system_note` into `_eddy_compare` and
    `_vlm_describe_screenshot`. Returns None when nothing fits — in which
    case the eddy/VLM run their baseline prompts unchanged.

    Selection order:
      0. If `style_name` is provided and matches an undertow_scaffolds/
         file (e.g., `photo_studio.md`), return that body — doctrine-
         specific rubrics beat scaffold-specific ones. Strip optional
         `seed_` prefix so `seed_photo_studio` → `photo_studio.md`.
      1. Filter files whose `applies_to` contains `scaffold` or "*" AND
         whose `phase` matches `phase` or "*".
      2. Prefer weight=strict over weight=advisory.
      3. Tie-break by lexicographic filename (deterministic, cheap).
      4. When `allow_fallback` and no specific match, return the body of
         `web_polish.md` if it exists and its applies_to covers "*".

    `task` is accepted for future keyword routing (mirroring
    `pick_scaffold`) but not yet consulted — scaffold+phase is the primary
    routing signal. Adding task keywords later is non-breaking.
    """
    del task  # reserved for keyword routing; currently unused
    root = scaffold_dir or (Path(__file__).parent / "undertow_scaffolds")

    # Step 0: doctrine-specific rubric
    if style_name:
        base = style_name[5:] if style_name.startswith("seed_") else style_name
        doctrine_path = root / f"{base}.md"
        if doctrine_path.is_file():
            return doctrine_path.read_text()

    sets = _load_direction_sets(root)
    if not sets:
        return None

    def _matches(ds: _DirectionSet) -> bool:
        scaffold_ok = scaffold in ds.applies_to or "*" in ds.applies_to
        phase_ok = ds.phase == phase or ds.phase == "*"
        return scaffold_ok and phase_ok

    matches = [ds for ds in sets if _matches(ds)]
    # web_polish.md is the generic fallback — it should not win against a
    # domain-specific file. Demote it to last by moving it out of the main
    # match list when other matches exist.
    specific = [ds for ds in matches if ds.path.stem != "web_polish"]
    if specific:
        specific.sort(key=lambda ds: (0 if ds.weight == "strict" else 1, ds.path.name))
        return specific[0].body

    if allow_fallback:
        for ds in matches:
            if ds.path.stem == "web_polish":
                return ds.body
    return None


# ──────────────────── formatting ────────────────────


def format_report(report: QAReport) -> str:
    """Format QA report for the wave to read."""
    status = "PASS" if report.passed else "FAIL"
    lines = [f"QA: {status}"]

    for r in report.results:
        mark = "✓" if r.passed else "✗"
        lines.append(f"  {mark} [{r.lever.action}] {r.saw}")
        if r.detail and not r.passed:
            lines.append(f"    → {r.detail}")

    if report.console_errors:
        lines.append(f"\n  Console errors: {'; '.join(report.console_errors[:5])}")

    return "\n".join(lines)


# ──────────────────── convenience for backward compat ────────────────────


def generate_levers(user_request: str, html_content: str = "") -> list[Lever]:
    """Generate test levers from what's in the HTML.

    Doesn't guess. Finds every testable surface in the code:
    - Every element ID → read_text lever
    - Every key binding → press lever
    - Every clickable thing → click lever
    - Always: console check + screenshot with expectation

    Also flags what SHOULD be testable but ISN'T — the tension.
    """
    import re
    levers: list[Lever] = []

    # Always start with console. Initial screenshot with no compare — just a
    # baseline snapshot; the user_request compare runs AFTER interactions so
    # that apps requiring a click (dice roller, counter, color picker) are
    # judged on their post-interaction state, not their initial placeholder.
    levers.append(Lever(action="console"))
    levers.append(Lever(action="screenshot"))

    if not html_content:
        # No HTML to inspect → judge the single screenshot we have against
        # the user's expectation. Static content, no interaction needed.
        levers[-1] = Lever(action="screenshot", expect=user_request)
        return levers

    # Find every element ID → read its text
    # No expect = just check it exists and has content. Pure fact check.
    ids = re.findall(r'id=["\']([^"\']+)["\']', html_content)
    for eid in ids:
        levers.append(Lever(action="read_text", selector=f"#{eid}"))

    # Find every key binding → press it
    # For press levers, expect="" means "just check if screen changed"
    # The undertow uses pixel diff, no eddy needed
    key_names = re.findall(
        r"""['"](Arrow(?:Left|Right|Up|Down)|Space|Enter|Escape|"""
        r"""Key[A-Z]|Digit\d|Tab|Backspace|Delete)['"]""",
        html_content
    )
    seen_keys = set()
    for key in key_names:
        if key in seen_keys:
            continue
        seen_keys.add(key)
        levers.append(Lever(action="press", key=key))

    # Find clickable elements
    # Buttons with IDs
    buttons = re.findall(r'<button[^>]*id=["\']([^"\']+)', html_content)
    for btn in buttons:
        levers.append(Lever(action="click", selector=f"#{btn}"))
    # If no ID buttons, try first few buttons by index
    if not buttons:
        button_count = len(re.findall(r'<button\b', html_content))
        for i in range(min(button_count, 3)):
            levers.append(Lever(action="click", selector=f"button:nth-of-type({i+1})"))

    # Detect if this is a game/animation — add motion check
    has_animation = bool(re.search(
        r'requestAnimationFrame|setInterval|animate|gameLoop|update\(|\.render\(',
        html_content
    ))
    has_physics = bool(re.search(
        r'velocity|gravity|collision|physics|cannon|ammo|rapier|matter',
        html_content, re.I
    ))

    if has_animation or has_physics:
        # Check if the scene is alive (things moving on their own)
        levers.append(Lever(action="motion"))

    # For games with a launch/start mechanic, test the play sequence
    if has_physics and 'Space' in seen_keys:
        # Launch sequence: press space (launch), wait for physics, check motion
        levers.append(Lever(
            action="sequence",
            expect="press Space|wait 2000|motion"
        ))

    # End with screenshot after all interactions, judged against the user's
    # request. This is THE compare that decides PASS/FAIL for interactive apps.
    # (For static pages with no interactions, we already attached user_request
    # to the initial screenshot in the early-return above.)
    has_interactions = any(
        l.action in ("click", "press", "motion", "sequence") for l in levers
    )
    if has_interactions:
        levers.append(Lever(action="screenshot", expect=user_request))
    else:
        # No interactions queued → apply the compare to the first screenshot
        # so static content still gets judged.
        for i, l in enumerate(levers):
            if l.action == "screenshot" and not l.expect:
                levers[i] = Lever(action="screenshot", expect=user_request)
                break

    return levers


async def run_drag(
    html_path: str,
    port: int = 9876,
    user_request: str = "",
    scaffold: str | None = None,
    phase: str = "deliver",
    style_name: str | None = None,
) -> dict:
    """Full QA run — eddy generates test plan, undertow executes it.

    `scaffold` (e.g. "dashboard", "landing", "gamedev") selects an
    undertow_scaffolds/*.md direction set via `pick_direction_set`.
    When None, no direction set is applied — baseline eddy prompts run.
    `phase` is the lifecycle stage (deliver/polish/fix/audit); direction
    sets declare which phase they apply to.
    """
    # Read HTML for hints
    html_content = ""
    try:
        html_content = Path(html_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Load reference context if available (from research phase)
    reference_context = ""
    try:
        project_dir = Path(html_path).resolve().parent
        # Walk up to find reference.md (could be in project root or src/)
        for _ in range(4):
            ref_file = project_dir / "reference.md"
            if ref_file.exists():
                reference_context = ref_file.read_text()[:500]
                break
            project_dir = project_dir.parent
    except Exception:
        pass

    # Resolve the direction set once per run so every eddy/VLM call in the
    # lever loop gets the same rubric. Absent scaffold → None → baseline
    # prompts. pick_direction_set itself is cheap (sorted glob + regex),
    # but there's no reason to repeat it per-lever.
    system_note: str | None = None
    if scaffold or style_name:
        try:
            system_note = pick_direction_set(
                user_request, scaffold or "", phase, style_name=style_name
            )
            if system_note:
                log.info(
                    f"Undertow: direction set loaded for scaffold={scaffold} "
                    f"style={style_name} phase={phase} ({len(system_note)} chars)"
                )
        except Exception as e:
            log.debug(f"pick_direction_set failed: {e}")

    # Generate levers from user request
    if user_request:
        # Enrich the screenshot expectation with reference context
        expect = user_request
        if reference_context:
            expect = f"{user_request}. Reference details: {reference_context[:200]}"
        levers = generate_levers(expect, html_content)
        log.info(f"Undertow: generated {len(levers)} levers from request" +
                 (" (with reference)" if reference_context else ""))
    else:
        levers = [
            Lever(action="console"),
            Lever(action="screenshot"),
        ]

    report = await pull_levers(html_path, levers, port=port, system_note=system_note)

    # Flag untested features
    warnings = []
    tested_actions = {r.lever.action for r in report.results}
    if "press" not in tested_actions and user_request and any(
        w in user_request.lower() for w in ["game", "interactive", "keyboard", "control"]
    ):
        warnings.append("No keyboard interactions were tested")
    if "click" not in tested_actions and user_request and any(
        w in user_request.lower() for w in ["button", "click", "menu", "nav"]
    ):
        warnings.append("No click interactions were tested")

    # Convert to old format + compute code tension
    errors = []
    for r in report.results:
        if not r.passed:
            msg = r.saw
            if r.detail:
                msg += f" — {r.detail}"
            errors.append(msg)
    if report.console_errors:
        errors.extend([f"JS error: {e}" for e in report.console_errors])

    # Code tension = ratio of failed levers to total levers
    total = len(report.results)
    failed = sum(1 for r in report.results if not r.passed)
    code_tension = failed / total if total > 0 else 0.5

    return {
        "passed": report.passed,
        "errors": errors,
        "warnings": warnings,
        "code_tension": code_tension,
        "levers_total": total,
        "levers_failed": failed,
    }


def format_qa_report(result: dict) -> str:
    """Backward-compatible format."""
    status = "PASS" if result["passed"] else "FAIL"
    lines = [f"QA: {status}"]
    if result["errors"]:
        for e in result["errors"]:
            lines.append(f"  ✗ {e}")
    if result.get("warnings"):
        for w in result["warnings"]:
            lines.append(f"  ⚠ {w}")
    if result["passed"]:
        lines.append("\nAll checks passed.")
    return "\n".join(lines)
