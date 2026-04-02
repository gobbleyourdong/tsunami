"""Project Init — provision from scaffold library.

Like Manus's webdev_init_project: analyzes what the project REQUIRES,
picks the right scaffold, copies it, installs deps, starts dev server.
The model writes domain logic into src/.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.tools.project_init")

# Scaffold directory — the CDN
SCAFFOLDS_DIR = Path(__file__).parent.parent.parent / "scaffolds"


def _pick_scaffold(name: str, dependencies: list[str]) -> str:
    """Pick scaffold by analyzing what the project REQUIRES.

    Requirement analysis, not keyword matching:
    1. Platform (3D, 2D, mobile, web)
    2. Persistence (database, save state)
    3. File handling (uploads, spreadsheets)
    4. Data visualization (charts, dashboards)
    5. Presentation (landing, portfolio)
    6. Default to minimal
    """
    deps_lower = {d.lower() for d in dependencies}
    all_text = name.lower() + " " + " ".join(deps_lower)

    def needs(*keywords):
        return any(k in all_text for k in keywords)

    # 1. 3D game/simulation
    if needs("three", "3d", "pinball", "fps", "voxel", "r3f", "rapier", "cannon"):
        if (SCAFFOLDS_DIR / "threejs-game").exists():
            return "threejs-game"

    # 2. 2D game
    if needs("pixi", "2d", "sprite", "platformer", "arcade", "tetris", "snake", "pong", "matter"):
        if (SCAFFOLDS_DIR / "pixijs-game").exists():
            return "pixijs-game"

    # 3. Any game (default to 2D)
    if needs("game"):
        if (SCAFFOLDS_DIR / "pixijs-game").exists():
            return "pixijs-game"

    # 4. Needs persistence (database, accounts, saving state)
    if needs("database", "login", "auth", "account", "persist", "save", "crud",
             "backend", "api", "server", "express", "sqlite", "todo", "saas",
             "track", "log", "history", "bookmark", "favorite"):
        if (SCAFFOLDS_DIR / "fullstack").exists():
            return "fullstack"

    # 5. Needs file handling (uploads, spreadsheets)
    if needs("upload", "file", "xlsx", "csv", "excel", "spreadsheet", "import",
             "export", "pdf", "document", "parse", "diff", "sheet"):
        if (SCAFFOLDS_DIR / "form-app").exists():
            return "form-app"

    # 6. Needs data visualization (charts, metrics)
    if needs("chart", "dashboard", "analytics", "metrics", "stats", "graph",
             "monitor", "visualiz", "report", "recharts", "d3"):
        if (SCAFFOLDS_DIR / "dashboard").exists():
            return "dashboard"

    # 7. Presentation (landing, portfolio)
    if needs("landing", "portfolio", "marketing", "homepage", "website",
             "showcase", "brochure", "about"):
        if (SCAFFOLDS_DIR / "landing").exists():
            return "landing"

    # 8. Default: minimal React app
    if (SCAFFOLDS_DIR / "react-app").exists():
        return "react-app"

    return ""


class ProjectInit(BaseTool):
    name = "project_init"
    description = (
        "Create a project from the scaffold library. "
        "Analyzes what the project needs (3D, database, file uploads, charts, etc.) "
        "and picks the right template. Installs deps, starts dev server. "
        "You write everything in src/ after this. "
        "Pass extra npm packages in 'dependencies' (e.g. ['xlsx', 'three'])."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name (lowercase, no spaces). Created in workspace/deliverables/",
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra npm packages to install (e.g. ['xlsx', 'three'])",
                    "default": [],
                },
            },
            "required": ["name"],
        }

    async def execute(self, name: str, dependencies: list = None, **kw) -> ToolResult:
        dependencies = dependencies or []

        ws = Path(self.config.workspace_dir)
        project_dir = ws / "deliverables" / name

        if (project_dir / "package.json").exists():
            return ToolResult(
                f"Project '{name}' exists at {project_dir}. "
                f"Write your components in {project_dir}/src/"
            )

        try:
            scaffold_name = _pick_scaffold(name, dependencies)

            if scaffold_name:
                scaffold_dir = SCAFFOLDS_DIR / scaffold_name
                shutil.copytree(
                    scaffold_dir, project_dir,
                    ignore=shutil.ignore_patterns(
                        "node_modules", "dist", ".vite", "package-lock.json"
                    ),
                )
                log.info(f"Copied scaffold '{scaffold_name}' → {project_dir}")

                if dependencies:
                    pkg_path = project_dir / "package.json"
                    pkg = json.loads(pkg_path.read_text())
                    for dep in dependencies:
                        pkg["dependencies"][dep] = "latest"
                    pkg["name"] = name
                    pkg_path.write_text(json.dumps(pkg, indent=2))

                app_tsx = project_dir / "src" / "App.tsx"
                if app_tsx.exists():
                    app_tsx.write_text(
                        '// TODO: Replace with your app\n'
                        'export default function App() {\n'
                        '  return <div>Loading...</div>\n'
                        '}\n'
                    )
            else:
                project_dir.mkdir(parents=True, exist_ok=True)
                src = project_dir / "src"
                src.mkdir(exist_ok=True)
                (src / "components").mkdir(exist_ok=True)

                deps = {"react": "^19.0.0", "react-dom": "^19.0.0"}
                for dep in dependencies:
                    deps[dep] = "latest"

                (project_dir / "package.json").write_text(json.dumps({
                    "name": name, "private": True, "type": "module",
                    "scripts": {"dev": "vite", "build": "vite build"},
                    "dependencies": deps,
                    "devDependencies": {
                        "@types/react": "^19.0.0", "@types/react-dom": "^19.0.0",
                        "@vitejs/plugin-react": "^4.3.0",
                        "typescript": "~5.7.0", "vite": "^6.0.0",
                    }
                }, indent=2))

                for fname, content in [
                    ("index.html", f'<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8"/>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>\n  <title>{name}</title>\n  <style>* {{ margin:0; padding:0; box-sizing:border-box; }}</style>\n</head>\n<body>\n  <div id="root"></div>\n  <script type="module" src="/src/main.tsx"></script>\n</body>\n</html>\n'),
                    ("vite.config.ts", 'import { defineConfig } from "vite"\nimport react from "@vitejs/plugin-react"\nexport default defineConfig({ plugins: [react()] })\n'),
                    ("tsconfig.json", json.dumps({"compilerOptions": {"target": "ES2020", "module": "ESNext", "lib": ["ES2020", "DOM", "DOM.Iterable"], "jsx": "react-jsx", "moduleResolution": "bundler", "strict": False, "noEmit": True, "isolatedModules": True, "esModuleInterop": True, "skipLibCheck": True, "allowImportingTsExtensions": True}, "include": ["src"]}, indent=2)),
                ]:
                    (project_dir / fname).write_text(content)

                (src / "main.tsx").write_text('import { createRoot } from "react-dom/client"\nimport App from "./App"\ncreateRoot(document.getElementById("root")!).render(<App />)\n')
                (src / "App.tsx").write_text('export default function App() {\n  return <div>Loading...</div>\n}\n')

            result = subprocess.run(["npm", "install"], cwd=str(project_dir), capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return ToolResult(f"Project created but npm install failed: {result.stderr[:300]}", is_error=True)

            try:
                from ..serve import serve_project
                url = serve_project(str(project_dir))
            except Exception:
                url = ""

            scaffold_info = f" (scaffold: {scaffold_name})" if scaffold_name else ""
            dep_list = ", ".join(dependencies) if dependencies else "none"
            return ToolResult(
                f"Project '{name}' ready{scaffold_info} at {project_dir}\n"
                f"Extra deps: {dep_list}\n"
                f"Dev server: {url or 'run npx vite --port 9876'}\n\n"
                f"src/App.tsx is a stub — replace it with your app.\n"
                f"Write components in src/components/.\n"
                f"After all files: shell_exec 'cd {project_dir} && npx vite build'"
            )

        except Exception as e:
            return ToolResult(f"Project init failed: {e}", is_error=True)
