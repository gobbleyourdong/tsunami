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


def _extract_alpha(path: Path, mode: str, pixel_art: bool = False) -> None:
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
                     When `pixel_art` is True the icon branch uses the
                     pixel_extract pipeline instead (Lab-space bg detection,
                     native-grid recovery, center-sampling, two-threshold
                     fringe peel) — ONLY appropriate for generations where
                     the subject is actually pixel art, since it quantizes
                     colors and snaps to a discovered grid.

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
        # Lab-space bg removal (with optional grid recovery if the subject
        # is actually pixel art). Both paths share the same bg-detection +
        # palette-quantization + two-threshold fringe peel — that's what
        # eliminates magenta-tinted fringe the RGB color-key couldn't reach
        # and handles interior holes (letter A, donuts, gear teeth) by
        # keying on color rather than spatial connectedness.
        #
        # Grid recovery snaps each AI-drawn pixel to a recovered native grid
        # and mode-samples per cell. That's only appropriate when the source
        # IS pixel art — running it on a photo or painting would quantize
        # and blockify the image. The caller tells us via the pixel_art flag.
        from PIL import Image as _Image2
        if pixel_art:
            from .pixel_extract import extract_one  # noqa: WPS433
            rgba_in = _np.dstack([arr.astype(_np.uint8), _np.full(arr.shape[:2], 255, dtype=_np.uint8)])
            result = extract_one(rgba_in)
            if result is None:
                rgba = _np.dstack([arr.astype(_np.uint8), _np.full(arr.shape[:2], 255, dtype=_np.uint8)])
            else:
                sprite = result.rgba
                sh, sw = sprite.shape[:2]
                # Preserve pixel structure: largest integer NN factor that fits,
                # then center on a transparent canvas at (w, h).
                factor = max(1, min(h // sh, w // sw))
                up = _Image2.fromarray(sprite, mode="RGBA").resize(
                    (sw * factor, sh * factor), _Image2.Resampling.NEAREST,
                ) if factor > 1 else _Image2.fromarray(sprite, mode="RGBA")
                canvas = _Image2.new("RGBA", (w, h), (0, 0, 0, 0))
                canvas.paste(up, ((w - up.size[0]) // 2, (h - up.size[1]) // 2))
                rgba = _np.asarray(canvas)
        else:
            from .pixel_extract import extract_alpha  # noqa: WPS433
            rgba_in = _np.dstack([arr.astype(_np.uint8), _np.full(arr.shape[:2], 255, dtype=_np.uint8)])
            rgba = extract_alpha(rgba_in)
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
        "Generate an image from a text description. "
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
            # _active_project can arrive in multiple shapes:
            #   - bare name ("gallery")
            #   - "deliverables/gallery"
            #   - "workspace/deliverables/gallery"
            #   - absolute path ("/tmp/ws/deliverables/gallery")
            # Only prepend workspace_dir when it's clearly relative.
            # Stripping leading "/" on an absolute path and then joining
            # re-produces the workspace prefix → nested doubled path like
            # /tmp/ws/tmp/ws/deliverables/gallery.
            if _active_project.startswith("/"):
                project_root = Path(_active_project)
            else:
                proj_rel = _active_project
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
            # If save_path is already absolute (e.g. `/tmp/x/public/art/1.png`),
            # use it as-is. Prior logic stripped the leading slash, treated it
            # as relative, and prepended workspace_dir again → double-nested
            # path like /tmp/x/tmp/x/public/art/1.png.
            if save_path.startswith("/"):
                actual_save = Path(save_path).resolve()
            else:
                actual_clean = save_path
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
            # Absolute path → use as-is. Prior code stripped the leading
            # slash and re-joined workspace_dir, producing /tmp/ws/tmp/ws/…
            # when the drone passed an already-absolute save_path.
            if save_path.startswith("/"):
                p = Path(save_path).resolve()
            else:
                # Strip "workspace/" prefix if the model sends absolute-looking paths
                clean = save_path
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
            # Pure black background. Simple, common in AI training data, and
            # most subject colors contrast strongly against it. Magenta and
            # green chromakeys both bled their hue into subject highlights
            # (pink-tinted foam, green speckle on edges) — black has no
            # chroma to bleed, just brightness.
            #
            # The one failure mode is dark subjects (black logos, dark
            # silhouettes) which can blend with the bg. Workaround: add a
            # contrasting outline in your prompt, e.g.
            #   "dark logo with thick white outline"
            prompt = (
                f"FLAT BACKGROUND SINGLE COLOR BLACK. "
                f"The entire background is pure black #000000, "
                f"completely uniform black filling the frame, "
                f"no gradients, no shading, no scenery, no other background elements. "
                f"Subject: (({prompt})), centered, isolated, "
                f"on pure black field, "
                f"hard clean sharp edges, no anti-aliasing, no soft edges, "
                f"no edge blur, no fade between subject and background, "
                f"crisp pixelated boundary, sharp silhouette"
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
                    # Detect pixel-art intent from the prompt. The user has
                    # to SAY "pixel" or "sprite" (or close variants) for us
                    # to run the grid-recovery pass — otherwise we quantize
                    # and blockify photos and illustrations that weren't
                    # meant to be pixel art.
                    pixel_art = any(
                        tok in prompt.lower()
                        for tok in ("pixel art", "pixelart", "sprite", "8-bit", "8 bit", "16-bit", "16 bit")
                    )
                    try:
                        _extract_alpha(p, mode, pixel_art=pixel_art)
                        tag = mode + ("+pixel-grid" if (mode == "icon" and pixel_art) else "")
                        result = ToolResult(result.content + f"\nExtracted alpha (mode={tag})")
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
        import base64, random
        try:
            # Prefer the dedicated image endpoint (:8092 ernie_server).
            # The text-model proxy on :8090 only routes images if SD_SERVER_URL
            # is set in its env, which isn't guaranteed. Going direct avoids
            # the hang when the proxy has `--image-model none`.
            import os as _oie
            endpoint = (
                _oie.environ.get("TSUNAMI_IMAGE_ENDPOINT")
                or "http://localhost:8092"
            )
            if not endpoint.startswith("http"):
                endpoint = f"http://{endpoint}"
            import httpx
            # Always pass a fresh random seed — without one Z-Image-Turbo's
            # sampler defaults to deterministic output, so repeated calls
            # with the same prompt return the same image. Users chaining
            # generations (banners, sprite sheets, variations) need variety.
            seed = random.randint(0, 2**31 - 1)
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{endpoint}/v1/images/generate",
                    json={
                        "prompt": prompt,
                        "width": w,
                        "height": h,
                        # Z-Image-Turbo official recipe: num_inference_steps=9
                        # (yields 8 DiT forwards), guidance_scale=0.0. We had
                        # been using steps=4 + guidance=1.0 which produced
                        # over-smooth, anti-aliased output — guidance>0 on a
                        # turbo model also degrades sharpness.
                        "steps": 9,
                        "guidance_scale": 0.0,
                        "seed": seed,
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
            f"Start the tsunami server with --image-model Tongyi-MAI/Z-Image-Turbo "
            f"to generate real images."
        )
