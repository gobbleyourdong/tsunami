"""Adversarial review — cross-examine reasoning before delivery.

After the wave writes a research synthesis or makes factual claims,
dispatch an eddy as a hostile reviewer. The eddy tries to BREAK
the argument. Its objections get fed back to the wave before delivery.

The undertow tests code. This tests reasoning.

Pattern:
1. Wave writes synthesis
2. Eddy receives: "assume this is wrong, find every error"
3. Eddy returns objections
4. Wave addresses objections or revises
5. Only then: deliver
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

from .config import resolve_aux_model_endpoint

log = logging.getLogger("tsunami.adversarial")

EDDY_ENDPOINT = resolve_aux_model_endpoint()


async def cross_examine(
    claim: str,
    context: str = "",
    endpoint: str = EDDY_ENDPOINT,
    model: str = "qwen",
) -> dict:
    """Send a claim to the eddy for adversarial review.

    The eddy tries to find flaws in the reasoning, not just facts.
    Returns dict with {objections: list[str], verdict: str, confidence: float}
    """
    prompt = f"""You are a hostile peer reviewer. Your job is to BREAK this argument.

Assume the following claim is WRONG and find every logical error, unstated assumption,
scope error, or reasoning flaw. Be specific. Cite which step fails and why.

Do NOT be polite. Do NOT say "interesting approach." Find the holes.

{"CONTEXT: " + context[:1000] if context else ""}

CLAIM TO ATTACK:
{claim[:2000]}

List every objection, one per line, starting with "FLAW:" for each one.
If you genuinely cannot find a flaw, say "NO FLAWS FOUND" (but try harder first).
End with VERDICT: PASS or FAIL."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{endpoint}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a ruthless peer reviewer. Find flaws in reasoning, not just facts."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
                headers={"Authorization": "Bearer not-needed"},
            )
            if resp.status_code != 200:
                return {"objections": [], "verdict": "ERROR", "confidence": 0.0, "raw": f"HTTP {resp.status_code}"}

            content = resp.json()["choices"][0]["message"]["content"].strip()

            # Parse objections
            objections = []
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("FLAW:"):
                    objections.append(line[5:].strip())

            # Parse verdict
            verdict = "UNKNOWN"
            if "VERDICT: PASS" in content.upper():
                verdict = "PASS"
            elif "VERDICT: FAIL" in content.upper():
                verdict = "FAIL"
            elif "NO FLAWS FOUND" in content.upper():
                verdict = "PASS"

            confidence = 1.0 - (len(objections) * 0.15)
            confidence = max(0.0, min(1.0, confidence))

            return {
                "objections": objections,
                "verdict": verdict,
                "confidence": confidence,
                "raw": content,
            }

    except Exception as e:
        log.warning(f"Adversarial review failed: {e}")
        return {"objections": [], "verdict": "ERROR", "confidence": 0.0, "raw": str(e)}


def format_review(review: dict) -> str:
    """Format adversarial review for injection into the wave's context."""
    if review["verdict"] == "ERROR":
        return "[Adversarial review unavailable]"

    if review["verdict"] == "PASS" and not review["objections"]:
        return "[Adversarial review: PASS — no flaws found]"

    lines = [f"[ADVERSARIAL REVIEW: {review['verdict']}]"]
    if review["objections"]:
        lines.append(f"The reviewer found {len(review['objections'])} potential flaws:")
        for i, obj in enumerate(review["objections"], 1):
            lines.append(f"  {i}. {obj}")
        lines.append("")
        lines.append("Address these objections before delivering. If any are valid, revise your conclusion.")
    return "\n".join(lines)


async def review_before_delivery(
    result_text: str,
    user_request: str = "",
    endpoint: str = EDDY_ENDPOINT,
) -> tuple[bool, str]:
    """Review a result before delivery.

    Returns (should_deliver, review_text).
    If should_deliver is False, the review_text contains objections
    that should be injected into the wave's context.
    """
    # Only review substantial claims (skip simple answers)
    if len(result_text) < 200:
        return True, ""

    # Check if result contains reasoning/claims worth reviewing
    reasoning_markers = [
        "therefore", "implies", "proves", "because", "since",
        "follows", "conclude", "shows that", "established",
        "proven", "verified", "confirmed", "chain",
    ]
    has_reasoning = any(m in result_text.lower() for m in reasoning_markers)
    if not has_reasoning:
        return True, ""

    review = await cross_examine(
        claim=result_text,
        context=user_request,
        endpoint=endpoint,
    )

    if review["verdict"] == "PASS":
        return True, format_review(review)

    if review["verdict"] == "FAIL" and review["objections"]:
        return False, format_review(review)

    # Unknown/error — let it through with warning
    return True, format_review(review)
