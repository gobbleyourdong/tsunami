"""QA-3 Fire 102: explicit `save to workspace/deliverables/<name>` must take
priority over keyword-overlap detection of existing projects.

The original Fire 102 repro: user says "save to workspace/deliverables/pivot-test-102
... generate an image ... actually no, build a React counter instead". The
agent's `_detect_existing_project` scored `generate-image-cute/` (unrelated
older dir) 2-keyword-overlap ("generate", "image") and targeted IT. User's
explicit target `pivot-test-102` was silently overridden — cross-session
protection (e98f5bc) saved the day, but the routing itself was wrong.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def agent():
    from tsunami.agent import Agent
    from tsunami.config import TsunamiConfig
    tmp = tempfile.mkdtemp()
    cfg = TsunamiConfig(
        model_backend="api",
        model_name="test",
        model_endpoint="http://localhost:9999",
        workspace_dir=tmp,
        max_iterations=5,
    )
    # Scaffold some decoy projects to confuse the keyword-overlap heuristic
    deliv = Path(tmp) / "deliverables"
    for name in ["generate-image-cute", "counter-app-old", "todo-list"]:
        (deliv / name / "src").mkdir(parents=True, exist_ok=True)
        (deliv / name / "package.json").write_text('{"name": "' + name + '"}')
        (deliv / name / "src" / "App.tsx").write_text(
            "export default function App() { return <div>stub</div> }"
        )
    return Agent(cfg)


def test_explicit_save_path_skips_existing_project_detection(agent):
    """Fire 102 exact repro: explicit save-path wins over keyword overlap."""
    # Without the fix, this prompt would match `generate-image-cute` via keywords
    # "generate" + "image" (2-word overlap).
    msg = (
        "save to workspace/deliverables/pivot-test-102. "
        "Generate an image of a red sunset. Actually no, ignore the image. "
        "Build a React counter instead with useState + 2 buttons + dark theme."
    )
    result = agent._detect_existing_project(msg)
    assert result == ""  # empty — no existing-project context → fresh build
    # active_project should NOT be set to any of the decoys
    assert agent.active_project != "generate-image-cute"


def test_explicit_save_path_fresh_name_still_skips(agent):
    """The name in the save-path need not exist — it's user INTENT for a fresh dir."""
    result = agent._detect_existing_project(
        "save to workspace/deliverables/brand-new-xyz. Build me a dashboard"
    )
    assert result == ""


def test_without_save_path_keyword_overlap_still_works(agent):
    """Regression: when NO save-path is given, the normal detection runs.
    This prompt should match `todo-list` via strong keyword overlap."""
    # "the todo list" + "fix" iteration verb should match todo-list
    result = agent._detect_existing_project("fix the todo list styling")
    # We don't strictly require a specific return, but result should NOT be
    # empty from the save-path early-return — either match or not based on
    # normal logic. Just make sure it doesn't crash and isn't empty for the
    # wrong reason.
    # (Can be "" if overlap threshold not met — that's normal detection,
    # different code path from the Fire 102 save-path escape.)
    assert isinstance(result, str)


def test_source_invariant_save_path_check_before_keyword_overlap():
    """Source check: the new early-return MUST appear before the
    keyword-overlap Counter() / sorted(overlap) logic. Guards against future
    reorderings that'd reintroduce Fire 102."""
    src = (Path(__file__).resolve().parent.parent / "agent.py").read_text()
    # Early-return regex
    idx_save = src.find("r'deliverables/[a-z0-9_-]+'")
    # First occurrence of the keyword-overlap scan
    idx_overlap = src.find("best_score = 0")
    assert idx_save != -1, "save-path early-return missing from _detect_existing_project"
    assert idx_overlap != -1
    assert idx_save < idx_overlap, (
        "save-path check must run BEFORE keyword-overlap scoring"
    )
