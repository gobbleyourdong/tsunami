"""Sprite generation backend — ERNIE-Image-Turbo.

Backend ABC gives generate_asset() a single interface to plug into. The
concrete backend:

1. owns its endpoint + default sampler knobs
2. implements `generate(prompt, w, h, ...) -> PIL.Image`
3. implements `available()` for health checks

Z-Image was retired 2026-04-17 — ERNIE is the sole shipping backend.

TODO v1.2: BackendName is a single-entry Literal today; widen to `str`
with runtime validation against a backend registry when a 2nd backend
actually lands (OpenAI, SD3, etc.).
"""
from __future__ import annotations

import base64
import io
import random
import time
from abc import ABC, abstractmethod
from typing import Literal, Optional

import httpx
from PIL import Image

BackendName = Literal["ernie"]


class Backend(ABC):
    """Uniform text-to-image surface for sprite generation."""

    name: BackendName
    version: str
    endpoint: str

    default_steps: int
    default_guidance: float
    default_size: tuple[int, int] = (512, 512)

    @abstractmethod
    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        steps: Optional[int] = None,
        guidance: Optional[float] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> Image.Image:
        """Synthesize one image. Callers apply style_prefix + suffix
        before calling; the backend doesn't own prompt assembly."""

    @abstractmethod
    def available(self) -> bool:
        """Cheap health probe — `backend_fallback` consults this before
        dispatching. Should finish in under a second."""


# ── ERNIE-Image-Turbo via tsunami :8092 ──────────────────────────────

class ErnieBackend(Backend):
    """ERNIE-Image-Turbo backend against the tsunami `serve_ernie`
    server on :8092. Endpoint body shape is `GenRequest`:

        POST /v1/images/generate
        {
          prompt, negative_prompt?, width=1024, height=1024,
          num_inference_steps=8, guidance_scale=1.0,
          seed?, n=1, response_format="b64_json",
          use_pe=False, model_kind?
        }

    Spec constants (locked):
      steps = 8, CFG = 1.0, size = 1024×1024, use_pe = False.

    `use_pe=False` is load-bearing — the prompt enhancer LLM degrades
    text rendering and adds decorative artifacts (literal quotes,
    asterisks, glitch nudges). Never flip it on without a measured
    reason.
    """

    name: BackendName = "ernie"
    version = "ernie@turbo-8s"
    endpoint = "http://localhost:8092/v1/images/generate"
    default_steps = 8
    default_guidance = 1.0
    default_size = (1024, 1024)

    # Long tail for batch + model-swap cases; short health probe.
    _gen_timeout = 600
    _health_timeout = 2

    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        steps: Optional[int] = None,
        guidance: Optional[float] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
    ) -> Image.Image:
        actual_seed = seed if (seed is not None and seed >= 0) \
                      else random.randint(0, 2**31 - 1)
        body: dict = {
            "prompt": prompt,
            "width": width, "height": height,
            "num_inference_steps": steps if steps is not None else self.default_steps,
            "guidance_scale": guidance if guidance is not None else self.default_guidance,
            "seed": actual_seed,
            "n": 1,
            "response_format": "b64_json",
            "use_pe": False,
        }
        if negative_prompt:
            body["negative_prompt"] = negative_prompt

        t0 = time.time()
        with httpx.Client(timeout=self._gen_timeout) as client:
            resp = client.post(self.endpoint, json=body)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            raise RuntimeError(
                f"{self.version} returned {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        # The serve_ernie response mirrors OpenAI's image envelope:
        # { "data": [{"b64_json": "..."}], ... }.
        if "error" in data:
            raise RuntimeError(f"{self.version} error: {data['error']}")
        try:
            b64 = data["data"][0]["b64_json"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"{self.version} unexpected response shape: "
                f"{str(data)[:300]} ({e})"
            )
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        img.load()
        print(f"[sprite_backends] {self.version} generated in {elapsed:.2f}s "
              f"(seed={actual_seed}, {body['num_inference_steps']}steps)")
        return img

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=self._health_timeout) as client:
                # serve_ernie exposes /healthz; the response body
                # includes {"pipe_loaded": bool} so we require a
                # truthy pipe_loaded, not just 2xx (server is up but
                # mid-swap during a model load).
                resp = client.get(self.endpoint.replace(
                    "/v1/images/generate", "/healthz",
                ))
            if resp.status_code != 200:
                return False
            body = resp.json()
            return bool(body.get("pipe_loaded"))
        except Exception:
            return False


# ── Registry ─────────────────────────────────────────────────────────

_BACKENDS: dict[BackendName, Backend] = {}


def get_backend(name: BackendName) -> Backend:
    """Return a cached backend instance. Backends are stateless; caching
    avoids re-constructing the httpx-using shell on every generate_asset
    call."""
    if name not in _BACKENDS:
        if name == "ernie":
            _BACKENDS[name] = ErnieBackend()
        else:
            raise ValueError(f"unknown backend: {name!r}")
    return _BACKENDS[name]
