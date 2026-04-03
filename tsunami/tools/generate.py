"""Generate tool — the artist.

Create images, audio, and other media. Uses whatever
generation backend is available: local (ComfyUI, SD),
API (OpenAI DALL-E, Stability), or stub.

The tool that makes the agent a creator, not just a processor.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult
from .filesystem import _resolve_path

log = logging.getLogger("tsunami.generate")


class GenerateImage(BaseTool):
    name = "generate_image"
    description = (
        "Generate an image from a text description. The artist: bring visual ideas into existence. "
        "Saves the image to the specified path."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Text description of the image to generate"},
                "save_path": {"type": "string", "description": "Path to save the generated image"},
                "width": {"type": "integer", "description": "Image width in pixels", "default": 1024},
                "height": {"type": "integer", "description": "Image height in pixels", "default": 1024},
                "style": {
                    "type": "string",
                    "description": "Style hint (e.g. 'photo', 'illustration', 'diagram')",
                    "default": "photo",
                },
            },
            "required": ["prompt", "save_path"],
        }

    async def execute(self, prompt: str, save_path: str, width: int = 1024,
                      height: int = 1024, style: str = "photo", **kw) -> ToolResult:
        p = _resolve_path(save_path, self.config.workspace_dir)
        p.parent.mkdir(parents=True, exist_ok=True)

        # SD-Turbo in-process first, placeholder fallback
        for backend in [self._try_sd_turbo_local, self._try_placeholder]:
            result = await backend(prompt, p, width, height, style)
            if not result.is_error:
                return result

        return ToolResult("No image generation backend available", is_error=True)

    async def _try_diffusion_server(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """Try the SD-Turbo server on :8091."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                try:
                    resp = await client.get("http://localhost:8091/health")
                    if resp.status_code != 200:
                        return ToolResult("Diffusion server not ready", is_error=True)
                except Exception:
                    return ToolResult("Diffusion server not running on :8091", is_error=True)

                resp = await client.post("http://localhost:8091/generate", json={
                    "prompt": prompt,
                    "width": min(w, 512),
                    "height": min(h, 512),
                    "steps": 1,
                })

                if resp.status_code == 200:
                    if resp.headers.get("content-type", "").startswith("image"):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(resp.content)
                    gen_time = resp.headers.get("X-Generation-Time", "?")
                    return ToolResult(f"Image generated and saved to {path} ({gen_time}s)")
                else:
                    error = resp.json().get("error", "unknown error")
                    return ToolResult(f"Diffusion error: {error}", is_error=True)
        except Exception as e:
            return ToolResult(f"Diffusion server error: {e}", is_error=True)

    async def _try_sd_turbo_local(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """Run SD-Turbo in-process. Auto-downloads the model on first use (~2GB)."""
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError:
            return ToolResult("diffusers not installed (pip install diffusers torch)", is_error=True)

        try:
            import torch

            # Lazy-load the pipeline (cached after first call)
            if not hasattr(self, '_sd_pipe'):
                dtype = torch.float16 if torch.cuda.is_available() else torch.float32
                device = "cuda" if torch.cuda.is_available() else "cpu"
                log.info(f"Loading SD-Turbo on {device} (first time downloads ~2GB)...")
                self._sd_pipe = AutoPipelineForText2Image.from_pretrained(
                    "stabilityai/sd-turbo",
                    torch_dtype=dtype,
                    variant="fp16" if dtype == torch.float16 else None,
                )
                self._sd_pipe.to(device)
                log.info("SD-Turbo loaded")

            import time
            t0 = time.time()
            image = self._sd_pipe(
                prompt=prompt,
                num_inference_steps=1,
                guidance_scale=0.0,
                width=min(w, 512),
                height=min(h, 512),
            ).images[0]
            elapsed = time.time() - t0

            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(path))
            return ToolResult(f"Image generated and saved to {path} (SD-Turbo, {elapsed:.1f}s)")

        except Exception as e:
            return ToolResult(f"SD-Turbo error: {e}", is_error=True)

    async def _try_comfyui(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """Try local ComfyUI instance."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("http://localhost:8188/system_stats")
                if resp.status_code != 200:
                    return ToolResult("ComfyUI not running", is_error=True)
        except Exception:
            return ToolResult("ComfyUI not reachable", is_error=True)

        # ComfyUI is running — queue a generation workflow
        # This is a simplified version; real implementation would use the full API
        return ToolResult(
            f"ComfyUI detected at localhost:8188. "
            f"Use shell_exec to queue a workflow for: '{prompt}' ({w}x{h})",
            is_error=True,  # Mark as error so we fall through to try other backends
        )

    async def _try_openai_api(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """Try OpenAI DALL-E API."""
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return ToolResult("No OPENAI_API_KEY set", is_error=True)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "n": 1,
                        "size": f"{w}x{h}" if f"{w}x{h}" in ("1024x1024", "1792x1024", "1024x1792") else "1024x1024",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                image_url = data["data"][0]["url"]

                # Download the image
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                path.write_bytes(img_resp.content)

                return ToolResult(f"Image generated and saved to {path} ({len(img_resp.content)} bytes)")
        except Exception as e:
            return ToolResult(f"DALL-E API error: {e}", is_error=True)

    async def _try_placeholder(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """Generate a placeholder SVG when no real backend is available."""
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect width="100%" height="100%" fill="#1a1a2e"/>
  <text x="50%" y="40%" text-anchor="middle" fill="#e0e0e0" font-family="monospace" font-size="20">
    [Image Placeholder]
  </text>
  <text x="50%" y="55%" text-anchor="middle" fill="#888" font-family="monospace" font-size="14">
    {prompt[:80]}
  </text>
  <text x="50%" y="70%" text-anchor="middle" fill="#555" font-family="monospace" font-size="12">
    {w}x{h} | {style}
  </text>
  <text x="50%" y="85%" text-anchor="middle" fill="#333" font-family="monospace" font-size="10">
    Connect a generation backend to produce real images
  </text>
</svg>"""
        # Save as SVG
        svg_path = path.with_suffix(".svg") if path.suffix not in (".svg",) else path
        svg_path.write_text(svg)
        return ToolResult(
            f"Placeholder SVG saved to {svg_path}. "
            f"No image generation backend available. Set OPENAI_API_KEY for DALL-E, "
            f"or start ComfyUI on port 8188, or install a local SD model."
        )
