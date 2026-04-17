"""Sprite generation backends — Z-Image-Turbo (MVP) + ERNIE (Phase 6.2).

Backend ABC gives generate_asset() a single interface to plug into. Each
concrete backend:

1. owns its endpoint + default sampler knobs
2. implements `generate(prompt, w, h, ...) -> PIL.Image`
3. implements `available()` for backend_fallback health checks

TODO v1.2 (per G5 in sprites/START_HERE.md): BackendName is a Literal
today; when a 3rd backend lands (OpenAI, SD3, etc.), widen to `str` with
runtime validation against a backend registry.
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

BackendName = Literal["z_image", "ernie"]


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


# ── Z-Image-Turbo via tsunami :8090 ──────────────────────────────────

class ZImageBackend(Backend):
    """The tsunami server has Z-Image-Turbo weights resident; we share
    that load via its OpenAI-compatible /v1/images/generate route.

    Official Z-Image-Turbo recipe: 9 steps, guidance 0.0. Guidance > 0
    on turbo models smooths edges and destroys pixel detail — do not
    raise it without a measured reason."""

    name: BackendName = "z_image"
    version = "zimage@turbo-9s"
    endpoint = "http://localhost:8090/v1/images/generate"
    default_steps = 9
    default_guidance = 0.0
    default_size = (512, 512)

    # Long timeout: server may be under LLM inference load when a sprite
    # request arrives. Actual gen is ~3s but queue wait can be minutes.
    _gen_timeout = 600
    # Short health probe — don't block dispatch on a slow server.
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
            "steps": steps if steps is not None else self.default_steps,
            "guidance_scale": guidance if guidance is not None else self.default_guidance,
            "seed": actual_seed,
        }
        if negative_prompt:
            body["negative_prompt"] = negative_prompt

        t0 = time.time()
        with httpx.Client(timeout=self._gen_timeout) as client:
            resp = client.post(self.endpoint, json=body)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            raise RuntimeError(
                f"{self.version} returned {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"{self.version} error: {data['error']}")
        b64 = data["data"][0]["b64_json"]
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        # Force decode now so callers don't hit lazy IO later.
        img.load()
        print(f"[sprite_backends] {self.version} generated in {elapsed:.2f}s "
              f"(seed={actual_seed}, {body['steps']}steps)")
        return img

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=self._health_timeout) as client:
                # /health is the canonical liveness probe on tsunami's
                # server; reaching it means the process is up and the
                # route stack is wired. Actual model-readiness is
                # stamped into its body but we only need the 2xx.
                resp = client.get(self.endpoint.replace("/v1/images/generate", "/health"))
            return resp.status_code == 200
        except Exception:
            return False


# ── ERNIE-Image-Turbo (Phase 6.2) ────────────────────────────────────

class ErnieBackend(Backend):
    """ERNIE-Image-Turbo backend — landed in Phase 6.2 after
    generate_asset() proves out on z_image. Per project memory:
    ERNIE-Image-Turbo uses 8 steps, CFG 1.0, 1024×1024, and
    `use_pe=False` forever (pe degrades text rendering + adds
    decorative artifacts).

    Not wired for v1.1 MVP (see G2 in START_HERE.md)."""

    name: BackendName = "ernie"
    version = "ernie@turbo-8s"
    endpoint = "http://localhost:8092/v1/images/generate"
    default_steps = 8
    default_guidance = 1.0
    default_size = (1024, 1024)

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
        raise NotImplementedError(
            "ErnieBackend.generate: deferred to Phase 6.2 "
            "(see sprites/START_HERE.md G2). Use ZImageBackend for MVP."
        )

    def available(self) -> bool:
        try:
            with httpx.Client(timeout=self._health_timeout) as client:
                resp = client.get(self.endpoint.replace("/v1/images/generate", "/health"))
            return resp.status_code == 200
        except Exception:
            return False


# ── Registry ─────────────────────────────────────────────────────────

_BACKENDS: dict[BackendName, Backend] = {}


def get_backend(name: BackendName) -> Backend:
    """Return a cached backend instance. Backends are stateless in the
    v1.1 MVP; caching avoids re-constructing the httpx-using shell
    on every generate_asset call."""
    if name not in _BACKENDS:
        if name == "z_image":
            _BACKENDS[name] = ZImageBackend()
        elif name == "ernie":
            _BACKENDS[name] = ErnieBackend()
        else:
            raise ValueError(f"unknown backend: {name!r}")
    return _BACKENDS[name]
