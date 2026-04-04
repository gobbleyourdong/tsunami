"""Formatter — output training data in standard formats.

Supports:
1. ShareGPT format (for axolotl/unsloth SFT)
2. ToolBench format (for tool-use SFT)
3. DPO pairs format (for preference optimization)
4. Train/val/test splits
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict
from pathlib import Path

from .pair_generator import BuilderPair, OrchestratorPair, DPOPair

log = logging.getLogger("tsunami.training.formatter")


def to_sharegpt_builder(pair: BuilderPair) -> dict:
    """Convert a builder pair to ShareGPT format.

    ShareGPT: [{from: "human", value: ...}, {from: "gpt", value: ...}]
    """
    human_msg = pair.instruction
    if pair.context:
        human_msg += f"\n\nContext:\n{pair.context}"

    return {
        "conversations": [
            {"from": "human", "value": human_msg},
            {"from": "gpt", "value": pair.output},
        ],
        "metadata": pair.metadata,
    }


def to_sharegpt_orchestrator(pair: OrchestratorPair) -> dict:
    """Convert an orchestrator pair to ShareGPT format.

    The "gpt" response is the plan + tool sequence as structured text.
    """
    human_msg = f"User request: {pair.user_prompt}\n\n{pair.context}"

    gpt_msg = ""
    if pair.plan:
        gpt_msg += f"Plan:\n{pair.plan}\n\n"
    gpt_msg += "Execution:\n"
    for step in pair.tool_sequence:
        name = step.get("name", "")
        error = " [ERROR]" if step.get("error") else ""
        args = {k: v for k, v in step.items() if k not in ("name", "error")}
        gpt_msg += f"  → {name}({json.dumps(args)}){error}\n"

    return {
        "conversations": [
            {"from": "human", "value": human_msg},
            {"from": "gpt", "value": gpt_msg},
        ],
        "metadata": pair.metadata,
    }


def to_toolbench(pair: OrchestratorPair) -> dict:
    """Convert an orchestrator pair to ToolBench format.

    ToolBench: {query, tool_calls: [{name, arguments}], ...}
    """
    return {
        "query": pair.user_prompt,
        "tool_calls": pair.tool_sequence,
        "plan": pair.plan,
        "metadata": pair.metadata,
    }


def to_dpo(pair: DPOPair) -> dict:
    """Convert a DPO pair to the standard format.

    {prompt, chosen, rejected}
    """
    return {
        "prompt": pair.prompt,
        "chosen": pair.chosen,
        "rejected": pair.rejected,
        "metadata": pair.metadata,
    }


def write_dataset(
    data: list[dict],
    output_dir: Path,
    name: str,
    train_ratio: float = 0.9,
    val_ratio: float = 0.05,
    seed: int = 42,
) -> dict:
    """Write a dataset with train/val/test splits.

    Returns stats about the written dataset.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Shuffle
    random.seed(seed)
    shuffled = data.copy()
    random.shuffle(shuffled)

    # Split
    n = len(shuffled)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    splits = {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }

    stats = {"total": n}
    for split_name, split_data in splits.items():
        if not split_data:
            continue
        path = output_dir / f"{name}_{split_name}.jsonl"
        with open(path, "w") as f:
            for item in split_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        stats[split_name] = len(split_data)
        log.info(f"Wrote {len(split_data)} examples to {path}")

    return stats


def generate_full_dataset(
    builder_pairs: list[BuilderPair],
    orchestrator_pairs: list[OrchestratorPair],
    dpo_pairs: list[DPOPair],
    output_dir: Path,
) -> dict:
    """Generate all dataset files from filtered pairs.

    Creates:
    - builder_sharegpt_{train,val,test}.jsonl (for 2B SFT)
    - orchestrator_sharegpt_{train,val,test}.jsonl (for 9B SFT)
    - orchestrator_toolbench_{train,val,test}.jsonl (for 9B tool-use)
    - dpo_{train,val,test}.jsonl (for preference optimization)
    """
    results = {}

    # Builder pairs → ShareGPT
    if builder_pairs:
        builder_data = [to_sharegpt_builder(p) for p in builder_pairs]
        results["builder_sharegpt"] = write_dataset(
            builder_data, output_dir, "builder_sharegpt"
        )

    # Orchestrator pairs → ShareGPT + ToolBench
    if orchestrator_pairs:
        orch_sharegpt = [to_sharegpt_orchestrator(p) for p in orchestrator_pairs]
        results["orchestrator_sharegpt"] = write_dataset(
            orch_sharegpt, output_dir, "orchestrator_sharegpt"
        )

        orch_toolbench = [to_toolbench(p) for p in orchestrator_pairs]
        results["orchestrator_toolbench"] = write_dataset(
            orch_toolbench, output_dir, "orchestrator_toolbench"
        )

    # DPO pairs
    if dpo_pairs:
        dpo_data = [to_dpo(p) for p in dpo_pairs]
        results["dpo"] = write_dataset(dpo_data, output_dir, "dpo")

    # Summary
    total = sum(r.get("total", 0) for r in results.values())
    log.info(f"Generated {total} total examples across {len(results)} datasets")

    return results
