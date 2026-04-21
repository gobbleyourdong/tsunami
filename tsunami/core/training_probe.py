"""ML training-recipe delivery gate — file-level plausibility.

The training vertical covers fine-tuning / pretraining / eval recipes
shipped as self-contained python projects. Probe is offline — we don't
run training (takes hours, needs a GPU). We check that the deliverable
has the *shape* of a plausible training recipe:

  1. A training entry file exists (train.py / finetune.py / main.py
     conventional, or a package.json/pyproject main pointing at one).
  2. A training framework is imported (torch, transformers, lightning,
     keras, jax, accelerate).
  3. A training-loop marker is present (`trainer.train()`, `.fit(`,
     `for epoch in`, `accelerator.backward`, etc.).
  4. A checkpoint/save hook is wired (`save_pretrained`, `torch.save`,
     `trainer.save_model`, `ModelCheckpoint(`, `.save(`).
  5. A config surface exists — either argparse/hydra/omegaconf in
     train.py, or a config.{yaml,json,toml} / hparams.yaml alongside.

Not caught (out of scope for a delivery gate):
  - Whether training actually converges (needs empirical harness)
  - Dataset availability / correctness (would need the data)
  - GPU compatibility / memory fit

Signals caught:
  - Ships a README that describes training but no train.py exists
  - Pastes a training loop but imports nothing (wrong framework)
  - Trains forever without saving (no checkpoint → all runs lost)
  - No hparams / config → reproducibility impossible
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ._probe_common import result


_FRAMEWORK_IMPORTS = (
    "torch", "transformers", "pytorch_lightning", "lightning",
    "tensorflow", "keras", "jax", "flax", "accelerate",
    "peft", "unsloth", "trl",
)

_LOOP_MARKERS = (
    "trainer.train(", "Trainer(", ".fit(", "accelerator.backward",
    "for epoch in", "for step in", "train_epoch(", "training_step(",
    "optimizer.step(",
)

_SAVE_MARKERS = (
    "save_pretrained(", "torch.save(", "trainer.save_model(",
    "ModelCheckpoint(", ".save_checkpoint(", "accelerator.save",
    "save_model(", "checkpoint_callback",
)

_CONFIG_MARKERS_IN_CODE = (
    "argparse.ArgumentParser", "ArgumentParser(", "@dataclass",
    "hydra.main", "OmegaConf.load", "hydra.compose", "HfArgumentParser",
    "TrainingArguments(", "TrainingConfig(", "pydantic",
)

_CONFIG_FILES = (
    "config.yaml", "config.yml", "config.json", "config.toml",
    "hparams.yaml", "hparams.yml", "conf/config.yaml",
    "configs/default.yaml", "configs/config.yaml",
    "train_config.yaml", "training_config.yaml",
)

_CONVENTIONAL_ENTRIES = (
    "train.py", "finetune.py", "fine_tune.py", "pretrain.py",
    "main.py", "run.py", "run_training.py", "run_finetune.py",
    "src/train.py", "src/finetune.py", "src/main.py",
    "scripts/train.py", "scripts/finetune.py",
)


def _find_entry(project_dir: Path) -> Path | None:
    """Locate the training entry file.

    Priority: pyproject [project.scripts] pointing at a train module,
    then package.json main, then conventional paths.
    """
    # pyproject [project.scripts]: look for a training-named script
    pyproj = project_dir / "pyproject.toml"
    if pyproj.is_file():
        try:
            t = pyproj.read_text(encoding="utf-8", errors="replace")
        except OSError:
            t = ""
        in_scripts = False
        for line in t.splitlines():
            s = line.strip()
            if s.startswith("["):
                in_scripts = s in ("[project.scripts]", "[tool.poetry.scripts]")
                continue
            if not in_scripts:
                continue
            m = re.match(
                r'(train\w*|finetune\w*|pretrain\w*)\s*=\s*["\']([\w.]+):([\w]+)["\']',
                s,
            )
            if m:
                module = m.group(2)
                rel = Path(*module.split(".")).with_suffix(".py")
                for layout in (project_dir / rel, project_dir / "src" / rel):
                    if layout.is_file():
                        return layout

    # package.json main
    pkg_path = project_dir / "package.json"
    if pkg_path.is_file():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            main = pkg.get("main")
            if isinstance(main, str):
                p = project_dir / main
                if p.is_file() and p.suffix == ".py":
                    return p
        except json.JSONDecodeError:
            pass

    # Conventional paths
    for rel in _CONVENTIONAL_ENTRIES:
        p = project_dir / rel
        if p.is_file():
            return p

    return None


def _scan_for_markers(text: str, markers: tuple[str, ...]) -> list[str]:
    hits = [m for m in markers if m in text]
    return hits


def _has_config_surface(project_dir: Path, entry_text: str) -> tuple[bool, str]:
    """Config surface = inline argparse/dataclass/hydra OR a config file.

    Returns (has_surface, evidence_string).
    """
    in_code = _scan_for_markers(entry_text, _CONFIG_MARKERS_IN_CODE)
    if in_code:
        return True, f"in-code: {', '.join(in_code[:3])}"
    for rel in _CONFIG_FILES:
        if (project_dir / rel).is_file():
            return True, f"config file: {rel}"
    # Broader sweep: any *.yaml / *.yml at root that mentions training keys
    for cfg in list(project_dir.glob("*.yaml")) + list(project_dir.glob("*.yml")):
        try:
            txt = cfg.read_text(encoding="utf-8", errors="replace").lower()
            if any(k in txt for k in ("learning_rate", "lr:", "batch_size",
                                      "epochs", "max_steps", "model_name")):
                return True, f"config-shaped yaml: {cfg.name}"
        except OSError:
            continue
    return False, ""


async def training_probe(
    project_dir: Path,
    task_text: str = "",
) -> dict:
    """Static checks: entry + framework + loop + save + config."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return result(False, f"project dir not found: {project_dir}")

    entry = _find_entry(project_dir)
    if entry is None:
        return result(
            False,
            "training: no entry file found. Checked pyproject "
            "[project.scripts] (train*/finetune*/pretrain* names), "
            "package.json main, and conventional paths "
            "(train.py / finetune.py / main.py at root, src/, scripts/).",
        )

    try:
        text = entry.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return result(False, f"training: cannot read entry {entry}: {e}")

    # Framework import
    fw_hits = _scan_for_markers(text, _FRAMEWORK_IMPORTS)
    if not fw_hits:
        # Try import-line matching too (from <fw> import ...)
        import_lines = [ln for ln in text.splitlines()
                        if ln.lstrip().startswith(("import ", "from "))]
        fw_hits = [fw for fw in _FRAMEWORK_IMPORTS
                   if any(fw in ln for ln in import_lines)]
        if not fw_hits:
            return result(
                False,
                f"training: entry {entry.name} imports no training "
                f"framework. Expected one of: {', '.join(_FRAMEWORK_IMPORTS[:8])}…",
            )

    loop_hits = _scan_for_markers(text, _LOOP_MARKERS)
    if not loop_hits:
        return result(
            False,
            f"training: entry {entry.name} has no training-loop "
            "marker (expected one of: trainer.train(, .fit(, "
            "for epoch in, accelerator.backward, optimizer.step(, ...).",
        )

    save_hits = _scan_for_markers(text, _SAVE_MARKERS)
    if not save_hits:
        return result(
            False,
            f"training: entry {entry.name} has a training loop but "
            "no checkpoint/save call. Expected one of: save_pretrained(, "
            "torch.save(, trainer.save_model(, ModelCheckpoint(, ... "
            "— a training run with no save is lost on exit.",
        )

    has_cfg, cfg_evidence = _has_config_surface(project_dir, text)
    if not has_cfg:
        return result(
            False,
            f"training: entry {entry.name} has no config surface — "
            "no argparse/dataclass/hydra in code, no config.{yaml,json,toml} "
            "or hparams.yaml alongside. Reproducibility impossible.",
        )

    rel = entry.relative_to(project_dir) if entry.is_relative_to(project_dir) else entry
    summary = (
        f"entry={rel}\n"
        f"framework={', '.join(fw_hits[:3])}\n"
        f"loop={', '.join(loop_hits[:3])}\n"
        f"save={', '.join(save_hits[:2])}\n"
        f"config={cfg_evidence}"
    )
    return result(True, "", raw=summary)


__all__ = ["training_probe", "_find_entry"]
