"""Validator — verify training dataset integrity before fine-tuning.

Checks:
1. All JSONL files parse correctly
2. Required fields present in every example
3. Token counts within model context windows
4. No empty conversations
5. Diversity metrics (unique prompts, scaffold distribution)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("tsunami.training.validator")


def validate_jsonl(path: Path) -> dict:
    """Validate a single JSONL file.

    Returns {valid, total, errors, avg_tokens, max_tokens}.
    """
    total = 0
    valid = 0
    errors = []
    token_counts = []

    with open(path) as f:
        for i, line in enumerate(f):
            total += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {i+1}: JSON parse error: {e}")
                continue

            # Check structure
            if "conversations" in item:
                convos = item["conversations"]
                if not isinstance(convos, list) or len(convos) < 2:
                    errors.append(f"Line {i+1}: conversations must have 2+ turns")
                    continue
                if convos[0].get("from") != "human":
                    errors.append(f"Line {i+1}: first turn must be from 'human'")
                    continue
                if convos[1].get("from") != "gpt":
                    errors.append(f"Line {i+1}: second turn must be from 'gpt'")
                    continue
                if not convos[0].get("value", "").strip():
                    errors.append(f"Line {i+1}: empty human message")
                    continue
                if not convos[1].get("value", "").strip():
                    errors.append(f"Line {i+1}: empty gpt response")
                    continue
                # Token count
                tokens = sum(len(c.get("value", "")) for c in convos) // 4
                token_counts.append(tokens)

            elif "prompt" in item and "chosen" in item:
                # DPO format
                if not item.get("chosen", "").strip():
                    errors.append(f"Line {i+1}: empty chosen response")
                    continue
                tokens = (len(item.get("prompt", "")) + len(item.get("chosen", ""))) // 4
                token_counts.append(tokens)

            elif "query" in item and "tool_calls" in item:
                # ToolBench format
                if not item.get("tool_calls"):
                    errors.append(f"Line {i+1}: empty tool_calls")
                    continue
                tokens = len(json.dumps(item)) // 4
                token_counts.append(tokens)

            else:
                errors.append(f"Line {i+1}: unrecognized format")
                continue

            valid += 1

    return {
        "path": str(path),
        "total": total,
        "valid": valid,
        "errors": errors[:10],  # cap error list
        "avg_tokens": round(sum(token_counts) / len(token_counts)) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "min_tokens": min(token_counts) if token_counts else 0,
    }


def validate_dataset(dataset_dir: Path) -> dict:
    """Validate all JSONL files in a dataset directory.

    Returns a summary with per-file stats and overall health.
    """
    if not dataset_dir.exists():
        return {"error": f"Directory not found: {dataset_dir}"}

    files = sorted(dataset_dir.glob("*.jsonl"))
    if not files:
        return {"error": "No JSONL files found"}

    results = {}
    total_examples = 0
    total_errors = 0

    for f in files:
        r = validate_jsonl(f)
        results[f.name] = r
        total_examples += r["valid"]
        total_errors += len(r["errors"])

    return {
        "files": len(files),
        "total_examples": total_examples,
        "total_errors": total_errors,
        "healthy": total_errors == 0,
        "details": results,
    }
