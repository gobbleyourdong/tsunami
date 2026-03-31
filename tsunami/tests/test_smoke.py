"""Smoke test — validates the full one-click experience.

Simulates what a fresh user sees after install:
1. Model servers respond
2. Wave (9B) can reason and call tools
3. Eddies (2B) can execute tasks in parallel
4. SD-Turbo can generate an image
5. Agent can scaffold a project, generate a hero, and serve it

Skip with: pytest -k "not smoke"
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

import httpx
import pytest

def _server_up(port: int) -> bool:
    try:
        return httpx.get(f"http://localhost:{port}/health", timeout=2).status_code == 200
    except Exception:
        return False

WAVE_UP = _server_up(8090)
EDDY_UP = _server_up(8092)

skip_no_wave = pytest.mark.skipif(not WAVE_UP, reason="9B wave not running on :8090")
skip_no_eddy = pytest.mark.skipif(not EDDY_UP, reason="2B eddy not running on :8092")


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSmokeModels:
    """Step 1: model servers respond."""

    @skip_no_wave
    def test_wave_health(self):
        r = httpx.get("http://localhost:8090/health", timeout=5)
        assert r.status_code == 200

    @skip_no_eddy
    def test_eddy_health(self):
        r = httpx.get("http://localhost:8092/health", timeout=5)
        assert r.status_code == 200


@skip_no_wave
class TestSmokeWave:
    """Step 2: wave can reason and call tools."""

    def test_wave_answers_question(self):
        r = httpx.post(
            "http://localhost:8090/v1/chat/completions",
            json={
                "model": "qwen",
                "messages": [{"role": "user", "content": "What is 7 * 13? Reply with just the number, nothing else."}],
                "max_tokens": 32,
            },
            headers={"Authorization": "Bearer not-needed"},
            timeout=60,
        )
        assert r.status_code == 200
        content = r.json()["choices"][0]["message"]["content"]
        assert "91" in content or "ninety" in content.lower()

    def test_wave_calls_tools(self):
        r = httpx.post(
            "http://localhost:8090/v1/chat/completions",
            json={
                "model": "qwen",
                "messages": [{"role": "user", "content": "Read the file config.yaml"}],
                "tools": [{"type": "function", "function": {
                    "name": "file_read",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
                }}],
                "tool_choice": "auto",
                "max_tokens": 128,
            },
            headers={"Authorization": "Bearer not-needed"},
            timeout=60,
        )
        assert r.status_code == 200
        msg = r.json()["choices"][0]["message"]
        assert msg.get("tool_calls"), "Wave should call file_read tool"


@skip_no_eddy
class TestSmokeEddy:
    """Step 3: eddies can execute tasks in parallel."""

    def test_single_eddy(self):
        from tsunami.eddy import run_bee
        r = run(run_bee(
            "What is 2+2?",
            workdir="/home/jb/ComfyUI/CelebV-HQ/ark",
        ))
        assert r.success
        assert "4" in r.output

    def test_parallel_eddies(self):
        from tsunami.eddy import run_swarm
        results = run(run_swarm(
            ["What is 1+1?", "What is 2+2?", "What is 3+3?", "What is 4+4?"],
            workdir="/home/jb/ComfyUI/CelebV-HQ/ark",
            max_concurrent=4,
        ))
        ok = sum(1 for r in results if r.success)
        assert ok >= 3, f"Only {ok}/4 eddies succeeded"


class TestSmokeImageGen:
    """Step 4: SD-Turbo can generate an image."""

    def test_sd_turbo_generates(self):
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError:
            pytest.skip("diffusers/torch not installed")

        if not torch.cuda.is_available():
            pytest.skip("No CUDA GPU available")

        tmpdir = tempfile.mkdtemp()
        out_path = os.path.join(tmpdir, "smoke_test.png")

        pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sd-turbo",
            torch_dtype=torch.float16,
            variant="fp16",
        )
        pipe.to("cuda")

        image = pipe(
            "a simple blue wave on dark background",
            num_inference_steps=1,
            guidance_scale=0.0,
            width=512,
            height=512,
        ).images[0]
        image.save(out_path)

        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 10000, "Image too small — generation likely failed"

        # Cleanup
        os.unlink(out_path)
        del pipe
        torch.cuda.empty_cache()


@skip_no_wave
class TestSmokeEndToEnd:
    """Step 5: full agent loop — prompt to result."""

    def test_agent_completes_task(self):
        from tsunami.config import TsunamiConfig
        from tsunami.agent import Agent

        tmpdir = tempfile.mkdtemp()
        config = TsunamiConfig(
            model_backend="api",
            model_name="Qwen3.5-9B",
            model_endpoint="http://localhost:8090",
            temperature=0.7,
            max_tokens=2048,
            workspace_dir=tmpdir,
            max_iterations=10,
        )
        agent = Agent(config)

        result = run(agent.run(
            "Create a file called index.html with a basic HTML page that says 'tsunami works'. "
            "Then confirm the file exists."
        ))

        assert agent.state.task_complete
        # Verify the file was actually created
        found = False
        for root, dirs, files in os.walk(tmpdir):
            if "index.html" in files:
                content = open(os.path.join(root, "index.html")).read()
                if "tsunami" in content.lower():
                    found = True
        assert found, "index.html not created with expected content"
