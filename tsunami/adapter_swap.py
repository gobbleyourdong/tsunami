"""LoRA adapter swap helper — pure function, no torch dependency.

Pulled out of serve_transformers.py so tests can import and exercise the
swap logic without loading the full model stack. The caller MUST hold the
gpu_sem (or equivalent single-writer guarantee) while invoking this so
swaps don't race with in-flight generate() calls.
"""

from __future__ import annotations

import logging

log = logging.getLogger("tsunami.adapter_swap")


def _loaded_adapter_names(model) -> set[str]:
    """Best-effort list of adapters PEFT has loaded on the model.

    PEFT's PeftModel exposes `peft_config: dict[name, PeftConfig]`. Older
    / partially-wrapped models may not have it — return empty set then and
    let the caller fall through to the try/except path.
    """
    cfg = getattr(model, "peft_config", None)
    if isinstance(cfg, dict):
        return set(cfg.keys())
    return set()


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
          - "no-change"      — name matches current, nothing done
          - "swapped→X"      — swap succeeded; new_current is X
          - "fallback→none"  — requested adapter not loaded; disabled to base
          - "unsupported"    — model has no adapter methods
          - "error:<msg>"    — swap attempt raised
    """
    if name == current:
        return "no-change", current

    # Graceful fallback when the requested adapter isn't loaded on the model
    # (e.g. router picked chrome-ext-v1 but server's --adapters-dir only had
    # build-v89 and gamedev). Without this, `set_adapter` raises ValueError
    # and the client never learns — request proceeds on the WRONG adapter
    # (whichever was active). Falling to base is predictable and logs clearly.
    if name != "none":
        loaded = _loaded_adapter_names(model)
        if loaded and name not in loaded:
            log.info(
                f"adapter {name!r} not loaded (available: {sorted(loaded)}) — "
                f"falling back to base model"
            )
            if hasattr(model, "disable_adapter_layers"):
                try:
                    model.disable_adapter_layers()
                    return "fallback→none", "none"
                except Exception as e:
                    log.warning(f"disable_adapter_layers after fallback raised: {e}")
                    return f"error:{e}", current
            return "unsupported", current

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
