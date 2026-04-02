"""Project Init — provision from scaffold library.

Like Manus's webdev_init_project: picks the right scaffold
based on what the project needs, copies it, installs deps,
starts dev server. The model writes domain logic into src/.
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
    """Pick the best scaffold based on project name and dependencies."""
    deps_lower = {d.lower() for d in dependencies}
    name_lower = name.lower()

    # 3D game keywords → threejs-game scaffold
    game_3d = {"three", "cannon", "rapier", "3d", "r3f"}
    if deps_lower & game_3d or any(k in name_lower for k in ["3d", "pinball", "fps", "voxel"]):
        if (SCAFFOLDS_DIR / "threejs-game").exists():
            return "threejs-game"

    # 2D game keywords → pixijs-game scaffold
    game_2d = {"pixi", "pixijs", "matter", "2d", "sprite", "platformer"}
    if deps_lower & game_2d or any(k in name_lower for k in ["2d", "platformer", "arcade", "shooter", "tetris", "snake", "pong"]):
        if (SCAFFOLDS_DIR / "pixijs-game").exists():
            return "pixijs-game"

    # Generic game → 2D by default (simpler)
    if any(k in name_lower for k in ["game"]):
        if (SCAFFOLDS_DIR / "pixijs-game").exists():
            return "pixijs-game"

    # Fullstack/API/database keywords → fullstack scaffold
    fullstack_keywords = {"express", "sqlite", "database", "api", "backend", "server", "crud"}
    if deps_lower & fullstack_keywords or any(k in name_lower for k in ["fullstack", "api", "backend", "crud", "todo-app"]):
        if (SCAFFOLDS_DIR / "fullstack").exists():
            return "fullstack"

    # Dashboard/analytics keywords → dashboard scaffold
    dash_keywords = {"chart", "dashboard", "analytics", "stats", "metrics", "recharts", "d3"}
    if deps_lower & dash_keywords or any(k in name_lower for k in ["dash", "analytics", "tracker", "monitor"]):
        if (SCAFFOLDS_DIR / "dashboard").exists():
            return "dashboard"

    # Landing/marketing keywords → landing scaffold
    landing_keywords = {"landing", "marketing", "homepage", "website", "portfolio"}
    if any(k in name_lower for k in landing_keywords):
        if (SCAFFOLDS_DIR / "landing").exists():
            return "landing"

    # File/form/upload keywords → form-app scaffold (xlsx, csv, editable table)
    form_keywords = {"xlsx", "csv", "upload", "file", "form", "spreadsheet", "excel", "papaparse"}
    if deps_lower & form_keywords or any(k in name_lower for k in ["excel", "upload", "form", "csv", "diff", "sheet"]):
        if (SCAFFOLDS_DIR / "form-app").exists():
            return "form-app"

    # Default → react-app
    if (SCAFFOLDS_DIR / "react-app").exists():
        return "react-app"

    return ""  # no scaffold found, generate from scratch


class ProjectInit(BaseTool):
    name = "project_init"
    description = (
        "Create a project from the scaffold library. "
        "Picks the right template (react-app, threejs-game, etc.) "
        "based on project name and dependencies. Installs deps, starts dev server. "
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
            # Pick scaffold
            scaffold_name = _pick_scaffold(name, dependencies)

            if scaffold_name:
                scaffold_dir = SCAFFOLDS_DIR / scaffold_name
                # Copy scaffold (skip node_modules and dist)
                shutil.copytree(
                    scaffold_dir, project_dir,
                    ignore=shutil.ignore_patterns(
                        "node_modules", "dist", ".vite", "package-lock.json"
                    ),
                )
                log.info(f"Copied scaffold '{scaffold_name}' → {project_dir}")

                # Add extra dependencies to package.json
                if dependencies:
                    pkg_path = project_dir / "package.json"
                    pkg = json.loads(pkg_path.read_text())
                    for dep in dependencies:
                        pkg["dependencies"][dep] = "latest"
                    pkg["name"] = name
                    pkg_path.write_text(json.dumps(pkg, indent=2))

                # Reset App.tsx to stub
                app_tsx = project_dir / "src" / "App.tsx"
                if app_tsx.exists():
                    app_tsx.write_text(
                        '// TODO: Replace with your app\n'
                        'export default function App() {\n'
                        '  return <div>Loading...</div>\n'
                        '}\n'
                    )
            else:
                # Fallback: generate minimal project
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

                (project_dir / "index.html").write_text(
                    f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                    f'  <meta charset="UTF-8"/>\n'
                    f'  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>\n'
                    f'  <title>{name}</title>\n'
                    f'  <style>* {{ margin:0; padding:0; box-sizing:border-box; }}</style>\n'
                    f'</head>\n<body>\n'
                    f'  <div id="root"></div>\n'
                    f'  <script type="module" src="/src/main.tsx"></script>\n'
                    f'</body>\n</html>\n'
                )

                (project_dir / "vite.config.ts").write_text(
                    'import { defineConfig } from "vite"\n'
                    'import react from "@vitejs/plugin-react"\n'
                    'export default defineConfig({ plugins: [react()] })\n'
                )

                (project_dir / "tsconfig.json").write_text(json.dumps({
                    "compilerOptions": {
                        "target": "ES2020", "module": "ESNext",
                        "lib": ["ES2020", "DOM", "DOM.Iterable"],
                        "jsx": "react-jsx", "moduleResolution": "bundler",
                        "strict": False, "noEmit": True,
                        "isolatedModules": True, "esModuleInterop": True,
                        "skipLibCheck": True, "allowImportingTsExtensions": True,
                    },
                    "include": ["src"]
                }, indent=2))

                (src / "main.tsx").write_text(
                    'import { createRoot } from "react-dom/client"\n'
                    'import App from "./App"\n'
                    'createRoot(document.getElementById("root")!).render(<App />)\n'
                )

                (src / "App.tsx").write_text(
                    'export default function App() {\n'
                    '  return <div>Loading...</div>\n'
                    '}\n'
                )

            # npm install
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return ToolResult(
                    f"Project created but npm install failed: {result.stderr[:300]}",
                    is_error=True,
                )

            # Start dev server
            try:
                from ..serve import serve_project
                url = serve_project(str(project_dir))
            except Exception:
                url = ""

            scaffold_info = f" (from '{scaffold_name}' scaffold)" if scaffold_name else ""
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
