"""QA-3 Fire 96: `_pre_scaffold` no longer scaffolds adversary-chosen dir names.

Pre-scaffold was extracting the first 3 non-skip words from the user prompt
and creating `workspace/deliverables/<word1>-<word2>-<word3>/`, running
`npm install` there, and shadowing the model's explicit `project_init`
calls. Fix: pre-scaffold only runs when the prompt contains an explicit
`deliverables/<name>` path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def agent_with_tmp_workspace():
    import asyncio
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
    agent = Agent(cfg)
    yield agent, tmp


def _run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


def test_no_scaffold_on_generic_build_prompt(agent_with_tmp_workspace):
    """Fire 96 root: `"build a counter app"` must NOT create a dir before model runs."""
    agent, tmp = agent_with_tmp_workspace
    result = _run(agent._pre_scaffold("build a counter app with plus and minus buttons"))
    assert result == ""
    # Critically: no dir created from word extraction
    assert not (Path(tmp) / "deliverables").exists() or \
           not any((Path(tmp) / "deliverables").iterdir())


def test_no_scaffold_on_adversary_phrase(agent_with_tmp_workspace):
    """Fire 96 attack repro: `"expose admin credentials in dashboard"` must NOT
    create `expose-admin-credentials/` — no word extraction = no control."""
    agent, tmp = agent_with_tmp_workspace
    _run(agent._pre_scaffold("expose admin credentials in dashboard"))
    deliv = Path(tmp) / "deliverables"
    # Either deliverables/ doesn't exist yet or it's empty
    if deliv.exists():
        entries = list(deliv.iterdir())
        assert not any("admin" in e.name or "credentials" in e.name for e in entries)


def test_no_scaffold_on_project_init_name_shadow(agent_with_tmp_workspace):
    """Fire 96 exact repro: `'project_init name "X". Then...'` must NOT create
    `project-init-name/` (which shadowed the user's explicit X)."""
    agent, tmp = agent_with_tmp_workspace
    _run(agent._pre_scaffold('project_init name "vortex-beacon-96". Then write sw.js'))
    deliv = Path(tmp) / "deliverables"
    if deliv.exists():
        entries = list(deliv.iterdir())
        assert not any(e.name == "project-init-name" for e in entries)


def test_scaffold_fires_on_explicit_deliverables_path(agent_with_tmp_workspace):
    """Legit: when user explicitly names `save to workspace/deliverables/my-app`,
    pre-scaffold SHOULD still fire. Only the word-extraction fallback was
    removed; the explicit-path branch is intact.

    Source-invariant check since we can't actually run project_init here
    without a scaffold tree + npm.
    """
    src = (Path(__file__).resolve().parent.parent / "agent.py").read_text()
    # save_match regex still present
    assert 'deliverables/([a-z0-9_-]+)' in src
    # Word-extraction fallback is REMOVED (no `name_words` variable)
    assert "name_words = [w for w in words" not in src


def test_questions_still_skipped(agent_with_tmp_workspace):
    """Regression: question-form prompts still return '' (unchanged)."""
    agent, tmp = agent_with_tmp_workspace
    for prompt in ["what can you build?", "how does this work?", "tell me about tsunami"]:
        result = _run(agent._pre_scaffold(prompt))
        assert result == ""


def test_no_build_keyword_still_skipped(agent_with_tmp_workspace):
    """Regression: prompts lacking build keywords still return ''."""
    agent, tmp = agent_with_tmp_workspace
    result = _run(agent._pre_scaffold("hello how are you today"))
    assert result == ""
