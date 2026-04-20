"""Guard against the 'inline style zero-padding' regression across every
scaffold's index.html.

Background: an inline `<style>* { margin: 0; padding: 0; ... }</style>` in
the scaffold's index.html beats every Tailwind px-*/py-*/m-* utility
because inline styles are un-layered, and un-layered rules outrank
`@layer utilities` regardless of selector specificity. PIKO v5 shipped
with all container paddings zeroed — content hugging the viewport. The
fix is to scope `margin: 0` to `body` and keep only `box-sizing` as
universal. We check every index.html / top-level .html in scaffolds/
to make sure future additions follow the same rule.
"""

from pathlib import Path

import pytest

SCAFFOLDS = Path(__file__).parent.parent.parent / "scaffolds"


def _scaffold_html_files() -> list[Path]:
    """Every HTML file Tsunami ships as part of a scaffold. Excludes
    dist/ (built artifacts — they'll be regenerated from source) and
    node_modules (vendor copies)."""
    out: list[Path] = []
    for path in SCAFFOLDS.rglob("*.html"):
        parts = path.parts
        if "dist" in parts or "node_modules" in parts:
            continue
        out.append(path)
    return out


@pytest.mark.parametrize(
    "path",
    _scaffold_html_files(),
    ids=lambda p: str(p.relative_to(SCAFFOLDS)) if SCAFFOLDS in p.parents else p.name,
)
def test_no_inline_universal_padding_reset(path: Path):
    """No scaffold HTML should ship the Tailwind-killing pattern:
        <style>* { margin: 0; padding: 0; ... }</style>

    The fix is to narrow the universal rule to box-sizing only, and move
    margin: 0 onto body. Any HTML found violating this will silently zero
    Tailwind's spacing utilities at runtime.
    """
    text = path.read_text()
    violation = "* { margin: 0; padding: 0;"
    assert violation not in text, (
        f"{path.relative_to(SCAFFOLDS)} ships a universal `* {{ margin: 0; "
        f"padding: 0; ... }}` inline style, which silently zeroes every "
        f"Tailwind spacing utility (PIKO v5 shipped with hero hugging the "
        f"viewport because of this). Rewrite as:\n"
        f"  *, *::before, *::after {{ box-sizing: border-box; }} "
        f"body {{ margin: 0; }}"
    )
