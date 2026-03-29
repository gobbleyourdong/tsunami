"""Web development tools — scaffold, screenshot, serve.

These tools give the agent a real web development workflow:
scaffold a project, run it, see it, fix it.
"""

from __future__ import annotations

import asyncio
import subprocess
import shutil
from pathlib import Path

from .base import BaseTool, ToolResult


class WebdevScaffold(BaseTool):
    name = "webdev_scaffold"
    description = (
        "Initialize a new web project with Vite + React + TypeScript + Tailwind CSS. "
        "Creates a complete development environment in one call. "
        "Use this FIRST when building any website or web app."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Name for the project directory (lowercase, no spaces)",
                },
                "template": {
                    "type": "string",
                    "enum": ["landing", "app", "dashboard"],
                    "description": "Project type: landing (marketing page), app (full SPA), dashboard (data display)",
                    "default": "landing",
                },
            },
            "required": ["project_name"],
        }

    async def execute(self, project_name: str, template: str = "landing", **kw) -> ToolResult:
        try:
            ws = Path(self.config.workspace_dir)
            project_dir = ws / "deliverables" / project_name
            if project_dir.exists():
                return ToolResult(f"Project {project_name} already exists at {project_dir}")

            project_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Create Vite + React + TypeScript project
            result = subprocess.run(
                ["npm", "create", "vite@latest", ".", "--", "--template", "react-ts"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=60,
                env={**__import__("os").environ, "npm_config_yes": "true"},
            )
            if result.returncode != 0:
                # Fallback: manual scaffold
                return await self._manual_scaffold(project_dir, project_name, template)

            # Step 2: Install dependencies + Tailwind
            subprocess.run(
                ["npm", "install"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=120,
            )

            subprocess.run(
                ["npm", "install", "-D", "tailwindcss", "@tailwindcss/vite"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=60,
            )

            # Step 3: Configure Tailwind in vite.config.ts
            vite_config = project_dir / "vite.config.ts"
            vite_config.write_text('''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, host: true }
})
''')

            # Step 4: Set up Tailwind CSS entry
            css_file = project_dir / "src" / "index.css"
            css_file.write_text('@import "tailwindcss";\n')

            # Step 5: Copy animation assets
            templates_dir = Path("skills/web-builder/templates")
            if templates_dir.exists():
                assets_dir = project_dir / "public"
                assets_dir.mkdir(exist_ok=True)
                for f in ["animations.js"]:
                    src = templates_dir / f
                    if src.exists():
                        shutil.copy2(src, assets_dir / f)

            # Step 6: Create tsunami.md
            tmd = project_dir / "tsunami.md"
            tmd.write_text(
                f"# {project_name}\n\n"
                f"Vite + React + TypeScript + Tailwind CSS project.\n"
                f"Type: {template}\n\n"
                f"## Development\n"
                f"- `npm run dev` to start dev server on port 5173\n"
                f"- Edit src/App.tsx for main component\n"
                f"- Tailwind classes available everywhere\n"
                f"- Public assets in public/\n"
            )

            # Step 7: Clean up default files
            default_css = project_dir / "src" / "App.css"
            if default_css.exists():
                default_css.write_text("")

            file_count = len(list(project_dir.rglob("*")))
            return ToolResult(
                f"Scaffolded {project_name} at {project_dir}\n"
                f"Stack: Vite + React + TypeScript + Tailwind CSS\n"
                f"Template: {template}\n"
                f"Files: {file_count}\n"
                f"Next: edit src/App.tsx, then use webdev_serve to start the dev server."
            )

        except Exception as e:
            return ToolResult(f"Scaffold error: {e}", is_error=True)

    async def _manual_scaffold(self, project_dir: Path, name: str, template: str) -> ToolResult:
        """Fallback: create a minimal Vite project manually."""
        (project_dir / "src").mkdir(exist_ok=True)
        (project_dir / "public").mkdir(exist_ok=True)

        # package.json
        (project_dir / "package.json").write_text(f'''{{"name":"{name}","private":true,"version":"0.0.0","type":"module","scripts":{{"dev":"vite","build":"vite build","preview":"vite preview"}},"dependencies":{{"react":"^19.0.0","react-dom":"^19.0.0"}},"devDependencies":{{"@types/react":"^19.0.0","@types/react-dom":"^19.0.0","@vitejs/plugin-react":"^4.5.0","tailwindcss":"^4.0.0","@tailwindcss/vite":"^4.0.0","typescript":"~5.8.0","vite":"^6.3.0"}}}}''')

        # vite.config.ts
        (project_dir / "vite.config.ts").write_text('''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, host: true }
})
''')

        # tsconfig
        (project_dir / "tsconfig.json").write_text('{"compilerOptions":{"target":"ES2020","useDefineForClassFields":true,"lib":["ES2020","DOM","DOM.Iterable"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"isolatedModules":true,"moduleDetection":"force","noEmit":true,"jsx":"react-jsx","strict":true,"noUnusedLocals":true,"noUnusedParameters":true,"noFallthroughCasesInSwitch":true},"include":["src"]}')

        # index.html
        (project_dir / "index.html").write_text(f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name}</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
''')

        # main.tsx
        (project_dir / "src" / "main.tsx").write_text('''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
''')

        # index.css
        (project_dir / "src" / "index.css").write_text('@import "tailwindcss";\n')

        # App.tsx placeholder
        (project_dir / "src" / "App.tsx").write_text('''export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <h1 className="text-4xl font-bold text-center pt-20">Hello from TSUNAMI</h1>
      <p className="text-gray-400 text-center mt-4">Edit src/App.tsx to get started</p>
    </div>
  )
}
''')

        # tsunami.md
        (project_dir / "tsunami.md").write_text(
            f"# {name}\n\nVite + React + TypeScript + Tailwind CSS project.\n"
            f"Run `npm install` then `npm run dev` to start.\n"
        )

        # Install deps
        subprocess.run(["npm", "install"], cwd=str(project_dir),
                       capture_output=True, text=True, timeout=120)

        return ToolResult(
            f"Scaffolded {name} (manual fallback) at {project_dir}\n"
            f"Stack: Vite + React + TypeScript + Tailwind CSS\n"
            f"Run: npm install && npm run dev"
        )


class WebdevServe(BaseTool):
    name = "webdev_serve"
    description = (
        "Start the dev server for the current web project. "
        "Returns the URL where the site is running."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Project directory name",
                },
                "port": {
                    "type": "integer",
                    "description": "Port to serve on",
                    "default": 5173,
                },
            },
            "required": ["project_name"],
        }

    async def execute(self, project_name: str, port: int = 5173, **kw) -> ToolResult:
        try:
            ws = Path(self.config.workspace_dir)
            project_dir = ws / "deliverables" / project_name

            if not project_dir.exists():
                return ToolResult(f"Project not found: {project_dir}", is_error=True)

            # Check if package.json exists (React project)
            if (project_dir / "package.json").exists():
                # Kill any existing dev server on this port
                subprocess.run(["fuser", "-k", f"{port}/tcp"],
                              capture_output=True, timeout=5)
                await asyncio.sleep(1)

                # Start vite dev server in background
                proc = subprocess.Popen(
                    ["npm", "run", "dev", "--", "--port", str(port)],
                    cwd=str(project_dir),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                await asyncio.sleep(3)  # Wait for server to start

                return ToolResult(
                    f"Dev server running at http://localhost:{port}\n"
                    f"PID: {proc.pid}\n"
                    f"Use webdev_screenshot to see the page."
                )
            else:
                # Static HTML project — use python http.server
                subprocess.run(["fuser", "-k", f"{port}/tcp"],
                              capture_output=True, timeout=5)
                await asyncio.sleep(1)

                proc = subprocess.Popen(
                    ["python3", "-m", "http.server", str(port)],
                    cwd=str(project_dir),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                await asyncio.sleep(1)

                return ToolResult(
                    f"Static server running at http://localhost:{port}\n"
                    f"PID: {proc.pid}"
                )

        except Exception as e:
            return ToolResult(f"Serve error: {e}", is_error=True)


class WebdevScreenshot(BaseTool):
    name = "webdev_screenshot"
    description = (
        "Take a screenshot of a running web page using headless Chrome. "
        "Returns the screenshot file path. Use this to SEE what the site "
        "looks like and identify visual issues to fix."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to screenshot (e.g., http://localhost:5173)",
                    "default": "http://localhost:5173",
                },
                "output_path": {
                    "type": "string",
                    "description": "Where to save the screenshot",
                    "default": "screenshot.png",
                },
                "full_page": {
                    "type": "boolean",
                    "description": "Capture full scrollable page (true) or just viewport (false)",
                    "default": True,
                },
                "width": {
                    "type": "integer",
                    "description": "Viewport width in pixels",
                    "default": 1440,
                },
                "height": {
                    "type": "integer",
                    "description": "Viewport height in pixels",
                    "default": 900,
                },
            },
            "required": [],
        }

    async def execute(self, url: str = "http://localhost:5173",
                      output_path: str = "screenshot.png",
                      full_page: bool = True,
                      width: int = 1440, height: int = 900, **kw) -> ToolResult:
        try:
            from playwright.async_api import async_playwright

            # Resolve output path
            ws = Path(self.config.workspace_dir)
            out = Path(output_path)
            if not out.is_absolute():
                out = ws / out
            out.parent.mkdir(parents=True, exist_ok=True)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": width, "height": height})

                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                except Exception:
                    # Retry with shorter timeout
                    await page.goto(url, wait_until="load", timeout=10000)

                await page.wait_for_timeout(1000)  # Let animations settle

                await page.screenshot(path=str(out), full_page=full_page)
                await browser.close()

            size_kb = out.stat().st_size // 1024
            return ToolResult(
                f"Screenshot saved to {out} ({size_kb}KB)\n"
                f"URL: {url}\n"
                f"Viewport: {width}x{height}\n"
                f"Full page: {full_page}\n"
                f"Review the screenshot to check layout, colors, spacing, and fix any issues."
            )

        except ImportError:
            return ToolResult(
                "Playwright not installed. Run: pip install playwright && python -m playwright install chromium",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(f"Screenshot error: {e}", is_error=True)


class WebdevGenerateAssets(BaseTool):
    name = "webdev_generate_assets"
    description = (
        "Generate all images needed for a web project in one batch. "
        "Creates hero images, icons, backgrounds, etc. using the image generation backend. "
        "Call this BEFORE building the UI to have assets ready."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Project directory name",
                },
                "assets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "Output filename (e.g., hero.png)"},
                            "prompt": {"type": "string", "description": "Image generation prompt"},
                            "width": {"type": "integer", "default": 1024},
                            "height": {"type": "integer", "default": 1024},
                        },
                        "required": ["filename", "prompt"],
                    },
                    "description": "List of images to generate",
                },
            },
            "required": ["project_name", "assets"],
        }

    async def execute(self, project_name: str, assets: list, **kw) -> ToolResult:
        try:
            import httpx

            ws = Path(self.config.workspace_dir)
            project_dir = ws / "deliverables" / project_name
            assets_dir = project_dir / "public" / "images"
            assets_dir.mkdir(parents=True, exist_ok=True)

            results = []
            for asset in assets:
                filename = asset.get("filename", "image.png")
                prompt = asset.get("prompt", "")
                width = asset.get("width", 1024)
                height = asset.get("height", 1024)
                save_path = str(assets_dir / filename)

                # Try diffusion server first
                generated = False
                for endpoint in ["http://localhost:8091/generate"]:
                    try:
                        async with httpx.AsyncClient(timeout=120) as client:
                            resp = await client.post(endpoint, json={
                                "prompt": prompt,
                                "width": width,
                                "height": height,
                                "steps": 20,
                                "save_path": save_path,
                            })
                            if resp.status_code == 200:
                                generated = True
                                results.append(f"  {filename}: generated ({width}x{height})")
                                break
                    except Exception:
                        continue

                if not generated:
                    # Create a placeholder SVG
                    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="#111120"/>
  <text x="50%" y="50%" text-anchor="middle" fill="#4a9eff" font-size="24" font-family="sans-serif">{filename}</text>
</svg>'''
                    (assets_dir / filename.replace('.png', '.svg')).write_text(svg)
                    results.append(f"  {filename}: placeholder SVG (no image server)")

            return ToolResult(
                f"Assets generated in {assets_dir}:\n" + "\n".join(results)
            )

        except Exception as e:
            return ToolResult(f"Asset generation error: {e}", is_error=True)
