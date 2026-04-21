"""Outbound-exfiltration gate — literal-secret + exfil-URL detection.

Scans content about to be written to disk for high-confidence exfil
signals: literal API keys, private-key PEM headers, concrete values
of sensitive environment variables at write time, and webhook-shaped
URLs pointing at known capture services.

Conservative by design: every false positive blocks a legitimate write,
so detectors key on format+length+structure, not on keyword mentions.
"Documentation that mentions ANTHROPIC_API_KEY" is fine; "a file
containing the literal 108-character Anthropic key prefix" is not.

History: this module stubbed at `return None` through 12+ claimed-fix
commits — Current's 2026-04-20 static audit surfaced that every
filesystem.py call site routed through a no-op. The stub docstring
admitted: "The real implementation was never committed." This replaces
the stub with a first real ruleset.

Signature contract (preserved): check_outbound_exfil(content, filename,
task_prompt) -> str | None. Return a non-empty reason string to block
the write, None to allow. Filesystem.py catches the return and
converts to a tool-level error.
"""

from __future__ import annotations

import os
import re
from typing import Optional


# Cap scan to the first ~50 KB of content. Large generated assets
# (images base64'd into HTML, bundled JS) dominate write volume; most
# exfiltration payloads would land near the top. This is a perf vs.
# coverage trade: perfect coverage would scan everything, but the gate
# runs on every file write, so bounded-latency beats theoretical
# completeness.
_MAX_SCAN_BYTES = 50_000


# ── Detectors ────────────────────────────────────────────────────────
#
# Each detector is (name, pattern). Pattern is a compiled regex that
# matches ONLY high-confidence literal values. A match returns a
# human-readable reason so filesystem.py's log line tells the operator
# which detector fired and what to investigate.
#
# Criteria for adding a detector here:
#   - Format is distinctive (prefix + length + alphabet)
#   - False-positive rate on normal code is near zero
#   - Block reason is actionable ("move this to env var", etc.)
#
# Detectors that require CONTEXT beyond the raw match (e.g. "this AWS
# key is paired with an AWS secret value in the same file") are split
# into sibling rules for composition below.

_DETECTORS: list[tuple[str, re.Pattern[str], str]] = [
    # Anthropic key — official format: sk-ant-apiNN- followed by 95+
    # urlsafe-b64 chars. Real keys are ~108 chars total.
    (
        "anthropic_api_key",
        re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_\-]{80,}"),
        "literal Anthropic API key. Move to ANTHROPIC_API_KEY env var "
        "and reference via os.environ[]. Never commit the value.",
    ),
    # OpenAI key — sk- prefix + 40+ chars. sk-proj-... also real.
    (
        "openai_api_key",
        re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{40,}"),
        "literal OpenAI API key. Move to OPENAI_API_KEY env var.",
    ),
    # AWS access key — AKIA + 16 uppercase/digits. Distinctive.
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "literal AWS access-key ID. Use IAM role / env credential file "
        "(~/.aws/credentials) — never commit.",
    ),
    # GitHub tokens — gh[pousr]_ prefix, 36+ chars urlsafe.
    (
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "literal GitHub token. Use GITHUB_TOKEN env var.",
    ),
    # Slack tokens — xox[abpsr]- prefix.
    (
        "slack_token",
        re.compile(r"\bxox[abpsr]-[0-9a-zA-Z\-]{10,}"),
        "literal Slack token. Move to SLACK_TOKEN env var.",
    ),
    # Private key PEM header — any variant (RSA/EC/DSA/OPENSSH/plain).
    (
        "pem_private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
        "PEM private key material. Keys belong in a secrets manager "
        "or an ignored .pem file — never in source or generated files.",
    ),
    # Stripe live key.
    (
        "stripe_live_key",
        re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b"),
        "literal Stripe live-mode key. Use STRIPE_SECRET_KEY env var; "
        "use sk_test_... for fixtures.",
    ),
    # Google API key — AIza + 35 chars.
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
        "literal Google API key. Use env var; rotate if already leaked.",
    ),
    # JWT-shaped tokens — header.payload.signature. Only flag when
    # the alphabet is base64url and the length suggests real token.
    (
        "jwt_token",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
        "JWT-shaped token. If this is a test fixture, use a truncated "
        "placeholder; if it's a real token, move to an env var.",
    ),
]


