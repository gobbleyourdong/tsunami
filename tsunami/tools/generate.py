"""Generate tool — the artist.

Create images, audio, and other media. Uses whatever
generation backend is available: local (ComfyUI, SD),
API (OpenAI DALL-E, Stability), or stub.

The tool that makes the agent a creator, not just a processor.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult


def _extract_alpha(path: Path, mode: str) -> None:
    """Convert the RGB image at `path` into an RGBA PNG with the alpha
    channel derived from the render-background signal.

      mode="alpha" — feathered 8-bit alpha from luminance. Black → 0,
                     bright → 255. Good for glows, particle sprites,
                     soft lighting effects.
      mode="icon"  — hard-edged color-key against magenta (#FF00FF).
                     Pixels close to magenta become transparent; everything
                     else stays fully opaque. A thin distance-ramp at the
                     threshold edge feathers the cutout ~2px to hide
                     color-fringe artifacts from the generator.

    Overwrites the file in place.
    """
    try:
        import numpy as _np
        from PIL import Image as _Image
    except ImportError as e:
        raise RuntimeError(f"alpha extraction requires pillow + numpy ({e})")

    img = _Image.open(path).convert("RGB")
    arr = _np.asarray(img, dtype=_np.float32)  # H × W × 3
    h, w, _ = arr.shape

    if mode == "alpha":
        # Rec.709 perceptual luminance — matches how human vision weights
        # channels (green dominates, red moderate, blue minor). Using this
        # instead of a flat (R+G+B)/3 gives cleaner feathering on colored
        # glows where the generator leaned one channel.
        lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
        # Stretch: take the darkest 5% as pure-transparent, brightest 5% as
        # pure-opaque. Gives a full-range alpha ramp even when the image
        # didn't quite hit solid black.
        lo = _np.percentile(lum, 5)
        hi = _np.percentile(lum, 95)
        if hi - lo < 1:
            alpha = _np.clip(lum, 0, 255).astype(_np.uint8)
        else:
            alpha = _np.clip((lum - lo) * 255.0 / (hi - lo), 0, 255).astype(_np.uint8)
        rgba = _np.dstack([arr.astype(_np.uint8), alpha])

    elif mode == "icon":
        # Dynamic corner-color key. Sample the four corners (plus a small
        # patch around each to denoise), pick the dominant color as the
        # background target, then color-key against it. This is generator-
        # agnostic — works whether SD produced magenta, white, gray, or
        # anything else. Color-based (not spatial) so it still catches
        # holes in the middle of icons (letter 'O', gear teeth, donut).
        #
        # Fallback to pure magenta if Z-Image-Turbo actually honors the
        # prompt — the magenta target is an even safer key than an arbitrary
        # corner color, since it's guaranteed not to match the subject.
        rgb_int = arr.astype(_np.uint8)
        # 8×8 corner patches → average → candidate background colors
        patch = 8
        corner_samples = [
            arr[:patch, :patch].reshape(-1, 3).mean(axis=0),
            arr[:patch, -patch:].reshape(-1, 3).mean(axis=0),
            arr[-patch:, :patch].reshape(-1, 3).mean(axis=0),
            arr[-patch:, -patch:].reshape(-1, 3).mean(axis=0),
        ]
        # Use median of corners so one "subject touches corner" outlier
        # doesn't poison the target color.
        target = _np.median(_np.stack(corner_samples), axis=0).astype(_np.float32)

        # If the corners are close to magenta (Z-Image-Turbo complied),
        # use the pure magenta target — it's cleaner.
        pure_magenta = _np.array([255, 0, 255], dtype=_np.float32)
        if _np.linalg.norm(target - pure_magenta) < 80:
            target = pure_magenta

        # Binary key on magenta-family shape rather than distance-to-target.
        # A pixel is "magenta-family" if BOTH R and B are high AND G is
        # clearly lower. Catches the fringe band in one shot — no soft
        # ramp leaving partial-alpha purple residue, no erosion chewing
        # real pixel-art edges. Legit subject colors (blue/cyan/white/black)
        # all fail the test: white has R=G=B, blue has R~0, cyan has R~0,
        # black has all low. Only true magenta-family pixels get zeroed.
        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]
        avg_rb = (r + b) / 2.0
        is_magenta_family = (
            (avg_rb > 120)            # not near-black
            & (avg_rb > g + 40)       # red+blue clearly higher than green
            & (_np.abs(r - b) < 120)  # roughly balanced R and B (rules out pure blue/red)
        )
        alpha = _np.where(is_magenta_family, 0, 255).astype(_np.uint8)

        # Premultiply fringe: kill RGB of transparent pixels so there's no
        # lingering color leak through any semi-transparent compositor.
        rgb = rgb_int.copy()
        rgb[alpha == 0] = 0
        rgba = _np.dstack([rgb, alpha])
    else:
        return

    _Image.fromarray(rgba, mode="RGBA").save(path, format="PNG")


def _public_url_hint(path: Path) -> str:
    """If `path` is inside a Vite/CRA-style `public/` dir, return the URL the
    dev server will serve it at (e.g. `<project>/public/assets/x.png` →
    `/assets/x.png`). Returns empty string otherwise.
    """
    parts = path.resolve().parts
    if "public" in parts:
        i = parts.index("public")
        return "/" + "/".join(parts[i + 1:])
    return ""

log = logging.getLogger("tsunami.generate")


class GenerateImage(BaseTool):
    name = "generate_image"
    description = (
        "Generate an image from a text description. The artist: bring visual ideas into existence. "
        "If a project exists, the image is auto-routed to <project>/public/assets/<filename> "
        "so you can reference it in JSX as <img src=\"/assets/<filename>\" />. "
        "Call project_init BEFORE generate_image when building a UI — otherwise images land "
        "in the workspace root and won't be served by the dev server."
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
                "mode": {
                    "type": "string",
                    "description": (
                        "Output mode. 'opaque' (default) = normal RGB. "
                        "'alpha' = render on black, extract 8-bit alpha from luminance "
                        "(for glows, sparks, soft cutouts, particle sprites). "
                        "'icon' = render on magenta, color-key out the background "
                        "(for hard-edged logos/icons with clean transparency)."
                    ),
                    "enum": ["opaque", "alpha", "icon"],
                    "default": "opaque",
                },
            },
            "required": ["prompt", "save_path"],
        }

    async def execute(self, prompt: str, save_path: str = "", width: int = 1024,
                      height: int = 1024, style: str = "photo",
                      mode: str = "opaque", **kw) -> ToolResult:
        # Training corpus uses `path` — accept either name so champion-trained
        # models don't silently fail on parameter-name mismatch.
        if not save_path and kw.get("path"):
            save_path = kw["path"]
        # Auto-generate save_path if model forgot it (common with 2B)
        if not save_path:
            import time as _time
            save_path = f"public/images/generated_{int(_time.time())}.png"
            log.info(f"generate_image called without save_path — defaulting to {save_path}")

        # Route saves into the active project's public/ when possible.
        # Without this, the model writes "/tmp/foo.png" (or any out-of-project
        # path) and the Vite dev server 404s on the <img src="..."> reference
        # because the file isn't under the serve root. Saving into public/
        # means the model can reference it as "/assets/foo.png" and it Just
        # Works after a build. (2026-04-13: image-gallery fix.)
        from .filesystem import _active_project
        routed = False
        if _active_project:
            import os.path as _osp
            filename = _osp.basename(save_path) or f"generated_{int(__import__('time').time())}.png"
            # Anything the model sent that ISN'T already rooted at the project
            # gets redirected to <project>/public/assets/. Covers /tmp/foo.png,
            # bare "foo.png", "images/foo.png", etc.
            # _active_project can arrive as "workspace/deliverables/foo" or
            # "deliverables/foo" depending on who set it. workspace_dir IS
            # the workspace root, so strip any leading "workspace/" to avoid
            # double-nesting (e.g. /tmp/ws/workspace/deliverables/foo).
            proj_rel = _active_project.lstrip("/")
            if proj_rel.startswith("workspace/"):
                proj_rel = proj_rel[len("workspace/"):]
            project_root = Path(self.config.workspace_dir) / proj_rel
            project_root_resolved = project_root.resolve()
            # Compute where the save would actually land using the SAME
            # resolution logic the non-routed branch uses below — else the
            # "is inside project?" check fails for save_paths like "/tmp/x.png"
            # (which land in workspace/tmp/x.png, outside the project, but my
            # previous check joined them to project_root and wrongly concluded
            # "inside").
            actual_clean = save_path.lstrip("/")
            for _pfx in ("workspace/", "app/workspace/"):
                if actual_clean.startswith(_pfx):
                    actual_clean = actual_clean[len(_pfx):]
                    break
            actual_save = (Path(self.config.workspace_dir) / actual_clean).resolve()
            try:
                inside_project = (
                    actual_save == project_root_resolved
                    or str(actual_save).startswith(str(project_root_resolved) + os.sep)
                )
            except Exception:
                inside_project = False
            if not inside_project:
                p = project_root / "public" / "assets" / filename
                p = p.resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                log.info(
                    f"generate_image: routed {save_path!r} → {p} "
                    f"(active project: {_active_project})"
                )
                routed = True

        if not routed:
            # Resolve path — always within workspace, strip leading /workspace
            clean = save_path.lstrip("/")
            # Strip "workspace/" prefix if the model sends absolute-looking paths
            for prefix in ["workspace/", "app/workspace/"]:
                if clean.startswith(prefix):
                    clean = clean[len(prefix):]
                    break
            p = (Path(self.config.workspace_dir) / clean).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)

        # Prompt modifiers for alpha/icon modes. These bias the generator
        # toward producing the specific background we'll color-key out post-hoc.
        mode = (mode or "opaque").lower()
        if mode == "alpha":
            prompt = f"{prompt}, on solid pure black background, centered subject"
        elif mode == "icon":
            # Heavy prompt repetition + emphatic tokens so SD-Turbo's
            # 1-step sampler actually produces magenta background.
            # Without this, it defaults to white/gray and the color-key
            # finds nothing to remove.
            prompt = (
                f"(({prompt})), centered, isolated, "
                f"on flat solid bright magenta color background, "
                f"pure magenta (hot pink) backdrop everywhere around the subject, "
                f"magenta wallpaper fill, no other background colors, "
                f"vibrant #FF00FF background, hard clean edges"
            )

        # Z-Image-Turbo on the tsunami server (/v1/images/generate on :8090)
        # is the canonical backend. Placeholder is the last-ditch fallback for
        # when the server is up but the image model wasn't loaded at startup.
        # SD-Turbo in-process was removed — Z-Image follows prompts better and
        # is the prod model.
        for backend in [self._try_zimage_server, self._try_placeholder]:
            result = await backend(prompt, p, width, height, style)
            if not result.is_error:
                # Post-process: extract alpha for alpha/icon modes so callers
                # get a PNG with real transparency instead of a background-
                # baked-in RGB image.
                if mode in ("alpha", "icon") and p.exists():
                    try:
                        _extract_alpha(p, mode)
                        result = ToolResult(result.content + f"\nExtracted alpha (mode={mode})")
                    except Exception as e:
                        log.warning(f"Alpha extraction failed: {e}")
                return result

        return ToolResult("No image generation backend available", is_error=True)

    async def _try_zimage_server(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """Call Z-Image-Turbo on the tsunami server (:8090/v1/images/generate).

        Z-Image-Turbo (Tongyi-MAI/Z-Image-Turbo) is the prod image model.
        Expects the tsunami server was started with --image-model set to
        Tongyi-MAI/Z-Image-Turbo (the default). If the server is up but
        --image-model was "none", returns is_error so the placeholder
        fallback can run.
        """
        import base64
        try:
            endpoint = getattr(self.config, "model_endpoint", "http://localhost:8090")
            if not endpoint.startswith("http"):
                endpoint = f"http://{endpoint}"
            import httpx
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{endpoint}/v1/images/generate",
                    json={
                        "prompt": prompt,
                        "width": w,
                        "height": h,
                        "steps": 4,  # Z-Image-Turbo: 4 steps is the sweet spot
                        "guidance_scale": 1.0,
                    },
                )
                if resp.status_code != 200:
                    return ToolResult(
                        f"Z-Image server returned {resp.status_code}: {resp.text[:200]}",
                        is_error=True,
                    )
                data = resp.json()
                if "error" in data:
                    return ToolResult(
                        f"Z-Image server error: {data['error']}",
                        is_error=True,
                    )
                if not data.get("data") or not data["data"][0].get("b64_json"):
                    return ToolResult("Z-Image server returned no image", is_error=True)
                b64 = data["data"][0]["b64_json"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(b64))
                url_hint = _public_url_hint(path)
                return ToolResult(
                    f"Image generated and saved to {path} (Z-Image-Turbo {w}x{h}, 4 steps)"
                    + (f"\nReference in JSX as <img src=\"{url_hint}\" />" if url_hint else "")
                )
        except Exception as e:
            return ToolResult(f"Z-Image call failed: {e}", is_error=True)

    async def _try_diffusion_server(self, prompt: str, path: Path, w: int, h: int, style: str) -> ToolResult:
        """(Legacy) Try the SD-Turbo server on :8091."""
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
                # Detect device safely — CUDA only if it actually works
                device = "cpu"
                dtype = torch.float32
                if torch.cuda.is_available():
                    try:
                        torch.zeros(1, device="cuda")
                        device = "cuda"
                        dtype = torch.float16
                    except Exception:
                        pass  # CUDA reports available but doesn't work (XPU, driver issues)

                log.info(f"Loading SD-Turbo on {device} (first time downloads ~2GB)...")
                # Diffusers defaults to safety_checker=None for SD-Turbo — the library
                # itself prints a warning advising NOT to expose this in user-facing
                # services. Load the checker explicitly; fail-secure if unavailable.
                try:
                    from diffusers.pipelines.stable_diffusion.safety_checker import (
                        StableDiffusionSafetyChecker,
                    )
                    from transformers import CLIPImageProcessor
                    safety_checker = StableDiffusionSafetyChecker.from_pretrained(
                        "CompVis/stable-diffusion-safety-checker",
                        torch_dtype=dtype,
                    )
                    feature_extractor = CLIPImageProcessor.from_pretrained(
                        "openai/clip-vit-base-patch32",
                    )
                except Exception as e:
                    return ToolResult(
                        "Image generation refused: safety checker could not be loaded "
                        f"({e}). Image generation is disabled until the checker is available.",
                        is_error=True,
                    )

                self._sd_pipe = AutoPipelineForText2Image.from_pretrained(
                    "stabilityai/sd-turbo",
                    torch_dtype=dtype,
                    variant="fp16" if dtype == torch.float16 else None,
                    safety_checker=safety_checker,
                    feature_extractor=feature_extractor,
                )
                self._sd_pipe.to(device)
                log.info("SD-Turbo loaded with safety checker")

            # SD-Turbo only supports up to 512×512 — warn explicitly when capping so
            # callers know their requested dimensions weren't honored.
            req_w, req_h = w, h
            w, h = min(w, 512), min(h, 512)
            if (req_w, req_h) != (w, h):
                log.warning(f"SD-Turbo requested {req_w}x{req_h}, capped to {w}x{h}")

            import time
            t0 = time.time()
            image = self._sd_pipe(
                prompt=prompt,
                num_inference_steps=1,
                guidance_scale=0.0,
                width=w,
                height=h,
            ).images[0]
            elapsed = time.time() - t0

            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(path))
            cap_note = f" (requested {req_w}x{req_h}, capped to {w}x{h})" if (req_w, req_h) != (w, h) else ""
            url_hint = _public_url_hint(path)
            return ToolResult(
                f"Image generated and saved to {path} (SD-Turbo {w}x{h}, {elapsed:.1f}s){cap_note}"
                + (f"\nReference in JSX as <img src=\"{url_hint}\" />" if url_hint else "")
            )

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
