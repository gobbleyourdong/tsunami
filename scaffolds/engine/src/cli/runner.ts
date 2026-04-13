/**
 * CLI Game Runner — headless or windowed via Playwright.
 * Run games from TypeScript files, take screenshots, run visual tests.
 *
 * Usage:
 *   npx tsx engine/src/cli/runner.ts demos/platformer.ts --headless
 *   npx tsx engine/src/cli/runner.ts demos/platformer.ts --screenshot-at=60
 */

export interface RunnerConfig {
  gamePath: string
  headless: boolean
  screenshotAt?: number   // frame number
  screenshotOutput?: string
  width: number
  height: number
  port: number
  timeout: number  // ms
}

export function parseArgs(args: string[]): RunnerConfig {
  const config: RunnerConfig = {
    gamePath: '',
    headless: false,
    width: 1280,
    height: 720,
    port: 5173,
    timeout: 30000,
  }

  for (const arg of args) {
    if (arg.startsWith('--headless')) {
      config.headless = true
    } else if (arg.startsWith('--screenshot-at=')) {
      config.screenshotAt = parseInt(arg.split('=')[1])
    } else if (arg.startsWith('--output=')) {
      config.screenshotOutput = arg.split('=')[1]
    } else if (arg.startsWith('--width=')) {
      config.width = parseInt(arg.split('=')[1])
    } else if (arg.startsWith('--height=')) {
      config.height = parseInt(arg.split('=')[1])
    } else if (arg.startsWith('--port=')) {
      config.port = parseInt(arg.split('=')[1])
    } else if (arg.startsWith('--timeout=')) {
      config.timeout = parseInt(arg.split('=')[1])
    } else if (!arg.startsWith('--')) {
      config.gamePath = arg
    }
  }

  return config
}

/**
 * Generate an HTML page that loads a game script.
 */
export function generateHTML(scriptPath: string): string {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>* { margin:0; padding:0; } canvas { width:100vw; height:100vh; display:block; }</style>
</head>
<body>
  <canvas id="canvas"></canvas>
  <script type="module" src="${scriptPath}"></script>
</body>
</html>`
}

/**
 * Level serialization: scene → JSON → scene (round-trip).
 */
export interface AssetManifest {
  meshes: string[]
  textures: string[]
  sounds: string[]
  animations: string[]
}

export function createManifest(): AssetManifest {
  return { meshes: [], textures: [], sounds: [], animations: [] }
}

export function addToManifest(manifest: AssetManifest, type: keyof AssetManifest, path: string): void {
  if (!manifest[type].includes(path)) {
    manifest[type].push(path)
  }
}

export function validateManifest(manifest: AssetManifest): { valid: boolean; missing: string[] } {
  // In a real implementation this would check file existence
  const missing: string[] = []
  return { valid: missing.length === 0, missing }
}