# Webhook-capture services — URLs pointing at these are strong exfil
# signals. Legitimate code rarely needs them; malicious prompt
# injection frequently constructs them.
_EXFIL_HOSTS = (
    "webhook.site",
    "requestbin.com", "requestbin.io",
    "pipedream.com/v1/",
    "ngrok.io", "ngrok-free.app",
    "burpcollaborator.net",
    "interact.sh",
    "oast.pro", "oast.live", "oast.site", "oast.me", "oast.fun", "oast.online",
    "canarytokens.com",
)
_EXFIL_HOST_RE = re.compile(
    r"https?://[^\s\"'<>]*?(?:" + "|".join(re.escape(h) for h in _EXFIL_HOSTS) + r")",
    re.IGNORECASE,
)


# Sensitive env vars whose literal VALUE (not name) leaking into a
# written file is a strong exfil signal. We resolve at write time — if
# os.environ["ANTHROPIC_API_KEY"] is "sk-ant-api99-abc..." and "abc"
# appears in the content, the drone is writing the key value out.
# Only match when the value is ≥ 12 chars (short values false-positive).
_SENSITIVE_ENV_VARS = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID", "GITHUB_TOKEN", "SLACK_TOKEN",
    "STRIPE_SECRET_KEY", "GOOGLE_API_KEY", "HF_TOKEN",
    "HUGGINGFACE_TOKEN", "DATABASE_URL", "DATABASE_PASSWORD",
    "SESSION_SECRET", "JWT_SECRET", "ENCRYPTION_KEY",
)
_MIN_ENV_VALUE_LEN = 12


def _scan_detectors(content: str) -> Optional[str]:
    """Run every detector; return reason on first match, None if clean."""
    for name, pattern, msg in _DETECTORS:
        if pattern.search(content):
            return f"[{name}] {msg}"
    return None


def _scan_env_value_leaks(content: str) -> Optional[str]:
    """Flag if a sensitive env var's current value appears literally in
    content. Requires the value to be ≥ _MIN_ENV_VALUE_LEN chars to
    avoid false-positive on e.g. DATABASE_URL="1".
    """
    for var in _SENSITIVE_ENV_VARS:
        val = os.environ.get(var, "")
        if len(val) >= _MIN_ENV_VALUE_LEN and val in content:
            return (
                f"[env_value_leak] the literal value of {var} appears "
                "in content about to be written. If the write is legit "
                "(e.g. writing a .env file), use a placeholder; if not, "
                "the drone is exfiltrating a secret into the deliverable."
            )
    return None


def _scan_exfil_urls(content: str) -> Optional[str]:
    m = _EXFIL_HOST_RE.search(content)
    if m:
        url = m.group(0)[:120]
        return (
            f"[exfil_url] content references a known webhook-capture "
            f"service: {url!r}. These services are used by prompt-"
            "injection attacks to exfiltrate data. Remove or replace "
            "with a legitimate endpoint."
        )
    return None


def check_outbound_exfil(
    content: str,
    filename: str,
    task_prompt: str = "",
) -> Optional[str]:
    """Scan content for exfil signals. Return block-reason or None.

    Args:
        content: text about to be written to disk
        filename: target path (used for context in log lines only)
        task_prompt: original user task (unused today; hook for
            future context-sensitive rules like "task says 'fetch X'
            but content writes X to a webhook")
    """
    if not content:
        return None

    # Bound scan to keep filesystem.py latency flat on large writes.
    sample = content if len(content) <= _MAX_SCAN_BYTES else content[:_MAX_SCAN_BYTES]

    for scanner in (_scan_detectors, _scan_env_value_leaks, _scan_exfil_urls):
        reason = scanner(sample)
        if reason:
            return reason
    return None


__all__ = ["check_outbound_exfil"]
