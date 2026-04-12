"""LoRA adapter swap helper — pure function, no torch dependency.

Pulled out of serve_transformers.py so tests can import and exercise the
swap logic without loading the full model stack. The caller MUST hold the
gpu_sem (or equivalent single-writer guarantee) while invoking this so
swaps don't race with in-flight generate() calls.
"""

from __future__ import annotations

import logging

log = logging.getLogger("tsunami.adapter_swap")


def apply_adapter_swap(model, name: str, current: str | None) -> tuple[str, str | None]:
    """Swap the active LoRA adapter on `model` if it differs from `current`.

    Args:
        model: the transformers / PEFT model object (has set_adapter /
            disable_adapter_layers / load_adapter attrs when it supports
            adapters).
        name: target adapter name. `"none"` disables all adapters (base model);
            any other string selects that adapter.
        current: the currently-active adapter name (None if none loaded).

    Returns:
        (status, new_current) tuple. status is a short log tag:
          - "no-change"  — name matches current, nothing done
          - "swapped→X"  — swap succeeded; new_current is X
          - "unsupported"— model has no adapter methods
          - "error:<msg>"— swap attempt raised
    """
    if name == current:
        return "no-change", current
    try:
        if name == "none":
            if hasattr(model, "disable_adapter_layers"):
                model.disable_adapter_layers()
                return f"swapped→none", "none"
            return "unsupported", current
        if hasattr(model, "set_adapter"):
            model.set_adapter(name)
            return f"swapped→{name}", name
        if hasattr(model, "load_adapter"):
            model.load_adapter(name, adapter_name=name)
            model.set_adapter(name)
            return f"swapped→{name}", name
        return "unsupported", current
    except Exception as e:
        log.warning(f"adapter swap to {name!r} failed: {e}")
        return f"error:{e}", current
