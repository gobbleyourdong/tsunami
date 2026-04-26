"""Regenerate scaffolds/<scaffold>/scaffold.yaml from the TS interfaces.

The scaffold.yaml is the drone-facing contract for which props exist on
each component. If it drifts from the actual TS types, drones hallucinate
props that cause build failures. This script parses each component's
`interface <Name>Props` block and emits a YAML declaration that mirrors
reality. Run after any scaffold UI change.

Usage:
    python3 -m tsunami.scripts.regen_scaffold_yaml [scaffold_name]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _extract_props(src: str, name: str) -> str:
    """Find `interface <name>Props ... { ... }` and return a compact
    comma-separated list of the props (name + type annotation).
    """
    m = re.search(
        rf"interface {re.escape(name)}Props[^{{]*\{{([^}}]+)\}}",
        src, re.DOTALL,
    )
    if not m:
        # Fall back to "extends HTMLAttributes" only
        if re.search(rf"interface {re.escape(name)}Props[^{{]*extends[^{{]*HTMLAttributes", src):
            return "className only (extends HTMLAttributes)"
        return ""
    body = m.group(1)
    pieces = []
    for line in body.splitlines():
        s = line.strip().rstrip(";,")
        if not s or s.startswith("//"):
            continue
        # Strip inline `// comment`
        s = re.sub(r"\s*//.*$", "", s)
        pieces.append(s)
    return ", ".join(pieces)[:200]


def regen(scaffold_name: str = "react-app") -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    scaffold_root = repo_root / "scaffolds" / scaffold_name
    ui_dir = scaffold_root / "src" / "components" / "ui"
    if not ui_dir.is_dir():
        # Inheriting scaffolds (auth-app, ai-app) re-export react-app's
        # UI components and add scaffold-specific contracts (useAuth,
        # useChat) in scaffold-specific fixtures (auth_flow.tsx,
        # chat_stream.tsx) — they don't have a self-contained
        # src/components/ui/ to scan, AND their fixture isn't named
        # drone_natural.tsx (each scaffold names its fixture after the
        # contract it locks). Emit a small inheritance-marker
        # scaffold.yaml that points at the actual fixture file.
        fixtures_dir = scaffold_root / "__fixtures__"
        # Scan for the scaffold-specific fixture (anything that's not
        # drone_natural.tsx or a *_patterns.tsx pattern fixture)
        scaffold_fixture = "<read __fixtures__/ for the locked contract>"
        if fixtures_dir.is_dir():
            tsxs = sorted(p.name for p in fixtures_dir.glob("*.tsx"))
            non_generic = [n for n in tsxs if n != "drone_natural.tsx" and "_patterns.tsx" not in n]
            if non_generic:
                scaffold_fixture = f"__fixtures__/{non_generic[0]}"
            elif tsxs:
                scaffold_fixture = f"__fixtures__/{tsxs[0]}"
        inherit_marker = scaffold_root / "scaffold.yaml"
        inherit_marker.write_text(
            f"# AUTO-GENERATED — {scaffold_name} inherits UI from react-app\n"
            f"# Regenerate with: python3 -m tsunami.scripts.regen_scaffold_yaml {scaffold_name}\n"
            f"\n"
            f"render_target: dom\n"
            f"frame_cadence: event\n"
            f"\n"
            f"inherits_from: react-app  # see scaffolds/react-app/scaffold.yaml for UI components\n"
            f"\n"
            f"# Scaffold-specific contract lives in {scaffold_fixture}\n"
            f"# (locks the API surface this scaffold adds on top of react-app's UI).\n"
            f"# Read that fixture FIRST for the locked contract.\n"
        )
        print(f"Wrote {inherit_marker} (inheritance marker — no src/components/ui/)")
        return inherit_marker

    lines = [
        f"# AUTO-GENERATED from {scaffold_name}/src/components/ui/*.tsx",
        f"# Regenerate with: python3 -m tsunami.scripts.regen_scaffold_yaml {scaffold_name}",
        "",
        "render_target: dom",
        "frame_cadence: event",
        "",
        "components:",
    ]
    for f in sorted(ui_dir.glob("*.tsx")):
        name = f.stem
        src = f.read_text()
        props = _extract_props(src, name)
        if props:
            lines.append(f"  {name}: {props}")
        else:
            lines.append(f"  {name}: (see source)")

    # Hooks (by scanning src/hooks/)
    hooks_dir = scaffold_root / "src" / "hooks"
    if hooks_dir.is_dir():
        lines.append("")
        lines.append("hooks:")
        for f in sorted(hooks_dir.glob("*.ts")):
            name = f.stem
            src = f.read_text()
            sig_m = re.search(rf"export function {re.escape(name)}[^{{]*", src)
            sig = sig_m.group(0).strip()[:180] if sig_m else ""
            lines.append(f"  {name}: {sig}")

    lines.extend([
        "",
        "imports:  # copy verbatim — use RELATIVE paths, not @/ alias (alias has a known resolution bug)",
        '  # UI components: import { Button, Card, CardContent, Input, Progress, Flex, Heading, Text, Badge, Dialog, Switch, Tooltip } from "./components/ui"',
        '  # Hooks: import { useInterval, useLocalStorage, useDebounce } from "./hooks"',
        '  # NEVER use @/components/... — TypeScript TS2614 resolution issue. Use ./components/... relative paths.',
        "",
        "usage_examples:  # literal JSX — copy the form, vary the values",
        '  Heading: <Heading level={1} size="3xl">Title</Heading>   # level is a NUMBER, not string',
        '  Button: <Button variant="primary" size="md" onClick={fn}>Click</Button>',
        '  Card: <Card className="p-6"><CardContent>...</CardContent></Card>',
        '  Flex: <Flex direction="col" gap={4} align="center">children</Flex>   # gap is a NUMBER',
        '  Input: <Input label="Name" value={v} onChange={e => setV(e.target.value)} />',
        '  Progress: <Progress value={75} variant="striped" />   # value is a NUMBER 0-100',
        '  Badge: <Badge className="ml-2">New</Badge>   # Badge takes only className + children',
        '  Text: <Text as="p" className="text-muted">body</Text>   # no size/muted props, use className',
        '  Dialog: <Dialog open={isOpen} onClose={close}>body</Dialog>',
        "",
        "rules:",
        "  - Only use props listed in components above — TypeScript will reject unknown props.",
        "  - Numeric prop types (`level`, `gap`, `value`, `size` when unioned with numbers) MUST be JSX numeric literals `{1}`, not strings `\"1\"`.",
        "  - For styling, use className with scaffold CSS classes (container, flex, card, etc.).",
        "  - <Input> takes only the declared props; do NOT pass `ref` (use `React.forwardRef` wrapper if needed).",
        "  - Don't overwrite main.tsx, vite.config.ts, or index.css.",
        "",
        "build: cd {project_path} && npm run build  # runs tsc + vite + vitest",
    ])

    out = scaffold_root / "scaffold.yaml"
    out.write_text("\n".join(lines) + "\n")
    return out


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "react-app"
    path = regen(name)
    print(f"Wrote {path}")
