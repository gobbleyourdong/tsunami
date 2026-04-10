"""Job executor — runs Tsunami agents as compute jobs.

When a node accepts a JOB_OFFER, this module does the actual work.
Wraps the Tsunami agent loop with isolation and result capture.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("megalan.executor")


@dataclass
class JobResult:
    job_id: str
    success: bool
    output_dir: str | None = None
    result_hash: str = ""
    duration_s: float = 0
    iterations: int = 0
    error: str = ""


class JobExecutor:
    """Executes Tsunami agent jobs in isolation."""

    def __init__(self, workspace_base: Path | None = None):
        self._workspace = workspace_base or Path.home() / ".megalan" / "jobs"
        self._workspace.mkdir(parents=True, exist_ok=True)

    async def execute(self, job_id: str, job_type: str, payload: dict) -> JobResult:
        if job_type == "tsunami_agent":
            return await self._run_tsunami(job_id, payload)
        elif job_type == "inference":
            return await self._run_inference(job_id, payload)
        else:
            return JobResult(job_id=job_id, success=False,
                             error=f"Unknown job type: {job_type}")

    async def _run_tsunami(self, job_id: str, payload: dict) -> JobResult:
        """Run a Tsunami agent build job via subprocess."""
        prompt = payload.get("prompt", "")
        if not prompt:
            return JobResult(job_id=job_id, success=False, error="No prompt")

        job_dir = self._workspace / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        t0 = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", "-m", "tsunami",
                "--task", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path.cwd()),
                env={"TSUNAMI_WORKSPACE": str(job_dir / "workspace")},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=600,
            )

            duration = time.monotonic() - t0

            # Find build output
            output_dir = self._find_output(job_dir)
            result_hash = self._hash_directory(output_dir) if output_dir else ""

            return JobResult(
                job_id=job_id,
                success=proc.returncode == 0,
                output_dir=output_dir,
                result_hash=result_hash,
                duration_s=duration,
                error=stderr.decode()[:500] if proc.returncode != 0 else "",
            )

        except asyncio.TimeoutError:
            return JobResult(
                job_id=job_id, success=False,
                duration_s=time.monotonic() - t0,
                error="Job timed out (600s)",
            )
        except Exception as e:
            return JobResult(
                job_id=job_id, success=False,
                duration_s=time.monotonic() - t0,
                error=str(e),
            )

    async def _run_inference(self, job_id: str, payload: dict) -> JobResult:
        """Run a model inference job."""
        prompt = payload.get("prompt", "")
        endpoint = payload.get("endpoint", "http://localhost:8095")

        t0 = time.monotonic()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{endpoint}/v1/chat/completions",
                    json={
                        "model": payload.get("model", ""),
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2048,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                output = data["choices"][0]["message"]["content"]
                result_hash = hashlib.sha256(output.encode()).hexdigest()

                return JobResult(
                    job_id=job_id, success=True,
                    result_hash=result_hash,
                    duration_s=time.monotonic() - t0,
                )
        except Exception as e:
            return JobResult(
                job_id=job_id, success=False,
                duration_s=time.monotonic() - t0,
                error=str(e),
            )

    def _find_output(self, job_dir: Path) -> str | None:
        """Find the build output directory."""
        deliverables = job_dir / "workspace" / "deliverables"
        if not deliverables.exists():
            return None
        for d in sorted(deliverables.iterdir(),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                dist = d / "dist"
                return str(dist) if dist.exists() else str(d)
        return None

    def _hash_directory(self, dir_path: str) -> str:
        """Hash all files in a directory for result verification."""
        h = hashlib.sha256()
        p = Path(dir_path)
        if not p.exists():
            return ""
        for f in sorted(p.rglob("*")):
            if f.is_file():
                h.update(str(f.relative_to(p)).encode())
                h.update(f.read_bytes())
        return h.hexdigest()

    def cleanup(self, job_id: str):
        job_dir = self._workspace / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
