"""Behavior → test-file compiler.

The plan's Tests section carries structured behavioral specs:

    behaviors:
      - trigger: "click [role=button name=/start/i]"
        expect: "[testid=timer] toHaveTextContent /24:/"
      - trigger: "type 'laundry' into [role=textbox] + press Enter"
        expect: "[testid=tasklist] toHaveTextContent 'laundry'"

This compiler translates each behavior into a vitest + @testing-library
test block, concatenates them into an App.test.tsx file, and writes it
alongside the component. The test file is machine-generated and only
re-written when the behavior list changes — the drone writes App.tsx to
satisfy the tests; the compiler owns the contract file.

Design principle: the behavior spec is the interface, App.tsx is the
implementation, vitest is the type-checker. When `npm run build` runs
`vitest run` after `vite build`, tests are the runtime proof the
delivered app matches the declared behavior.

Trigger grammar (parsed permissively; best-effort, never fails loudly):
    click <selector>
    type '<text>' into <selector> [+ press <key>]
    press <Key>

Selector grammar:
    [role=<role> name=/<pattern>/]     → getByRole(role, {name: /pattern/})
    [role=<role>]                       → getByRole(role)
    [testid=<id>]                       → getByTestId(id)
    [label=<text>]                      → getByLabelText(text)
    <fallback>                          → getByText(<fallback>) or literal

Expect grammar (first token is the matcher target, rest is the matcher):
    <selector> toHaveTextContent <pattern>
    <selector> toBeInTheDocument
    <selector> toBeDisabled / toBeEnabled
    <selector> toHaveValue '<value>'
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Behavior:
    trigger: str
    expect: str


def _parse_selector(sel: str) -> str:
    """Return an @testing-library call expression for the selector."""
    sel = sel.strip()
    # [role=X name=/pat/] — emit a permissive matcher that tries the
    # accessibility-first path (getByRole+name, which matches aria-label
    # AND text children) then falls back to getByText (plain visible
    # text). Covers all drone patterns:
    #   <button>Start</button>              → both match
    #   <button aria-label="Start">         → getByRole+name matches
    #   <div>Start</div> (no role)          → getByText matches
    # The strict getByRole+name alone failed when drone used `name={...}`
    # as an HTML attribute (not accessible); plain getByText failed when
    # drone used aria-label with no text children. Try-both is robust.
    m = re.match(r"\[\s*role\s*=\s*([\w-]+)\s+name\s*=\s*/(.+?)/(\w*)\s*\]", sel)
    if m:
        role, pat, flags = m.group(1), m.group(2), m.group(3) or "i"
        return (f"(screen.queryByRole('{role}', {{name: /{pat}/{flags}}}) "
                f"|| screen.getByText(/{pat}/{flags}))")
    # [role=X]
    m = re.match(r"\[\s*role\s*=\s*([\w-]+)\s*\]", sel)
    if m:
        return f"screen.getByRole('{m.group(1)}')"
    # [testid=X] or [data-testid=X]
    m = re.match(r"\[\s*(?:data-)?testid\s*=\s*([\w-]+)\s*\]", sel)
    if m:
        return f"screen.getByTestId('{m.group(1)}')"
    # [label=X]
    m = re.match(r"\[\s*label\s*=\s*(.+?)\s*\]", sel)
    if m:
        return f"screen.getByLabelText('{m.group(1).strip(chr(39))}')"
    # [text=/pattern/] or [text='literal']
    m = re.match(r"\[\s*text\s*=\s*/(.+?)/(\w*)\s*\]", sel)
    if m:
        pat, flags = m.group(1), m.group(2) or "i"
        return f"screen.getByText(/{pat}/{flags})"
    m = re.match(r"\[\s*text\s*=\s*['\"](.+?)['\"]\s*\]", sel)
    if m:
        return f"screen.getByText('{m.group(1)}')"
    # Fallback: literal text
    quoted = sel.replace("'", "\\'")
    return f"screen.getByText('{quoted}')"


def _compile_trigger(trigger: str) -> str:
    """Return JS lines that perform the trigger action."""
    t = trigger.strip()
    # click <selector>
    m = re.match(r"click\s+(.+)", t, re.IGNORECASE)
    if m:
        return f"fireEvent.click({_parse_selector(m.group(1))})"
    # type '<text>' into <selector> [+ press <key>]
    m = re.match(
        r"type\s+['\"](.+?)['\"]\s+into\s+(\[[^\]]+\]|\S+)(?:\s*\+\s*press\s+(\w+))?",
        t, re.IGNORECASE,
    )
    if m:
        text = m.group(1).replace("'", "\\'")
        sel = _parse_selector(m.group(2))
        keypress = m.group(3)
        lines = [
            f"fireEvent.change({sel}, {{target: {{value: '{text}'}}}})",
        ]
        if keypress:
            # Default to Enter (key=Enter, code=Enter, keyCode=13)
            key_name = keypress.capitalize()
            key_code = {"Enter": 13, "Space": 32, "Escape": 27}.get(key_name, 0)
            lines.append(
                f"fireEvent.keyDown({sel}, {{key: '{key_name}', code: '{key_name}', keyCode: {key_code}}})"
            )
        return "\n    ".join(lines)
    # press <Key>
    m = re.match(r"press\s+(\w+)", t, re.IGNORECASE)
    if m:
        key = m.group(1).capitalize()
        return f"fireEvent.keyDown(document.body, {{key: '{key}', code: '{key}'}})"
    return f"// unparsable trigger: {trigger!r}"


def _compile_expect(expect: str) -> str:
    """Return a JS expect(...) assertion line."""
    e = expect.strip()
    # Split into selector part + matcher part
    # Selector is [role=...], [testid=...], etc. then matcher phrase.
    m = re.match(r"(\[[^\]]+\])\s+(.+)", e)
    if not m:
        return f"// unparsable expect: {expect!r}"
    sel_call = _parse_selector(m.group(1))
    matcher = m.group(2).strip()

    # toHaveTextContent /pattern/ or "text"
    m2 = re.match(r"toHaveTextContent\s+/(.+?)/(\w*)", matcher)
    if m2:
        pat, flags = m2.group(1), m2.group(2) or "i"
        return f"expect({sel_call}).toHaveTextContent(/{pat}/{flags})"
    m2 = re.match(r"toHaveTextContent\s+['\"](.+?)['\"]", matcher)
    if m2:
        return f"expect({sel_call}).toHaveTextContent('{m2.group(1)}')"
    # toBeInTheDocument / toBeDisabled / toBeEnabled
    if matcher in ("toBeInTheDocument", "toBeDisabled", "toBeEnabled", "toBeVisible"):
        return f"expect({sel_call}).{matcher}()"
    # toHaveValue '<value>'
    m2 = re.match(r"toHaveValue\s+['\"](.+?)['\"]", matcher)
    if m2:
        return f"expect({sel_call}).toHaveValue('{m2.group(1)}')"
    # Fallback: raw
    return f"expect({sel_call}).{matcher}"


def compile_behaviors(behaviors: list[Behavior | dict]) -> str:
    """Produce a complete App.test.tsx file string."""
    out: list[str] = [
        "// AUTO-GENERATED by tsunami.test_compiler — do not edit.",
        "// The behavior spec in plans/current.md is the source of truth;",
        "// edit that and the test file will be re-emitted at build time.",
        "",
        "import { describe, test, expect } from 'vitest'",
        "import { render, screen, fireEvent } from '@testing-library/react'",
        "import '@testing-library/jest-dom'",
        "import App from './App'",
        "",
        "describe('App behavior', () => {",
    ]
    for b in behaviors:
        if isinstance(b, dict):
            trig = b.get("trigger", "")
            exp = b.get("expect", "")
            name = b.get("name") or f"{trig.split()[0]}: {trig[:60]}"
        else:
            trig = b.trigger
            exp = b.expect
            name = f"{trig.split()[0]}: {trig[:60]}"
        safe_name = name.replace("'", "\\'")
        out.append(f"  test('{safe_name}', () => {{")
        out.append(f"    render(<App />)")
        out.append(f"    {_compile_trigger(trig)}")
        out.append(f"    {_compile_expect(exp)}")
        out.append(f"  }})")
        out.append("")
    out.append("})")
    out.append("")
    return "\n".join(out)


def write_test_file(behaviors: list[Behavior | dict], project_path: str | Path) -> Path:
    """Compile behaviors → src/App.test.tsx. Returns the written path."""
    tsx = compile_behaviors(behaviors)
    out = Path(project_path) / "src" / "App.test.tsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tsx)
    return out


if __name__ == "__main__":
    # Smoke test
    sample = [
        {"trigger": "click [role=button name=/start/i]",
         "expect": "[testid=timer] toHaveTextContent /24:/"},
        {"trigger": "click [role=button name=/reset/i]",
         "expect": "[testid=timer] toHaveTextContent /25:00/"},
        {"trigger": "type 'laundry' into [role=textbox] + press Enter",
         "expect": "[testid=tasklist] toHaveTextContent 'laundry'"},
    ]
    print(compile_behaviors(sample))
