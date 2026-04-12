"""Vision grounding — extract element positions from reference images.

Qwen-VL can identify UI elements and return bounding boxes:
  "Where is the A button?" → <ref>A button</ref><box>(723,456),(812,545)</box>

Coordinates are normalized to 0-1000 scale. We convert to percentages
so the agent can use them directly in CSS positioning.

This is the bridge between "looks roughly like a gameboy" and
"pixel-perfect replica". The agent sees WHERE things are, not just
what they look like.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from pathlib import Path

import httpx

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.vision_ground")

# Vision model endpoint — separate from the text wave
VL_ENDPOINT = os.environ.get("TSUNAMI_VL_ENDPOINT", "http://localhost:8094")


class VisionGround(BaseTool):
    name = "vision_ground"
    description = (
        "Extract UI element positions from a reference image. "
        "Give it an image path and a list of elements to find. "
        "Returns bounding boxes as percentages — use these for exact CSS positioning. "
        "ALWAYS use this after finding reference images to get precise element layouts."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Path to the reference image (PNG, JPG, or SVG)",
                },
                "elements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of UI elements to locate, e.g. "
                        '["A button", "B button", "D-pad", "screen", "speaker grille"]'
                    ),
                },
            },
            "required": ["image_path", "elements"],
        }

    async def execute(self, image_path: str, elements: list[str] | None = None, **kw) -> ToolResult:
        if not elements:
            return ToolResult("No elements specified to find", is_error=True)

        p = Path(image_path).expanduser().resolve()
        if not p.exists():
            return ToolResult(f"Image not found: {p}", is_error=True)

        # Encode image to base64
        image_b64 = _encode_image(p)
        if not image_b64:
            return ToolResult(f"Failed to encode image: {p}", is_error=True)

        # Try dedicated VL endpoint first, then eddy, then the main tsunami
        # endpoint (Gemma-4 is multimodal — same pattern as undertow's
        # _vlm_describe_screenshot). Every reasonable deployment has at least
        # the main endpoint up, so this should always have a fallback.
        fallbacks = [
            VL_ENDPOINT,
            os.environ.get("TSUNAMI_EDDY_ENDPOINT", "http://localhost:8092"),
            os.environ.get("TSUNAMI_MODEL_ENDPOINT", "http://localhost:8090"),
        ]
        # Dedupe while preserving order
        seen = set()
        ordered = [e for e in fallbacks if not (e in seen or seen.add(e))]
        for endpoint in ordered:
            result = await _ground_elements(endpoint, image_b64, elements, str(p))
            if result:
                return ToolResult(result)

        return ToolResult(
            "Vision grounding unavailable — no VL model endpoint responding. "
            "Start a vision model on port 8094, or ensure the main tsunami "
            "endpoint is reachable (multimodal Gemma-4 handles grounding).",
            is_error=True,
        )


async def _ground_elements(endpoint: str, image_b64: str, elements: list[str], image_path: str) -> str | None:
    """Ask Qwen-VL to locate elements in the image.

    Uses the grounding prompt format that triggers bbox output:
    <img>base64...</img>Locate these elements: A button, B button, screen
    """
    # Build the grounding prompt
    element_list = ", ".join(elements)
    prompt = (
        f"Look at this UI/device image. For each element listed below, "
        f"describe its position as a RATIO of the total image dimensions "
        f"(left%, top%, width%, height%). These are proportional — "
        f"50% means halfway across. Be precise.\n\n"
        f"Also note the overall aspect ratio of the device "
        f"(e.g. portrait 7:12 for a Game Boy, landscape 16:9 for a monitor).\n\n"
        f"Elements to locate: {element_list}\n\n"
        f"For each element, respond in this exact format:\n"
        f"ASPECT_RATIO: <W>:<H>\n"
        f"ELEMENT: <name>\n"
        f"POSITION: left=<X>% top=<Y>% width=<W>% height=<H>%\n"
        f"COLOR: <dominant color hex>\n"
        f"NOTES: <shape, style details>\n"
    )

    try:
        # 300s — under concurrent QA load the gpu_sem queue + 1500-token
        # vision-grounding generate can take 3-5 min end-to-end. Empirical
        # 180s timeout still fired ReadTimeout. Vision grounding is
        # best-effort under load; if 300s isn't enough the tool returns
        # "unavailable" and the caller falls back to text-only reasoning.
        async with httpx.AsyncClient(timeout=300) as client:
            # Health check
            try:
                resp = await client.get(f"{endpoint}/health")
                if resp.status_code != 200:
                    return None
            except Exception:
                return None

            # Send vision request (OpenAI-compatible multimodal format)
            resp = await client.post(
                f"{endpoint}/v1/chat/completions",
                json={
                    "model": "qwen-vl",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                            ],
                        }
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.1,
                },
                headers={"Authorization": "Bearer not-needed"},
            )

            if resp.status_code != 200:
                log.warning(f"VL endpoint {endpoint} returned {resp.status_code}")
                return None

            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Parse the response into structured data
            parsed = _parse_grounding_response(content, elements)

            # Format output
            lines = [f"Vision grounding for: {image_path}"]
            lines.append(f"Elements found: {len(parsed)}/{len(elements)}\n")

            for elem in parsed:
                lines.append(f"  {elem['name']}:")
                lines.append(f"    position: left={elem['left']}% top={elem['top']}% "
                             f"width={elem['width']}% height={elem['height']}%")
                if elem.get("color"):
                    lines.append(f"    color: {elem['color']}")
                if elem.get("notes"):
                    lines.append(f"    notes: {elem['notes']}")

            # Add CSS positioning hints
            lines.append("\nCSS positioning hints (use position:absolute inside a relative container):")
            for elem in parsed:
                name_css = elem["name"].lower().replace(" ", "-").replace("/", "-")
                lines.append(
                    f"  .{name_css} {{ "
                    f"position: absolute; "
                    f"left: {elem['left']}%; "
                    f"top: {elem['top']}%; "
                    f"width: {elem['width']}%; "
                    f"height: {elem['height']}%; "
                    f"}}"
                )

            return "\n".join(lines)

    except Exception as e:
        # httpx.ReadTimeout sometimes stringifies as empty — include type name.
        log.warning(f"Vision grounding failed on {endpoint}: {type(e).__name__}: {e or '(no message)'}")
        return None


def _parse_grounding_response(content: str, elements: list[str]) -> list[dict]:
    """Parse the VL model's element position response into structured data."""
    results = []

    # Try structured format first: ELEMENT: ... POSITION: left=X% top=Y%...
    blocks = re.split(r'(?=ELEMENT:)', content, flags=re.IGNORECASE)
    for block in blocks:
        if not block.strip():
            continue

        name_match = re.search(r'ELEMENT:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
        pos_match = re.search(
            r'left\s*=?\s*(\d+(?:\.\d+)?)%?\s+'
            r'top\s*=?\s*(\d+(?:\.\d+)?)%?\s+'
            r'width\s*=?\s*(\d+(?:\.\d+)?)%?\s+'
            r'height\s*=?\s*(\d+(?:\.\d+)?)%?',
            block, re.IGNORECASE,
        )
        color_match = re.search(r'COLOR:\s*(#[0-9a-fA-F]{3,8}|\w+)', block, re.IGNORECASE)
        notes_match = re.search(r'NOTES:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)

        if name_match and pos_match:
            results.append({
                "name": name_match.group(1).strip(),
                "left": float(pos_match.group(1)),
                "top": float(pos_match.group(2)),
                "width": float(pos_match.group(3)),
                "height": float(pos_match.group(4)),
                "color": color_match.group(1) if color_match else "",
                "notes": notes_match.group(1).strip() if notes_match else "",
            })

    # Also try Qwen-VL native grounding format: <box>(x1,y1),(x2,y2)</box>
    # Coordinates are 0-1000 normalized
    box_pattern = re.findall(
        r'<ref>(.*?)</ref>\s*<box>\((\d+),(\d+)\),\((\d+),(\d+)\)</box>',
        content,
    )
    for name, x1, y1, x2, y2 in box_pattern:
        # Convert 0-1000 to percentages
        x1, y1, x2, y2 = float(x1) / 10, float(y1) / 10, float(x2) / 10, float(y2) / 10
        results.append({
            "name": name.strip(),
            "left": round(x1, 1),
            "top": round(y1, 1),
            "width": round(x2 - x1, 1),
            "height": round(y2 - y1, 1),
            "color": "",
            "notes": "",
        })

    # If no structured results, try to match element names with any percentages nearby
    if not results:
        for elem in elements:
            pattern = re.search(
                rf'{re.escape(elem)}[^%]*?(\d+(?:\.\d+)?)%[^%]*?(\d+(?:\.\d+)?)%'
                rf'[^%]*?(\d+(?:\.\d+)?)%[^%]*?(\d+(?:\.\d+)?)%',
                content, re.IGNORECASE,
            )
            if pattern:
                results.append({
                    "name": elem,
                    "left": float(pattern.group(1)),
                    "top": float(pattern.group(2)),
                    "width": float(pattern.group(3)),
                    "height": float(pattern.group(4)),
                    "color": "",
                    "notes": "",
                })

    return results


def _encode_image(path: Path) -> str | None:
    """Encode an image to base64. Converts SVG to PNG if needed."""
    try:
        if path.suffix.lower() == ".svg":
            # SVG → can't be directly used for vision, skip
            return None

        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")
    except Exception as e:
        log.warning(f"Failed to encode {path}: {e}")
        return None
