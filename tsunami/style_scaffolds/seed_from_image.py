"""Seed-from-image resolver — step-zero style picker.

Pipeline (mirrors the existing TSUNAMI_STYLE env pattern, but takes an
image instead of a doctrine name):

  TSUNAMI_STYLE_SEED=/path/or/url  →  synthesize_seeded_style() runs FIRST

Steps (all cheap, all with graceful fallbacks):
  1. Palette extract — PIL quantize → 3–5 dominant hex colors + mean
     lightness (→ mode: light|neutral|dark by lightness bucket).
  2. Mood VLM probe — one call to the local Qwen/ERNIE multimodal
     endpoint asking a FIXED classification prompt. On timeout /
     endpoint-down, we skip and rely on palette-only matching.
  3. Hybrid synthesis — load the matched doctrine's body, OVERRIDE
     its ## Palette section with the extracted hex, APPEND a
     ## Seed Image Notes section with the VLM's mood observations.
  4. Return (name, body) — `pick_style()` returns this verbatim so
     `format_style_directive()` injects the synthesized body as
     usual. Name is `seed_<base_doctrine>` so downstream logs can
     trace provenance.

The 9 doctrines encode layout / motion / structural moves that one
image cannot supply. Image gives PALETTE + MOOD; doctrine supplies
SKELETON. Same hybrid pattern as editorial_dark + "use your client's
brand colors" — structure is reusable, surface is bespoke.

Environment:
  TSUNAMI_STYLE_SEED       — path or URL to the seed image (required)
  TSUNAMI_VLM_ENDPOINT     — default http://localhost:8090 (override)
  TSUNAMI_VLM_TIMEOUT_S    — default 20
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

log_lines: list[str] = []  # ephemeral trace; accessible via get_trace()


def _log(s: str) -> None:
    log_lines.append(s)


def get_trace() -> list[str]:
    return log_lines.copy()


# ── Step 1: palette extraction ────────────────────────────────────────────

def _load_image_bytes(src: str) -> bytes:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(
            src, headers={"User-Agent": "Mozilla/5.0 tsunami-seed"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    return Path(src).read_bytes()


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    r, g, b = r / 255, g / 255, b / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6
    elif mx == g:
        h = ((b - r) / d + 2) / 6
    else:
        h = ((r - g) / d + 4) / 6
    return h, s, l


def _hue_bucket(h: float, s: float) -> str:
    if s < 0.15:
        return "neutral"
    deg = h * 360
    if deg < 15 or deg >= 345: return "red"
    if deg < 45:               return "orange"
    if deg < 70:               return "yellow"
    if deg < 150:              return "green"
    if deg < 200:              return "teal"
    if deg < 255:              return "blue"
    if deg < 290:              return "purple"
    return "magenta"


def extract_palette(image_path: str, k: int = 5) -> dict:
    """Extract dominant colors + perceived lightness + accent hue.

    Uses PIL's quantize (median-cut) — no sklearn / colorthief dep.
    """
    try:
        from PIL import Image  # lazy import so the module loads without PIL
    except Exception as e:
        _log(f"palette: PIL unavailable ({e}) — returning empty")
        return {"hex": [], "mode": "", "accent_hue": "", "mean_lightness": 0.0}

    raw = _load_image_bytes(image_path)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    # downsample for speed — palette quality survives at 200px
    img.thumbnail((200, 200))

    q = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: k * 3]
    counts = Counter(q.getdata())  # pixel -> palette index
    ranked = [idx for idx, _ in counts.most_common()]
    rgb_ranked = [(pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]) for i in ranked]

    hexes = [_rgb_to_hex(c) for c in rgb_ranked]

    # mean lightness weighted by pixel count
    total = sum(counts.values())
    mean_l = sum(_luminance(c) * counts[ranked[i]] for i, c in enumerate(rgb_ranked)) / total

    # Dominant background hue/sat — used to distinguish warm-paper (cream,
    # bone, sand — "neutral" mode) from pure-white ("light" mode). Both are
    # bright, so lightness alone cannot tell them apart.
    bg_h, bg_s, bg_l = _rgb_to_hsl(*rgb_ranked[0])
    bg_hue_deg = bg_h * 360

    # Mode bucket. Cross-check against the 155-template scrape showed
    # that PNG-based mode and CSS-declared mode agree on only 54% — this
    # divergence is INTENTIONAL: the classifier scores what a viewer
    # sees, not what the designer coded. A portfolio with `bg=#fff` but
    # heavy dark-photo hero should seed as `dark` / `neutral`, matching
    # the visual feel — that's the whole point of seeding from an image.
    #
    # Thresholds:
    #   mean_l < 0.22  → dark
    #   mean_l > 0.75  → light (pure/cool) or neutral (warm-bg + sat)
    #   else           → neutral (warm-paper / mid-imagery / loaded scene)
    if mean_l < 0.22:
        mode = "dark"
    elif mean_l > 0.75:
        if 15 <= bg_hue_deg <= 55 and bg_s >= 0.07:
            mode = "neutral"   # warm cream / bone / sand
        else:
            mode = "light"     # pure white / cool-grey
    else:
        mode = "neutral"

    # accent hue — take the most saturated non-neutral color
    accent_rgb = None
    best_s = 0.0
    for c in rgb_ranked:
        _, s, _ = _rgb_to_hsl(*c)
        if s > best_s:
            best_s = s
            accent_rgb = c
    accent_hue = "neutral"
    if accent_rgb and best_s > 0.15:
        h, s, _l = _rgb_to_hsl(*accent_rgb)
        accent_hue = _hue_bucket(h, s)

    _log(f"palette: {hexes}  mode={mode}  accent_hue={accent_hue}  mean_l={mean_l:.2f}")
    return {
        "hex": hexes,
        "mode": mode,
        "accent_hue": accent_hue,
        "mean_lightness": round(mean_l, 3),
        "accent_hex": _rgb_to_hex(accent_rgb) if accent_rgb else "",
    }


# ── Step 2: VLM mood probe ────────────────────────────────────────────────

_VLM_SYSTEM = (
    "You classify a single reference image into one of our site-design "
    "doctrines. Reply in EXACTLY this format, no preamble:\n"
    "DOCTRINE: <one of: editorial_dark, shadcn_startup, photo_studio, "
    "magazine_editorial, playful_chromatic, swiss_modern, cinematic_display, "
    "atelier_warm, newsroom_editorial, brutalist_web>\n"
    "TYPEFACE: <serif_display | sans_display | condensed_display | mono>\n"
    "DENSITY: <dense | negative_space>\n"
    "MOTION: <motion_forward | minimal>\n"
    "NOTES: <one short sentence of distinctive observations>"
)
_VLM_USER = (
    "Classify this image's aesthetic. Base the doctrine choice on overall "
    "feel — palette, type, density, grain of the composition. Be decisive, "
    "return exactly the format above."
)

_VALID_DOCTRINES = {
    "editorial_dark", "shadcn_startup", "photo_studio", "magazine_editorial",
    "playful_chromatic", "swiss_modern", "cinematic_display", "atelier_warm",
    "newsroom_editorial", "brutalist_web",
}


def vlm_probe(image_path: str,
              endpoint: str | None = None,
              timeout_s: int | None = None) -> dict:
    """Multimodal mood classification — DEFERRED since 2026-04-26.

    Originally called a local Qwen3.6-VL endpoint at localhost:8090 to
    classify a reference image's mood (warm/cool/playful/serious/etc.).
    That endpoint was retired with the local-LLM stack in c94b029, and
    the Claude-vision-via-API replacement is part of the deferred
    "Generations TBD" work. For now this returns {} immediately so
    callers fall back to palette-only matching without burning a 20s
    timeout per call.

    Re-enabling: replace the urllib POST below with an Anthropic vision
    API call (anthropic.Anthropic().messages.create with image content),
    or whatever your harness provides. The _VLM_SYSTEM / _VLM_USER
    prompts are preserved unchanged below for that future re-enablement.
    """
    _log("vlm_probe: skipped (deferred until image-gen pipeline returns)")
    return {}

    # Preserved for future re-enablement — see docstring above.
    endpoint = endpoint or os.environ.get("TSUNAMI_VLM_ENDPOINT", "http://localhost:8090")
    timeout_s = timeout_s or int(os.environ.get("TSUNAMI_VLM_TIMEOUT_S", "20"))

    try:
        raw = _load_image_bytes(image_path)
        b64 = base64.b64encode(raw).decode()

        payload = {
            "model": "tsunami",
            "max_tokens": 160,
            "temperature": 0.1,
            "enable_thinking": False,
            "messages": [
                {"role": "system", "content": _VLM_SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": _VLM_USER},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
        }
        req = urllib.request.Request(
            f"{endpoint.rstrip('/')}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer not-needed",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = json.loads(r.read().decode())
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    except Exception as e:
        _log(f"vlm: endpoint unreachable / error — fallback to palette-only ({e})")
        return {}

    def _grab(label: str) -> str:
        m = re.search(rf"^{label}:\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    doctrine = _grab("DOCTRINE").lower().replace(" ", "_")
    if doctrine not in _VALID_DOCTRINES:
        _log(f"vlm: doctrine '{doctrine}' not in whitelist — ignored")
        doctrine = ""
    out = {
        "doctrine": doctrine,
        "typeface": _grab("TYPEFACE"),
        "density":  _grab("DENSITY"),
        "motion":   _grab("MOTION"),
        "notes":    _grab("NOTES"),
        "raw":      text,
    }
    _log(f"vlm: doctrine={doctrine}  typeface={out['typeface']}  density={out['density']}")
    return out


# ── Step 3: closest-doctrine via palette fallback ─────────────────────────

# Rough accent-hue → doctrine mapping when the VLM is unavailable.
# Ordered by preference within each mode bucket.
_PALETTE_FALLBACK = {
    "light": {
        "neutral": "shadcn_startup",    # white + grey accents — safe baseline
        "blue":    "shadcn_startup",    # signal-blue cluster
        "purple":  "shadcn_startup",    # electric-purple cluster
        "orange":  "photo_studio",      # coral-accent photographer cluster
        "red":     "newsroom_editorial",# breaking-news red
        "yellow":  "shadcn_startup",    # highlight-yellow startup
        "green":   "shadcn_startup",
        "teal":    "shadcn_startup",
        "magenta": "playful_chromatic",
    },
    "neutral": {
        "neutral": "magazine_editorial",
        "orange":  "atelier_warm",
        "red":     "atelier_warm",
        "yellow":  "atelier_warm",
        "green":   "atelier_warm",
        "blue":    "magazine_editorial",
        "purple":  "playful_chromatic",
        "teal":    "atelier_warm",
        "magenta": "playful_chromatic",
    },
    "dark": {
        "neutral": "cinematic_display",
        "red":     "cinematic_display",
        "yellow":  "cinematic_display",
        "orange":  "editorial_dark",   # gold/copper luxury accent
        "blue":    "editorial_dark",
        "purple":  "editorial_dark",
        "green":   "editorial_dark",
        "teal":    "editorial_dark",
        "magenta": "cinematic_display",
    },
}


def closest_doctrine(palette: dict) -> str:
    mode = palette.get("mode", "light")
    hue  = palette.get("accent_hue", "neutral")
    return _PALETTE_FALLBACK.get(mode, {}).get(hue, "shadcn_startup")


# ── Step 4: hybrid synthesis ──────────────────────────────────────────────

_PALETTE_SECTION_RE = re.compile(
    r"(## Palette\s*\n)(.*?)(?=\n## |\Z)", re.DOTALL
)


def _render_palette_override(palette: dict) -> str:
    hex_list = palette.get("hex", [])
    lines = [
        "<!-- OVERRIDDEN from seed image — base doctrine palette superseded -->",
        f"- Mode inferred from seed: **{palette.get('mode','?')}** "
        f"(mean lightness {palette.get('mean_lightness','?')}).",
        "- Dominant hex colors (ranked by pixel share):",
    ]
    for i, h in enumerate(hex_list):
        role = (
            "background" if i == 0 else
            "foreground" if i == 1 else
            "accent" if i == 2 else
            "tertiary"
        )
        lines.append(f"  - `{h}` — suggested `{role}`")
    if palette.get("accent_hex"):
        lines.append(f"- Accent hue ({palette.get('accent_hue')}) concentrated at `{palette['accent_hex']}` — use for interactive elements.")
    lines.append(
        "- KEEP this palette. Do NOT substitute the base doctrine's palette. "
        "The base doctrine's typography / layout / motion sections still apply."
    )
    return "\n".join(lines) + "\n"


_DEFAULT_MODE_LINE_RE = re.compile(r"^(default_mode\s*:\s*)(light|neutral|dark)\s*$", re.MULTILINE)


def synthesize_seeded_style(seed: dict) -> tuple[str, str]:
    """Produce (name, body) for a seeded style.

    `seed` is the dict returned by `extract_seed()` below.

    Mode conflict resolution: if the base doctrine's default_mode disagrees
    with the seed palette's inferred mode (e.g. VLM picks brutalist_web
    which wants `light`, but the seed image is clearly dark), we OVERRIDE
    the body's `default_mode` frontmatter with the seed mode. The palette
    is load-bearing — the scaffold-activation note must match it or the
    drone imports the wrong tokens_*.css file.
    """
    base = seed["doctrine"]
    body_path = Path(__file__).parent / f"{base}.md"
    if not body_path.is_file():
        _log(f"synthesize: base doctrine '{base}' not found — falling back to shadcn_startup")
        base = "shadcn_startup"
        body_path = Path(__file__).parent / f"{base}.md"
    base_body = body_path.read_text()

    # 0. Reconcile mode — seed wins over base doctrine.
    seed_mode = seed.get("palette", {}).get("mode", "")
    if seed_mode in ("light", "neutral", "dark"):
        m = _DEFAULT_MODE_LINE_RE.search(base_body)
        if m and m.group(2) != seed_mode:
            _log(f"synthesize: mode conflict — base={m.group(2)} seed={seed_mode}; overriding to seed")
            base_body = _DEFAULT_MODE_LINE_RE.sub(
                rf"\g<1>{seed_mode}", base_body, count=1
            )

    # 1. Override Palette section
    override = _render_palette_override(seed["palette"])
    if _PALETTE_SECTION_RE.search(base_body):
        body = _PALETTE_SECTION_RE.sub(rf"\1{override}\n", base_body, count=1)
    else:
        body = base_body + "\n\n## Palette\n" + override

    # 2. Append Seed Image Notes (VLM output + palette trace)
    notes = ["\n## Seed Image Notes\n"]
    vlm = seed.get("vlm") or {}
    if vlm:
        notes.append(f"- VLM classification: `{vlm.get('doctrine','?')}`")
        notes.append(f"- Typeface hint: {vlm.get('typeface','?')}")
        notes.append(f"- Density: {vlm.get('density','?')}")
        notes.append(f"- Motion: {vlm.get('motion','?')}")
        if vlm.get("notes"):
            notes.append(f"- Observation: {vlm['notes']}")
    else:
        notes.append("- VLM unavailable — using palette-only matching.")
    notes.append(f"- Base doctrine chosen: **{base}** "
                 f"({'VLM-picked' if vlm.get('doctrine') == base else 'palette-fallback'}).")
    notes.append(
        "- If the base doctrine's layout (hero shape / section order) feels "
        "wrong for the seed image, trust the seed — change the layout. The "
        "palette-lock above is the load-bearing constraint."
    )

    body = body + "\n".join(notes) + "\n"

    name = f"seed_{base}"
    return name, body


# ── Public entry point ────────────────────────────────────────────────────

def extract_seed(image_path: str) -> dict:
    """Run palette + VLM + doctrine-match. Returns a seed record."""
    log_lines.clear()
    palette = extract_palette(image_path)
    vlm = vlm_probe(image_path)
    vlm_doctrine = vlm.get("doctrine") if vlm else ""

    if vlm_doctrine:
        doctrine = vlm_doctrine
    else:
        doctrine = closest_doctrine(palette)

    seed = {
        "image_path": image_path,
        "palette": palette,
        "vlm": vlm,
        "doctrine": doctrine,
        "trace": get_trace(),
    }
    return seed


__all__ = [
    "extract_seed",
    "synthesize_seeded_style",
    "extract_palette",
    "vlm_probe",
    "closest_doctrine",
]
