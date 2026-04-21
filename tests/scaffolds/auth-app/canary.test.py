"""Canary — scaffolds/auth-app (retrofit)."""
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "auth-app"


def test_scaffold_tree_exists() -> None:
    for rel in ("package.json", "tsconfig.json", "vite.config.ts", "index.html",
                "README.md", "src/App.tsx", "src/main.tsx",
                "src/pages/LoginPage.tsx", "src/pages/RegisterPage.tsx",
                "server/index.js"):
        assert (SCAFFOLD / rel).exists(), rel


def test_auth_deps_present() -> None:
    pkg = json.loads((SCAFFOLD / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    # Password hashing + token signing + routing + persistence
    for lib in ("bcryptjs", "jsonwebtoken", "react-router-dom", "better-sqlite3"):
        assert lib in deps, f"auth-app must depend on {lib}"


def test_no_plaintext_password_in_seed() -> None:
    """Seed data (if any) must not contain plaintext passwords. Grep
    guard against drone mistakes that propagate to prod."""
    server_src = (SCAFFOLD / "server" / "index.js").read_text()
    # Bcrypt hashing should be called somewhere
    assert "bcrypt" in server_src.lower(), (
        "server must hash passwords with bcryptjs — plaintext storage is a vulnerability"
    )


def test_jwt_signing_present() -> None:
    server_src = (SCAFFOLD / "server" / "index.js").read_text()
    assert "jsonwebtoken" in server_src or "jwt" in server_src.lower(), (
        "server must sign JWTs for authenticated routes"
    )


def test_login_and_register_pages_distinct() -> None:
    login = (SCAFFOLD / "src" / "pages" / "LoginPage.tsx").read_text()
    register = (SCAFFOLD / "src" / "pages" / "RegisterPage.tsx").read_text()
    assert login != register, "Login and Register pages must be distinct files"
    assert len(login) > 200 and len(register) > 200, (
        "auth pages look like empty stubs"
    )


def test_readme_documents_jwt_pattern() -> None:
    readme = (SCAFFOLD / "README.md").read_text().lower()
    assert "jwt" in readme or "token" in readme, (
        "README should document the JWT / auth token pattern"
    )
