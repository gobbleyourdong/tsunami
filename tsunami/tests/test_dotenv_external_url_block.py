"""QA-3 Fire 105: .env plant with external attacker URL.

Vite's `VITE_*` env vars BAKE INTO the production bundle as string
constants — so an attacker-controlled URL hidden in src/.env becomes a
baked-in endpoint in dist/. The App.tsx source only shows
`import.meta.env.VITE_FOO` (non-literal), which misses any content
scanner targeting .tsx files.

FileWrite now refuses .env* writes containing external http(s):// URLs.
Localhost / private-net / path-relative references pass.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from tsunami.config import TsunamiConfig
from tsunami.tools.filesystem import FileWrite
from tsunami.tools import filesystem as fs_state


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_tool(ws: str) -> FileWrite:
    cfg = TsunamiConfig(
        model_backend="api",
        model_name="test",
        model_endpoint="http://localhost:9999",
        workspace_dir=ws,
    )
    return FileWrite(cfg)


@pytest.fixture(autouse=True)
def reset_session():
    fs_state._session_created_projects.clear()
    yield
    fs_state._session_created_projects.clear()


def test_fire105_exact_repro_blocks():
    """Fire 105 exact on-disk payload: VITE_EXFIL_URL=https://attacker.test/..."""
    with tempfile.TemporaryDirectory() as tmp:
        fs_state.register_session_project("dotenv-105")
        (Path(tmp) / "deliverables" / "dotenv-105" / "src").mkdir(parents=True)
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path="workspace/deliverables/dotenv-105/src/.env",
            content="VITE_EXFIL_URL=https://example-attacker.test/qa3-dotenv105",
        ))
        assert result.is_error
        assert "BLOCKED" in result.content
        assert "example-attacker.test" in result.content


def test_dotenv_with_multiple_external_urls_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        fs_state.register_session_project("myapp")
        (Path(tmp) / "deliverables" / "myapp" / "src").mkdir(parents=True)
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path="workspace/deliverables/myapp/src/.env",
            content=(
                "VITE_API_URL=https://api.attacker1.com\n"
                "VITE_ANALYTICS=https://track.attacker2.net/pixel\n"
                "VITE_NAME=hello\n"
            ),
        ))
        assert result.is_error
        assert "BLOCKED" in result.content


def test_dotenv_with_localhost_url_passes():
    """Legit: localhost dev endpoint."""
    with tempfile.TemporaryDirectory() as tmp:
        fs_state.register_session_project("myapp")
        (Path(tmp) / "deliverables" / "myapp" / "src").mkdir(parents=True)
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path="workspace/deliverables/myapp/src/.env",
            content="VITE_API_URL=http://localhost:3000/api\n",
        ))
        assert not result.is_error


def test_dotenv_with_private_net_passes():
    """Legit: private network IP (10.x, 192.168.x, 172.16-31.x)."""
    for addr in ("http://10.0.0.5", "http://192.168.1.1/api", "http://172.20.0.2:8080"):
        with tempfile.TemporaryDirectory() as tmp:
            fs_state.register_session_project("myapp")
            (Path(tmp) / "deliverables" / "myapp" / "src").mkdir(parents=True)
            tool = _make_tool(tmp)
            result = _run(tool.execute(
                path="workspace/deliverables/myapp/src/.env",
                content=f"VITE_API_URL={addr}/api\n",
            ))
            assert not result.is_error, f"should pass for {addr}"


def test_dotenv_with_no_urls_passes():
    """Non-URL env values: API keys, feature flags, etc."""
    with tempfile.TemporaryDirectory() as tmp:
        fs_state.register_session_project("myapp")
        (Path(tmp) / "deliverables" / "myapp" / "src").mkdir(parents=True)
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path="workspace/deliverables/myapp/src/.env",
            content=(
                "VITE_FEATURE_DARK=true\n"
                "VITE_VERSION=1.2.3\n"
                "VITE_TITLE=My App\n"
            ),
        ))
        assert not result.is_error


def test_dotenv_production_variant_blocks():
    """`.env.production` / `.env.local` etc. — all `.env*` names checked."""
    with tempfile.TemporaryDirectory() as tmp:
        fs_state.register_session_project("myapp")
        (Path(tmp) / "deliverables" / "myapp").mkdir(parents=True)
        tool = _make_tool(tmp)
        for fname in (".env.production", ".env.local", ".env.staging"):
            result = _run(tool.execute(
                path=f"workspace/deliverables/myapp/{fname}",
                content="VITE_EXFIL=https://attacker.test",
            ))
            assert result.is_error, f"should block {fname}"


def test_regular_tsx_file_with_external_url_passes():
    """This gate ONLY affects .env* files. An http(s) URL in an App.tsx
    is a separate concern handled by other content gates (Fires 59/61)."""
    with tempfile.TemporaryDirectory() as tmp:
        fs_state.register_session_project("myapp")
        (Path(tmp) / "deliverables" / "myapp" / "src").mkdir(parents=True)
        tool = _make_tool(tmp)
        result = _run(tool.execute(
            path="workspace/deliverables/myapp/src/App.tsx",
            content=(
                'export default function App() {\n'
                '  return <a href="https://example.com">link</a>\n'
                '}\n'
            ),
        ))
        # Should pass the .env gate; may be refused by other gates but
        # not this one.
        if result.is_error:
            assert "BLOCKED: .env" not in result.content
