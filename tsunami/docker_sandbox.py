"""Docker sandbox — safe code execution in a container.

When Docker is available, shell_exec commands run inside a container
instead of on bare metal. This prevents:
- Accidental system damage from buggy generated code
- npm/pip packages touching the host system
- Runaway processes consuming host resources

Fallback: if Docker is unavailable, runs on host (current behavior).

Container setup:
- Image: tsunami-sandbox (Python + Node + common tools)
- Workspace mounted read-write at /workspace
- GPU passthrough when nvidia-container-toolkit present
- Timeout enforcement via --stop-timeout
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

log = logging.getLogger("tsunami.docker_sandbox")

SANDBOX_IMAGE = "tsunami-sandbox"
DOCKERFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "exec.Dockerfile")


def is_docker_available() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_gpu_available() -> bool:
    """Check if nvidia-container-toolkit is installed."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_sandbox_image_built() -> bool:
    """Check if the sandbox Docker image exists."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", SANDBOX_IMAGE],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_sandbox_image(dockerfile_path: str = DOCKERFILE_PATH) -> bool:
    """Build the sandbox Docker image.

    Returns True if build succeeded, False otherwise.
    """
    if not os.path.exists(dockerfile_path):
        log.warning(f"Dockerfile not found at {dockerfile_path}")
        return False

    try:
        context_dir = os.path.dirname(dockerfile_path)
        result = subprocess.run(
            ["docker", "build", "-t", SANDBOX_IMAGE, "-f", dockerfile_path, context_dir],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            log.info(f"Built sandbox image: {SANDBOX_IMAGE}")
            return True
        else:
            log.warning(f"Failed to build sandbox: {result.stderr[:200]}")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning(f"Build failed: {e}")
        return False


def wrap_command_for_docker(
    command: str,
    workspace_dir: str,
    timeout: int = 120,
    gpu: bool = False,
) -> list[str]:
    """Wrap a shell command to run inside the Docker sandbox.

    Returns the full docker run command as a list of args.
    """
    abs_workspace = os.path.abspath(workspace_dir)

    args = [
        "docker", "run", "--rm",
        "--network", "none",  # no internet access inside sandbox
        "-v", f"{abs_workspace}:/workspace",
        "-w", "/workspace",
        "--stop-timeout", str(timeout),
        "--memory", "2g",
        "--cpus", "2",
    ]

    if gpu:
        args.extend(["--gpus", "all"])

    args.extend([SANDBOX_IMAGE, "bash", "-c", command])
    return args


def run_in_sandbox(
    command: str,
    workspace_dir: str,
    timeout: int = 120,
) -> tuple[str, int]:
    """Run a command inside the Docker sandbox.

    Returns (output, return_code).
    Falls back to host execution if Docker is unavailable.
    """
    if not is_docker_available():
        log.debug("Docker not available — running on host")
        return _run_on_host(command, workspace_dir, timeout)

    if not is_sandbox_image_built():
        log.info("Sandbox image not built — running on host")
        return _run_on_host(command, workspace_dir, timeout)

    gpu = is_gpu_available()
    docker_cmd = wrap_command_for_docker(command, workspace_dir, timeout, gpu)

    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True, text=True,
            timeout=timeout + 10,  # extra grace for container startup
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        return output.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s (sandbox)", 124
    except Exception as e:
        log.warning(f"Sandbox execution failed: {e} — falling back to host")
        return _run_on_host(command, workspace_dir, timeout)


def _run_on_host(command: str, workspace_dir: str, timeout: int) -> tuple[str, int]:
    """Fallback: run command directly on host."""
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True, text=True,
            cwd=workspace_dir if os.path.isdir(workspace_dir) else None,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        return output.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s", 124
    except Exception as e:
        return f"Execution error: {e}", 1


def health_check() -> dict:
    """Check sandbox health status."""
    return {
        "docker_available": is_docker_available(),
        "gpu_available": is_gpu_available(),
        "image_built": is_sandbox_image_built() if is_docker_available() else False,
        "sandbox_image": SANDBOX_IMAGE,
    }
