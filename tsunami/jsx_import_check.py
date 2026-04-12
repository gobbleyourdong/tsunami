"""QA-1 Playtest Fire 118: shipped app that blank-pages at runtime.

`src/App.tsx` imported `{ Card, Input, Button, Alert }` from
`./components/ui` — but JSX body used `<Badge key={tip}>`. Badge wasn't
imported. At runtime Badge is undefined → React throws → entire app
fails before mount. The deliverable's package.json had plain `vite
build` (no `tsc --noEmit` prefix — typecheck skipped) so the
undefined-component slipped through to dist.

Pure-function static analysis: parse App.tsx, find all JSX component
tags (PascalCase identifiers in `<Foo>` / `<Foo.Bar>` / `<Foo />` form),
then find all imported names + locally-defined identifiers. Any JSX
component that isn't in either set is a smoking gun.

This catches the specific "undefined React component" class without
needing a full TS parser — regex on the import / JSX surface.
"""

from __future__ import annotations

import re

# React / HTML intrinsics that are valid JSX tags without an import.
_REACT_INTRINSICS = frozenset(
    {
        "Fragment",
        "StrictMode",
        "Suspense",
        "Profiler",
    }
)


def _find_jsx_components(content: str) -> set[str]:
    """Return the set of PascalCase identifiers used as JSX tags.

    Distinguishes JSX tags from TypeScript generic type arguments:
    `useState<Direction>(x)` is a generic, not a JSX `<Direction>`. The
    preceding char of a real JSX `<` is typically `(`, `,`, `{`, `>`,
    `=`, whitespace, or start-of-line — never an identifier char.
    """
    out: set[str] = set()
    # Look-behind: preceding char must not be [A-Za-z0-9_] (which would
    # indicate `ident<Type>` — a generic). Use a negative-lookbehind for
    # identifier chars.
    for m in re.finditer(
        r'(?<![A-Za-z0-9_])<([A-Z][A-Za-z0-9_]*)(?:\.[A-Za-z0-9_]+)?\b',
        content,
    ):
        out.add(m.group(1))
    return out


def _find_imported_names(content: str) -> set[str]:
    """Return the set of identifiers brought into scope by `import` stmts.

    Handles the four common forms:
      import X from "mod"                → {X}
      import { X, Y as Z } from "mod"    → {X, Z}
      import * as X from "mod"           → {X}
      import X, { Y, Z } from "mod"      → {X, Y, Z}
    """
    out: set[str] = set()
    # Default + named:  import X, { Y, Z } from "mod"
    for m in re.finditer(
        r'import\s+([A-Za-z_$][\w$]*)\s*(?:,\s*\{([^}]*)\})?\s*from\s+["\'][^"\']+["\']',
        content,
    ):
        out.add(m.group(1))
        if m.group(2):
            for piece in m.group(2).split(","):
                piece = piece.strip()
                if not piece:
                    continue
                # `X as Y` → Y is the binding.
                if " as " in piece:
                    _, _, alias = piece.partition(" as ")
                    out.add(alias.strip())
                else:
                    out.add(piece)
    # Named only:  import { X, Y as Z } from "mod"
    for m in re.finditer(
        r'import\s+\{([^}]+)\}\s+from\s+["\'][^"\']+["\']',
        content,
    ):
        for piece in m.group(1).split(","):
            piece = piece.strip()
            if not piece:
                continue
            if " as " in piece:
                _, _, alias = piece.partition(" as ")
                out.add(alias.strip())
            else:
                out.add(piece)
    # Namespace:  import * as X from "mod"
    for m in re.finditer(
        r'import\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from',
        content,
    ):
        out.add(m.group(1))
    return out


def _find_local_identifiers(content: str) -> set[str]:
    """Return PascalCase names defined locally in the file (function
    components, const assignments, class components, type aliases)."""
    out: set[str] = set()
    # function Foo(...) / function Foo<T>(...)
    for m in re.finditer(
        r'\bfunction\s+([A-Z][A-Za-z0-9_]*)\s*[<(]',
        content,
    ):
        out.add(m.group(1))
    # const Foo = ... / let Foo = ... / var Foo = ...
    for m in re.finditer(
        r'\b(?:const|let|var)\s+([A-Z][A-Za-z0-9_]*)\s*[:=]',
        content,
    ):
        out.add(m.group(1))
    # class Foo extends ... / class Foo<T> ...
    for m in re.finditer(
        r'\bclass\s+([A-Z][A-Za-z0-9_]*)\b',
        content,
    ):
        out.add(m.group(1))
    # export default function Foo(...) / export default class Foo ...
    # (covered by the function / class patterns above)
    return out


def find_undefined_jsx_components(content: str) -> list[str]:
    """Return the sorted list of JSX component names used in `content`
    that are neither imported nor locally defined nor React intrinsics.

    Empty list means every JSX tag is resolvable — no runtime surprises.
    """
    used = _find_jsx_components(content)
    if not used:
        return []
    imported = _find_imported_names(content)
    local = _find_local_identifiers(content)
    known = imported | local | _REACT_INTRINSICS
    missing = sorted(used - known)
    return missing
