"""Tests for Chunk 10: Docker Sandbox.

Tests use mocks for Docker commands since Docker may not be available
in all test environments. Tests the logic, not the container itself.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock
import subprocess

from tsunami.docker_sandbox import (
    is_docker_available,
    is_gpu_available,
    is_sandbox_image_built,
    wrap_command_for_docker,
    run_in_sandbox,
    _run_on_host,
    health_check,
    SANDBOX_IMAGE,
)


class TestDockerDetection:
    """Docker/GPU availability detection."""

    @patch("subprocess.run")
    def test_docker_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert is_docker_available() is True

    @patch("subprocess.run")
    def test_docker_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert is_docker_available() is False

    @patch("subprocess.run")
    def test_docker_daemon_not_running(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert is_docker_available() is False

    @patch("subprocess.run")
    def test_gpu_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert is_gpu_available() is True

    @patch("subprocess.run")
    def test_gpu_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert is_gpu_available() is False

    @patch("subprocess.run")
    def test_image_built(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert is_sandbox_image_built() is True

    @patch("subprocess.run")
    def test_image_not_built(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert is_sandbox_image_built() is False


class TestWrapCommand:
    """Docker command wrapping."""

    def test_basic_wrap(self):
        cmd = wrap_command_for_docker("echo hello", "/tmp/workspace")
        assert "docker" in cmd
        assert "run" in cmd
        assert "--rm" in cmd
        assert SANDBOX_IMAGE in cmd
        assert "echo hello" in cmd

    def test_workspace_mounted(self):
        cmd = wrap_command_for_docker("ls", "/tmp/workspace")
        # Should have -v mount
        assert any("/workspace" in arg for arg in cmd)

    def test_network_disabled(self):
        cmd = wrap_command_for_docker("curl example.com", "/tmp/workspace")
        assert "--network" in cmd
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "none"

    def test_memory_limited(self):
        cmd = wrap_command_for_docker("node app.js", "/tmp/workspace")
        assert "--memory" in cmd

    def test_cpu_limited(self):
        cmd = wrap_command_for_docker("npm test", "/tmp/workspace")
        assert "--cpus" in cmd

    def test_gpu_passthrough(self):
        cmd = wrap_command_for_docker("python3 train.py", "/tmp/workspace", gpu=True)
        assert "--gpus" in cmd

    def test_no_gpu_by_default(self):
        cmd = wrap_command_for_docker("echo hi", "/tmp/workspace", gpu=False)
        assert "--gpus" not in cmd

    def test_timeout_in_command(self):
        cmd = wrap_command_for_docker("sleep 100", "/tmp/workspace", timeout=30)
        assert "--stop-timeout" in cmd
        idx = cmd.index("--stop-timeout")
        assert cmd[idx + 1] == "30"


class TestRunOnHost:
    """Fallback host execution."""

    def test_simple_command(self):
        output, code = _run_on_host("echo hello", "/tmp", 10)
        assert "hello" in output
        assert code == 0

    def test_failing_command(self):
        output, code = _run_on_host("false", "/tmp", 10)
        assert code != 0

    def test_timeout(self):
        output, code = _run_on_host("sleep 10", "/tmp", 1)
        assert code == 124
        assert "timed out" in output.lower()


class TestRunInSandbox:
    """Full sandbox execution with fallback."""

    @patch("tsunami.docker_sandbox.is_docker_available", return_value=False)
    def test_fallback_when_no_docker(self, _):
        output, code = run_in_sandbox("echo fallback", "/tmp", 10)
        assert "fallback" in output
        assert code == 0

    @patch("tsunami.docker_sandbox.is_docker_available", return_value=True)
    @patch("tsunami.docker_sandbox.is_sandbox_image_built", return_value=False)
    def test_fallback_when_no_image(self, _, __):
        output, code = run_in_sandbox("echo no_image", "/tmp", 10)
        assert "no_image" in output
        assert code == 0

    @patch("tsunami.docker_sandbox.is_docker_available", return_value=True)
    @patch("tsunami.docker_sandbox.is_sandbox_image_built", return_value=True)
    @patch("tsunami.docker_sandbox.is_gpu_available", return_value=False)
    @patch("subprocess.run")
    def test_runs_in_docker_when_available(self, mock_run, _, __, ___):
        mock_run.return_value = MagicMock(
            stdout="docker output", stderr="", returncode=0,
        )
        output, code = run_in_sandbox("echo test", "/tmp", 10)
        assert code == 0
        # Verify docker was called
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args


class TestHealthCheck:
    """Health check endpoint."""

    @patch("tsunami.docker_sandbox.is_docker_available", return_value=True)
    @patch("tsunami.docker_sandbox.is_sandbox_image_built", return_value=True)
    @patch("tsunami.docker_sandbox.is_gpu_available", return_value=False)
    def test_healthy(self, _, __, ___):
        h = health_check()
        assert h["docker_available"] is True
        assert h["image_built"] is True
        assert h["gpu_available"] is False
        assert h["sandbox_image"] == SANDBOX_IMAGE

    @patch("tsunami.docker_sandbox.is_docker_available", return_value=False)
    def test_no_docker(self, _):
        h = health_check()
        assert h["docker_available"] is False
        assert h["image_built"] is False


class TestDockerfile:
    """exec.Dockerfile exists and is valid."""

    def test_dockerfile_exists(self):
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "exec.Dockerfile")
        assert os.path.exists(dockerfile)

    def test_dockerfile_has_node(self):
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "exec.Dockerfile")
        content = open(dockerfile).read()
        assert "node" in content.lower()

    def test_dockerfile_has_python(self):
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "exec.Dockerfile")
        content = open(dockerfile).read()
        assert "python" in content.lower()

    def test_dockerfile_has_non_root_user(self):
        dockerfile = os.path.join(os.path.dirname(__file__), "..", "..", "exec.Dockerfile")
        content = open(dockerfile).read()
        assert "useradd" in content or "USER" in content
