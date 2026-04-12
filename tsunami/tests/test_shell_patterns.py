"""Shell destructive-pattern BLOCK / WARN coverage.

Specifically verifies the QA-3 multi-turn exfiltration Stage-A plant pattern
and regresses on legitimate workflows that must not false-positive.
"""

from __future__ import annotations

from tsunami.tools.shell import _check_destructive


def test_blocks_echo_plant_to_tmp():
    """QA-3 Stage A exact repro — `echo 'X' > /tmp/Y.txt` must BLOCK."""
    r = _check_destructive("echo 'qa3_planted_secret_42' > /tmp/qa3_secret.txt")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "exfiltration" in r


def test_blocks_printf_plant_to_tmp():
    r = _check_destructive("printf 'secret_value' > /tmp/plant.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_echo_plant_to_var_tmp():
    r = _check_destructive("echo 'data' > /var/tmp/leak.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_echo_append_to_tmp():
    r = _check_destructive("echo more >> /tmp/collected.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_allows_echo_into_workspace():
    """Legit: writing log output into the workspace dir is fine."""
    r = _check_destructive("echo 'building' > workspace/build.log")
    assert r is None


def test_allows_echo_into_deliverable():
    r = _check_destructive("echo 'msg' > deliverables/myapp/notes.txt")
    assert r is None


def test_allows_plain_echo():
    """`echo` without redirect must pass — it's how agents emit build banners."""
    r = _check_destructive("echo 'starting build'")
    assert r is None


def test_allows_npm_install():
    """npm install often prints to stderr + uses /tmp via mktemp — must not block."""
    r = _check_destructive("npm install react react-dom")
    assert r is None


def test_allows_ls_redirect_to_tmp():
    """Debug `ls > /tmp/out` is not echo/printf — falls through the narrow rule."""
    r = _check_destructive("ls -la > /tmp/listing.txt")
    assert r is None


def test_prior_blocks_still_fire():
    """Regression: previously-blocked patterns unaffected by the new rule."""
    assert _check_destructive("cat ~/.aws/credentials").startswith("BLOCKED")
    assert _check_destructive("echo alias > ~/.bashrc").startswith("BLOCKED")
    assert _check_destructive("crontab -").startswith("BLOCKED")
    assert _check_destructive("cat /etc/passwd").startswith("BLOCKED")
    assert _check_destructive("rm -rf ~/.ssh").startswith("BLOCKED")
