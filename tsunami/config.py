"""Configuration for the Tsunami agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TsunamiConfig:
    # --- Model (serve_transformers.py) ---
    model_backend: str = "api"
    model_name: str = "tsunami"
    model_endpoint: str = "http://localhost:8090"
    api_key: str | None = None
    # Qwen3.6-35B-A3B README (Thinking mode — Precise Coding / WebDev):
    #   temperature=0.6, top_p=0.95, top_k=20, min_p=0.0,
    #   presence_penalty=0.0, repetition_penalty=1.0.
    # Native context 262144 (256K). enable_thinking=True (default).
    #
    # max_tokens bounded to 2500 for build-agent turns. At /v1 prefill-
    # inclusive decode rate (~15-20 tok/s on 6K-token prompts), 2500
    # tokens = ~2-2.5 min of generation. Iter 1 with thinking-OFF and
    # a pre-scaffolded project needs ~1500-2000 tok to write a full
    # App.tsx (pomodoro, tic-tac-toe, counter); subsequent iters emit
    # a few hundred. 2500 gives headroom without allowing iter 1 to
    # consume the full T2 budget on one file_write (3784-token write
    # at 15:50 burned 236s of 300s eval budget, timing out at iter 4).
    # Qwen card suggests 81920 for math/coding competitions — not
    # relevant for this build-agent use case.
    temperature: float = 0.6
    top_p: float = 0.95
    top_k: int = 20
    min_p: float = 0.0
    presence_penalty: float = 0.0
    repetition_penalty: float = 1.0
    max_tokens: int = 6144
    client_id: str = ""  # set via TSUNAMI_USER env var; feeds the `user` field of
                         # /v1/chat/completions so the server can enforce per-user
                         # fairness. Leave empty on single-user setups — the server
                         # falls back to a shared "default" queue.
    adapter: str = ""    # set via TSUNAMI_ADAPTER env var; feeds the `adapter` field
                         # of /v1/chat/completions so the server swaps LoRA adapters
                         # per-request. "" = leave server's current adapter; "none" =
                         # force base model. Server serializes swaps via gpu_sem.

    # --- Eddy (fast workers — same endpoint) ---
    eddy_endpoint: str = "http://localhost:8090"

    # --- Watcher (self-evaluation) ---
    watcher_enabled: bool = False
    watcher_model: str = "tsunami"
    watcher_endpoint: str = "http://localhost:8090"

    # --- Paths ---
    workspace_dir: str = "./workspace"
    # Default to the package's bundled skills directory so the agent gets
    # the canonical workflows out-of-the-box. Override via env or arg to
    # point at a user's own skills dir for additive workflows.
    skills_dir: str = str(Path(__file__).parent / "skills")

    # --- Behavior ---
    max_iterations: int = 200
    tool_timeout: int = 0  # 0 = no timeout
    error_escalation_threshold: int = 3
    watcher_interval: int = 5  # check every N iterations

    # --- Search ---
    search_backend: str = "duckduckgo"  # "serpapi", "brave", "duckduckgo"
    search_api_key: str | None = None

    # --- Tools ---
    # Tools load on demand via load_toolbox — no profile needed

    # --- Browser ---
    browser_headless: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> TsunamiConfig:
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_env(cls, base: TsunamiConfig | None = None) -> TsunamiConfig:
        cfg = base or cls()
        env_map = {
            "TSUNAMI_MODEL_BACKEND": "model_backend",
            "TSUNAMI_MODEL_NAME": "model_name",
            "TSUNAMI_MODEL_ENDPOINT": "model_endpoint",
            "TSUNAMI_API_KEY": "api_key",
            "TSUNAMI_USER": "client_id",
            "TSUNAMI_ADAPTER": "adapter",
            "TSUNAMI_WATCHER_ENABLED": "watcher_enabled",
            "TSUNAMI_WATCHER_MODEL": "watcher_model",
            "TSUNAMI_WORKSPACE": "workspace_dir",
            "TSUNAMI_SEARCH_BACKEND": "search_backend",
            "TSUNAMI_SEARCH_API_KEY": "search_api_key",
        }
        for env_key, attr in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                ftype = type(getattr(cfg, attr)) if getattr(cfg, attr) is not None else str
                if ftype is bool:
                    setattr(cfg, attr, val.lower() in ("1", "true", "yes"))
                elif ftype is int:
                    setattr(cfg, attr, int(val))
                elif ftype is float:
                    setattr(cfg, attr, float(val))
                else:
                    setattr(cfg, attr, val)
        return cfg

    @property
    def plans_dir(self) -> Path:
        return Path(self.workspace_dir) / "plans"

    @property
    def notes_dir(self) -> Path:
        return Path(self.workspace_dir) / "notes"

    @property
    def deliverables_dir(self) -> Path:
        return Path(self.workspace_dir) / "deliverables"

    def ensure_dirs(self):
        for d in [self.plans_dir, self.notes_dir, self.deliverables_dir]:
            d.mkdir(parents=True, exist_ok=True)
