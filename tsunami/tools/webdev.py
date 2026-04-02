"""Web development tools — scaffold, screenshot, serve.

These tools give the agent a real web development workflow:
scaffold a project, run it, see it, fix it.
"""

from __future__ import annotations

import asyncio
import subprocess
import shutil
import urllib.request
from pathlib import Path

from ..config import resolve_aux_model_endpoint
from ..docker_exec import (
    docker_required,
    docker_requested,
    execute_browser as execute_browser_in_docker,
    run_shell as run_shell_in_docker,
)
from .base import BaseTool, ToolResult

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


async def _wait_for_http_ready(url: str, timeout_s: float = 12.0) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


def _tail_log_hint(log_path: str) -> str:
    path = Path(log_path)
    if not path.exists():
        return log_path
    try:
        lines = [line.strip() for line in path.read_text(errors="replace").splitlines() if line.strip()]
        if not lines:
            return log_path
        return f"{log_path} — last line: {lines[-1][:220]}"
    except Exception:
        return log_path


def normalize_screenshot_output_path(output_path: str) -> tuple[str, str | None]:
    """Coerce screenshot outputs to a real image extension."""
    out = Path(output_path or "screenshot.png")
    suffix = out.suffix.lower()
    if suffix in SCREENSHOT_EXTENSIONS:
        return str(out), None

    if suffix:
        corrected = str(out.with_suffix(".png"))
        return corrected, f"Adjusted screenshot output path from {output_path} to {corrected}."

    corrected = str(out.with_name(f"{out.name}.png"))
    return corrected, f"Adjusted screenshot output path from {output_path or 'screenshot'} to {corrected}."


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

            # Always use manual scaffold — npm create is flaky
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

            # Step 3b: Relax TypeScript config for LLM-generated code
            for tsfile in ["tsconfig.json", "tsconfig.app.json"]:
                tspath = project_dir / tsfile
                if tspath.exists():
                    import json
                    try:
                        tc = json.loads(tspath.read_text())
                        co = tc.get("compilerOptions", {})
                        co["strict"] = False
                        co["noUnusedLocals"] = False
                        co["noUnusedParameters"] = False
                        tspath.write_text(json.dumps(tc, indent=2))
                    except (json.JSONDecodeError, KeyError):
                        pass

            # Step 4: Set up Tailwind CSS entry
            css_file = project_dir / "src" / "index.css"
            css_file.write_text('@import "tailwindcss";\n')

            # Step 4b: Create component directory structure
            (project_dir / "src" / "components" / "UI").mkdir(parents=True, exist_ok=True)
            (project_dir / "src" / "sections").mkdir(parents=True, exist_ok=True)
            (project_dir / "src" / "data").mkdir(parents=True, exist_ok=True)

            # Starter Navbar
            (project_dir / "src" / "components" / "Navbar.tsx").write_text('''export default function Navbar() {
  return (
    <nav className="bg-gray-900 bg-opacity-80 backdrop-blur-sm fixed w-full z-50 py-4">
      <div className="container mx-auto px-4 flex justify-between items-center">
        <a href="#" className="text-2xl font-bold text-white">Project</a>
        <div className="hidden md:flex space-x-6">
          <a href="#features" className="text-gray-300 hover:text-white transition">Features</a>
          <a href="#about" className="text-gray-300 hover:text-white transition">About</a>
        </div>
      </div>
    </nav>
  )
}
''')
            # Starter Footer
            (project_dir / "src" / "components" / "Footer.tsx").write_text('''export default function Footer() {
  return (
    <footer className="bg-gray-950 text-gray-400 py-12 text-center text-sm">
      <p>&copy; {new Date().getFullYear()} Built with TSUNAMI</p>
    </footer>
  )
}
''')
            # Starter Hero
            (project_dir / "src" / "sections" / "HeroSection.tsx").write_text('''export default function HeroSection() {
  return (
    <section className="relative bg-gray-900 text-white py-32 overflow-hidden">
      <div className="container mx-auto px-4 text-center">
        <h1 className="text-5xl md:text-7xl font-bold leading-tight mb-6">Title Here</h1>
        <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">Subtitle here.</p>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-8 rounded-full shadow-lg transition duration-300">Get Started</button>
      </div>
    </section>
  )
}
''')
            # Stub App.tsx — the wave MUST replace this with the real app
            app_file = project_dir / "src" / "App.tsx"
            app_file.write_text('''// TODO: Replace this with your app
export default function App() {
  return <div>App not built yet — write your components and wire them here.</div>
}
''')
            # Clean up default App.css
            default_css = project_dir / "src" / "App.css"
            if default_css.exists():
                default_css.write_text("")

            # Step 5: Create tsunami.md
            tmd = project_dir / "tsunami.md"
            tmd.write_text(
                f"# {project_name}\n\n"
                f"Vite + React + TypeScript + Tailwind CSS project.\n"
                f"Type: {template}\n\n"
                f"## Development\n"
                f"- `npm run dev -- --port 9876` to start dev server on port 9876\n"
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
        # Relaxed tsconfig — LLM-generated code often has unused vars/params
        (project_dir / "tsconfig.json").write_text('{"compilerOptions":{"target":"ES2020","useDefineForClassFields":true,"lib":["ES2020","DOM","DOM.Iterable"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"isolatedModules":true,"moduleDetection":"force","noEmit":true,"jsx":"react-jsx","strict":false,"noUnusedLocals":false,"noUnusedParameters":false,"noFallthroughCasesInSwitch":true},"include":["src"]}')

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

        # Clean blank slate — just src/components/ dir and stub App.tsx
        (project_dir / "src" / "components").mkdir(parents=True, exist_ok=True)

        # Stub App.tsx — the wave MUST replace this
        (project_dir / "src" / "App.tsx").write_text('''// TODO: Replace with your app
export default function App() {
  return <div>App not built yet</div>
}
''')

        install_mode = "host"
        if docker_requested():
            out, err, returncode, reason = await run_shell_in_docker("npm install", str(project_dir), 120)
            if reason is None:
                install_mode = "docker"
                if returncode != 0:
                    return ToolResult(f"Scaffolded files but npm install failed: {(err or out)[:300]}", is_error=True)
            elif docker_required():
                return ToolResult(f"Scaffolded files but Docker execution failed: {reason}", is_error=True)
            else:
                subprocess.run(["npm", "install"], cwd=str(project_dir),
                               capture_output=True, text=True, timeout=120)
        else:
            subprocess.run(["npm", "install"], cwd=str(project_dir),
                           capture_output=True, text=True, timeout=120)

        return ToolResult(
            f"Scaffolded {name} (manual fallback) at {project_dir}\n"
            f"Stack: Vite + React + TypeScript + Tailwind CSS\n"
            f"Execution sandbox: {install_mode}\n"
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
                    "default": 9876,
                },
            },
            "required": ["project_name"],
        }

    async def execute(self, project_name: str, port: int = 9876, **kw) -> ToolResult:
        try:
            ws = Path(self.config.workspace_dir)
            project_dir = ws / "deliverables" / project_name

            if not project_dir.exists():
                return ToolResult(f"Project not found: {project_dir}", is_error=True)

            # Check if package.json exists (React project)
            if (project_dir / "package.json").exists():
                # Pre-flight: type-check for import errors
                sandbox_mode = "host"
                tsc_stdout = ""
                if docker_requested():
                    tsc_stdout, tsc_stderr, tsc_returncode, reason = await run_shell_in_docker(
                        "npx tsc --noEmit --pretty",
                        str(project_dir),
                        30,
                    )
                    if reason is None:
                        sandbox_mode = "docker"
                    elif docker_required():
                        return ToolResult(f"Docker execution required but unavailable: {reason}", is_error=True)
                    else:
                        tsc_result = subprocess.run(
                            ["npx", "tsc", "--noEmit", "--pretty"],
                            cwd=str(project_dir),
                            capture_output=True, text=True, timeout=30,
                        )
                        tsc_stdout = tsc_result.stdout
                        tsc_returncode = tsc_result.returncode
                else:
                    tsc_result = subprocess.run(
                        ["npx", "tsc", "--noEmit", "--pretty"],
                        cwd=str(project_dir),
                        capture_output=True, text=True, timeout=30,
                    )
                    tsc_stdout = tsc_result.stdout
                    tsc_returncode = tsc_result.returncode
                build_warnings = ""
                if tsc_returncode != 0:
                    # Extract just the error lines (not the full output)
                    errors = [l for l in tsc_stdout.split("\n")
                              if "error TS" in l or "Cannot find" in l or "not found" in l][:5]
                    if errors:
                        build_warnings = "\n⚠️ BUILD WARNINGS:\n" + "\n".join(errors) + "\nFix these before screenshotting.\n"

                if sandbox_mode == "docker":
                    log_path = f"/tmp/tsunami-vite-{project_name}-{port}.log"
                    start_cmd = (
                        f"pkill -f 'vite.*--port {port}' >/dev/null 2>&1 || true; "
                        f"nohup npm run dev -- --host 0.0.0.0 --port {port} "
                        f"> {log_path} 2>&1 & echo $!"
                    )
                    out, err, returncode, reason = await run_shell_in_docker(start_cmd, str(project_dir), 20)
                    if reason is None and returncode == 0:
                        ready = await _wait_for_http_ready(f"http://localhost:{port}")
                        if not ready:
                            return ToolResult(
                                f"Dev server failed to come up at http://localhost:{port}\n"
                                f"Execution sandbox: docker\n"
                                f"Check {_tail_log_hint(log_path)}",
                                is_error=True,
                            )
                        pid_text = out.strip().splitlines()[-1] if out.strip() else "docker"
                        return ToolResult(
                            f"Dev server running at http://localhost:{port}\n"
                            f"PID: {pid_text}\n"
                            + build_warnings +
                            f"Execution sandbox: docker\n"
                            f"Use webdev_screenshot to see the page."
                        )
                    if docker_required():
                        return ToolResult(f"Docker execution required but unavailable: {reason or err}", is_error=True)

                # Kill any existing dev server on this port
                subprocess.run(["fuser", "-k", f"{port}/tcp"],
                              capture_output=True, timeout=5)
                await asyncio.sleep(1)

                # Start vite dev server in background
                log_path = f"/tmp/tsunami-vite-{project_name}-{port}.log"
                log_handle = open(log_path, "ab")
                proc = subprocess.Popen(
                    ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", str(port)],
                    cwd=str(project_dir),
                    stdout=log_handle, stderr=subprocess.STDOUT,
                )
                try:
                    log_handle.close()
                except Exception:
                    pass
                ready = await _wait_for_http_ready(f"http://localhost:{port}")
                if not ready:
                    return ToolResult(
                        f"Dev server failed to come up at http://localhost:{port}\n"
                        f"Execution sandbox: host\n"
                        f"Check {_tail_log_hint(log_path)}",
                        is_error=True,
                    )

                return ToolResult(
                    f"Dev server running at http://localhost:{port}\n"
                    f"PID: {proc.pid}\n"
                    + build_warnings +
                    f"Execution sandbox: host\n"
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
                    "description": "URL to screenshot (e.g., http://localhost:9876)",
                    "default": "http://localhost:9876",
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

    async def execute(self, url: str = "http://localhost:9876",
                      output_path: str = "screenshot.png",
                      full_page: bool = True,
                      width: int = 1440, height: int = 900, **kw) -> ToolResult:
        ws = Path(self.config.workspace_dir)
        normalized_output_path, path_note = normalize_screenshot_output_path(output_path)
        out = Path(normalized_output_path)
        if not out.is_absolute():
            out = ws / out
        out.parent.mkdir(parents=True, exist_ok=True)

        if docker_requested():
            ok, result, reason = await asyncio.to_thread(
                execute_browser_in_docker,
                "screenshot",
                {
                    "url": url,
                    "output_path": str(out),
                    "full_page": full_page,
                    "width": width,
                    "height": height,
                    "headless": True,
                },
            )
            if ok:
                screenshot = result if isinstance(result, dict) else {}
                error_text = screenshot.get("error_text")
                size_kb = screenshot.get("size_kb", out.stat().st_size // 1024 if out.exists() else 0)
                result_msg = f"Screenshot saved to {out} ({size_kb}KB)\nURL: {url}\nViewport: {width}x{height}\n"
                if path_note:
                    result_msg = f"{path_note}\n{result_msg}"
                if error_text:
                    result_msg += f"\n⚠️ BUILD ERROR DETECTED:\n{error_text}\n\nFix the error in the source file and screenshot again."
                else:
                    vision_feedback = await self._analyze_screenshot(str(out))
                    if vision_feedback:
                        result_msg += f"\n📸 VISUAL ANALYSIS:\n{vision_feedback}"
                    else:
                        result_msg += "No errors detected."
                return ToolResult(result_msg)
            if docker_required():
                return ToolResult(f"Docker browser execution required but unavailable: {reason or result}", is_error=True)

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": width, "height": height})

                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                except Exception:
                    # Retry with shorter timeout
                    await page.goto(url, wait_until="load", timeout=10000)

                await page.wait_for_timeout(1000)  # Let animations settle

                # Check for Vite/React error overlays before screenshot
                error_text = await page.evaluate("""() => {
                    // Vite error overlay
                    const viteErr = document.querySelector('vite-error-overlay');
                    if (viteErr) return viteErr.shadowRoot?.querySelector('.message-body')?.textContent || 'Vite error detected';
                    // React error boundary
                    const reactErr = document.querySelector('#react-refresh-overlay');
                    if (reactErr) return reactErr.textContent?.substring(0, 500) || 'React error detected';
                    // Generic error text on page
                    const body = document.body?.innerText || '';
                    if (body.includes('Failed to resolve import') || body.includes('SyntaxError') || body.includes('Module not found'))
                        return body.substring(0, 500);
                    return null;
                }""")

                await page.screenshot(path=str(out), full_page=full_page)
                await browser.close()

            size_kb = out.stat().st_size // 1024
            result_msg = f"Screenshot saved to {out} ({size_kb}KB)\nURL: {url}\nViewport: {width}x{height}\n"
            if path_note:
                result_msg = f"{path_note}\n{result_msg}"

            if error_text:
                result_msg += f"\n⚠️ BUILD ERROR DETECTED:\n{error_text}\n\nFix the error in the source file and screenshot again."
            else:
                # Vision analysis — send screenshot to model, get text feedback
                vision_feedback = await self._analyze_screenshot(str(out))
                if vision_feedback:
                    result_msg += f"\n📸 VISUAL ANALYSIS:\n{vision_feedback}"
                else:
                    result_msg += "No errors detected."

            return ToolResult(result_msg)

        except ImportError:
            return ToolResult(
                "Playwright not installed. Rerun ./setup.sh or install it in the repo venv: ./.venv/bin/python -m pip install playwright && ./.venv/bin/python -m playwright install chromium",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(f"Screenshot error: {e}", is_error=True)

    async def _analyze_screenshot(self, image_path: str) -> str:
        """Send screenshot to vision model for analysis. Returns text only — image stays on disk."""
        try:
            import base64
            import httpx

            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            # Try primary model first, then the auxiliary endpoint if it differs.
            endpoints = [self.config.model_endpoint]
            aux_endpoint = resolve_aux_model_endpoint()
            if aux_endpoint not in endpoints:
                endpoints.append(aux_endpoint)

            for endpoint in endpoints:
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(
                            f"{endpoint}/v1/chat/completions",
                            json={
                                "model": "qwen",
                                "messages": [{
                                    "role": "user",
                                    "content": [
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                                        {"type": "text", "text": "Analyze this web page screenshot. List any visual issues: broken layout, missing content, color problems, overlapping elements, empty sections, broken images. Be specific and brief. If it looks good, say so."},
                                    ]
                                }],
                                "max_tokens": 300,
                            },
                            headers={"Authorization": "Bearer not-needed"},
                        )
                        if resp.status_code == 200:
                            return resp.json()["choices"][0]["message"]["content"]
                except Exception:
                    continue
        except Exception:
            pass
        return ""


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
                        async with httpx.AsyncClient(timeout=None) as client:
                            # Convert host path to Docker container path
                            ark_dir = str(Path(__file__).parent.parent.parent)
                            container_save = save_path.replace(ark_dir, "/ark")
                            resp = await client.post(endpoint, json={
                                "prompt": prompt,
                                "width": width,
                                "height": height,
                                "steps": 20,
                                "save_path": container_save,
                            })
                            if resp.status_code == 200:
                                # Also write response bytes to host path
                                # (in case Docker save_path mapping fails)
                                if resp.headers.get("content-type", "").startswith("image"):
                                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                                    Path(save_path).write_bytes(resp.content)
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
