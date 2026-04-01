"""Project Init — create a blank Vite + React + TypeScript project.

This is `npm create vite` as a tool. Writes ONLY infrastructure:
package.json, index.html, vite.config, tsconfig, main.tsx.
The wave writes everything in src/. No template components.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.tools.project_init")


class ProjectInit(BaseTool):
    name = "project_init"
    description = (
        "Create a blank Vite + React + TypeScript project. "
        "Writes package.json, index.html, vite.config.ts, tsconfig.json, src/main.tsx. "
        "Runs npm install. You write everything in src/ after this. "
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
                    "description": "Extra npm packages to install (e.g. ['xlsx', 'three', 'cannon-es'])",
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
            project_dir.mkdir(parents=True, exist_ok=True)
            src = project_dir / "src"
            src.mkdir(exist_ok=True)
            (src / "components").mkdir(exist_ok=True)

            # package.json
            deps = {"react": "^19.0.0", "react-dom": "^19.0.0"}
            for dep in dependencies:
                deps[dep] = "latest"

            (project_dir / "package.json").write_text(json.dumps({
                "name": name,
                "private": True,
                "type": "module",
                "scripts": {"dev": "vite", "build": "vite build"},
                "dependencies": deps,
                "devDependencies": {
                    "@types/react": "^19.0.0",
                    "@types/react-dom": "^19.0.0",
                    "@vitejs/plugin-react": "^4.3.0",
                    "typescript": "~5.7.0",
                    "vite": "^6.0.0",
                }
            }, indent=2))

            # index.html
            (project_dir / "index.html").write_text(
                f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                f'  <meta charset="UTF-8"/>\n'
                f'  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>\n'
                f'  <title>{name}</title>\n'
                f'</head>\n<body>\n'
                f'  <div id="root"></div>\n'
                f'  <script type="module" src="/src/main.tsx"></script>\n'
                f'</body>\n</html>\n'
            )

            # vite.config.ts
            (project_dir / "vite.config.ts").write_text(
                'import { defineConfig } from "vite"\n'
                'import react from "@vitejs/plugin-react"\n'
                'export default defineConfig({ plugins: [react()] })\n'
            )

            # tsconfig.json — relaxed for LLM-generated code
            (project_dir / "tsconfig.json").write_text(json.dumps({
                "compilerOptions": {
                    "target": "ES2020", "module": "ESNext",
                    "lib": ["ES2020", "DOM", "DOM.Iterable"],
                    "jsx": "react-jsx", "moduleResolution": "bundler",
                    "strict": False, "noEmit": True,
                    "isolatedModules": True, "esModuleInterop": True,
                    "skipLibCheck": True, "allowImportingTsExtensions": True,
                    "noUnusedLocals": False, "noUnusedParameters": False,
                },
                "include": ["src"]
            }, indent=2))

            # main.tsx — minimal entry point
            (src / "main.tsx").write_text(
                'import { createRoot } from "react-dom/client"\n'
                'import App from "./App"\n'
                'createRoot(document.getElementById("root")!).render(<App />)\n'
            )

            # Stub App.tsx — wave MUST replace this
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

            # Start Vite dev server
            try:
                from ..serve import serve_project
                url = serve_project(str(project_dir))
                log.info(f"Dev server: {url}")
            except Exception:
                url = ""

            dep_list = ", ".join(dependencies) if dependencies else "none"
            return ToolResult(
                f"Project '{name}' ready at {project_dir}\n"
                f"Dependencies: react, react-dom, {dep_list}\n"
                f"Dev server: {url or 'run npx vite --port 9876'}\n\n"
                f"Write your components in src/. App.tsx is a stub — replace it.\n"
                f"After writing all files: shell_exec 'cd {project_dir} && npx vite build'"
            )

        except Exception as e:
            return ToolResult(f"Project init failed: {e}", is_error=True)
