"""Current — semantic tension measurement.

Measures the coherence of a response by probing the model's own
confidence. Truth forms tight knots (low tension). Hallucination
forms loose tangles (high tension).

The current doesn't move the water. It measures which way it's flowing.

Based on the Wilson Loop / TuningFork from mind_proton:
- Generate response
- Probe alignment against truth anchors and drift markers
- Return tension score (0.0 = grounded, 1.0 = hallucinating)
- If tension high, iteratively correct by re-asking with focus
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from .config import resolve_aux_model_endpoint

log = logging.getLogger("tsunami.current")

# Tension thresholds
GROUNDED = 0.15      # Below this: deliver confidently
UNCERTAIN = 0.40     # Above this: needs correction or search
DRIFTING = 0.70      # Above this: don't deliver, say "I don't know"


@dataclass
class Depth:
    """A tension measurement result."""
    score: float              # 0.0 (grounded) to 1.0 (hallucinating)
    truth_alignment: float    # How well it aligns with truth anchors
    drift_alignment: float    # How well it aligns with drift markers
    classification: str       # "grounded", "uncertain", "drifting"
    details: dict = field(default_factory=dict)


# Truth anchors — statements a grounded response would align with
TRUTH_ANCHORS = [
    "This statement is factually accurate and verifiable.",
    "I am confident this is true based on evidence.",
    "This follows logically from established premises.",
]

# Drift markers — patterns that indicate hallucination
DRIFT_MARKERS = [
    "This statement might be fabricated or exaggerated.",
    "I'm not actually sure if this is accurate.",
    "This could be a plausible-sounding hallucination.",
]

# Textual red flags that increase tension without needing model eval
RED_FLAGS = [
    # Hedging that suggests uncertainty
    r'\b(I think|I believe|probably|might be|could be|possibly|not sure)\b',
    # Fabrication patterns
    r'\b(according to (my|some)|studies show that|research indicates)\b',
    # Specific numbers without source (likely hallucinated)
    r'\b\d{4,}\b.*\b(percent|million|billion|trillion)\b',
    # Confident claims about specific dates, names without citation markers
    r'\bin (January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b',
]

# Quality anchors that decrease tension
QUALITY_ANCHORS = [
    r'\[[\d]+\]',           # Citation markers [1], [2]
    r'https?://\S+',        # URLs (actual sources)
    r'\baccording to .*(Reuters|AP|Nature|Science|arXiv|IEEE|ACM)\b',
    r'\bpeer-reviewed\b',
    r'\bpublished in\b',
]

# Code tension — measured by the undertow (screenshot + static analysis),
# not by pattern matching here. Current only measures prose tension.
# The undertow is QA. Current is the lie detector. Different jobs.


def measure_heuristic(text: str) -> float:
    """Fast heuristic tension measurement — no model call needed.

    Measures PROSE tension only — is the text hedging, fabricating, or grounded?
    Code quality is measured by the undertow (screenshot + static analysis).
    Current is the lie detector. Undertow is QA. Different jobs.
    """
    if not text.strip():
        return 0.5  # empty = uncertain

    red_flag_count = sum(
        1 for pattern in RED_FLAGS
        if re.search(pattern, text, re.IGNORECASE)
    )
    quality_count = sum(
        1 for pattern in QUALITY_ANCHORS
        if re.search(pattern, text, re.IGNORECASE)
    )

    # Base tension from text length (very short = suspicious)
    length_factor = min(1.0, len(text) / 200)

    tension = 0.3  # baseline uncertain
    tension += red_flag_count * 0.1
    tension -= quality_count * 0.15
    tension -= length_factor * 0.1

    return max(0.0, min(1.0, tension))


async def measure_with_model(
    text: str,
    endpoint: str | None = None,
    model: str = "qwen",
) -> Depth:
    """Deep tension measurement using the 2B eddy as probe.

    Asks the model to evaluate the response against truth anchors
    and drift markers. Returns a Depth measurement.
    """
    endpoint = endpoint or resolve_aux_model_endpoint()

    # First: fast heuristic
    heuristic_score = measure_heuristic(text)

    # If heuristic is clearly grounded or clearly drifting, skip model call
    if heuristic_score < 0.1:
        return Depth(
            score=heuristic_score,
            truth_alignment=0.9,
            drift_alignment=0.1,
            classification="grounded",
        )
    if heuristic_score > 0.8:
        return Depth(
            score=heuristic_score,
            truth_alignment=0.1,
            drift_alignment=0.9,
            classification="drifting",
        )

    # Model-based probe: ask the 2B to evaluate
    probe_prompt = f"""Rate the factual reliability of this text on a scale of 1-10.
1 = clearly fabricated/hallucinated, 10 = verifiable and well-sourced.

Text: "{text[:500]}"

Respond with ONLY a number 1-10 and one word: the number, then "grounded" or "uncertain" or "drifting".
Example: "8 grounded" or "3 drifting"."""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{endpoint}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a factual reliability evaluator. Be strict."},
                        {"role": "user", "content": probe_prompt},
                    ],
                    "max_tokens": 20,
                    "temperature": 0.1,
                },
                headers={"Authorization": "Bearer not-needed"},
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                # Parse "8 grounded" or "3 drifting"
                parts = content.split()
                if parts:
                    try:
                        score_raw = int(parts[0])
                        model_tension = 1.0 - (score_raw / 10.0)
                    except ValueError:
                        model_tension = 0.5

                    # Blend heuristic and model scores
                    final_score = (heuristic_score * 0.4) + (model_tension * 0.6)
                else:
                    final_score = heuristic_score
            else:
                final_score = heuristic_score

    except Exception as e:
        log.warning(f"Current measurement failed: {e}")
        final_score = heuristic_score

    # Classify
    if final_score < GROUNDED:
        classification = "grounded"
    elif final_score < UNCERTAIN:
        classification = "uncertain"
    else:
        classification = "drifting"

    return Depth(
        score=final_score,
        truth_alignment=1.0 - final_score,
        drift_alignment=final_score,
        classification=classification,
        details={"heuristic": heuristic_score, "model_blend": final_score},
    )


async def correct_thought(
    original: str,
    tension: float,
    endpoint: str | None = None,
    model: str = "qwen",
    max_iterations: int = 3,
) -> str:
    """Iteratively correct a drifting response.

    The TuningFork pattern: re-ask with focus on uncertain parts
    until tension drops or max iterations reached.
    """
    endpoint = endpoint or resolve_aux_model_endpoint()

    if tension < UNCERTAIN:
        return original  # no correction needed

    current_text = original
    for i in range(max_iterations):
        correction_prompt = f"""The following response may contain inaccuracies.
Identify which specific claims are uncertain or likely wrong.
Rewrite ONLY the uncertain parts to be either:
- Factually correct (if you know the truth)
- Explicitly marked as uncertain ("approximately", "it is believed that")
- Removed (if you can't verify)

Original: "{current_text[:500]}"

Corrected version:"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{endpoint}/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": correction_prompt}],
                        "max_tokens": 512,
                        "temperature": 0.3,
                    },
                    headers={"Authorization": "Bearer not-needed"},
                )
                if resp.status_code == 200:
                    corrected = resp.json()["choices"][0]["message"]["content"].strip()
                    new_tension = measure_heuristic(corrected)
                    if new_tension < tension:
                        current_text = corrected
                        tension = new_tension
                    if tension < UNCERTAIN:
                        break
        except Exception:
            break

    return current_text
