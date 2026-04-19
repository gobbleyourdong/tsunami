# GAP — chrome-extension

## Purpose
Browser extension scaffold. Manifest v3, popup + content script +
background worker. Target: bookmark tools, highlighters, context-menu
utilities.

## Wire state
- **Not routed.** No plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 deliveries**.

## Structural blockers (known)
- Vision gate DOES NOT APPLY — extension runs in browser chrome, not
  a web page we can screenshot.
- Manifest v3 service-worker lifecycle: drones use v2 patterns
  (persistent background page) that v3 rejects.
- Extension testing needs to load the unpacked extension into a
  headless browser — more setup than the other scaffolds.

## Churn lever
1. Add `plan_scaffolds/chrome-extension.md` — sections: Manifest,
   Popup, Content, Background, Permissions, Build.
2. Pin manifest v3. Include a valid manifest.json stub and forbid
   v2 fields in the prompt.
3. Delivery gate: playwright loads the built `dist/`, exercises the
   popup, asserts a state change (counter increments, selection
   highlights, etc.).
4. Ship: link-grabber, text-highlighter, tab-organizer.

## Out of scope
- Firefox / Safari manifest variants (chrome only to start).
- Publishing to the Web Store.

## Test suite (inference-free)
Playwright with `--load-extension=<dist>`. Exercises popup DOM and
asserts on in-page behavior. Parallel-safe — each instance gets its
own user-data-dir.

## Success signal
Extension loads, popup renders, click flow produces the expected
state change, no manifest v3 violations in chrome://extensions.
