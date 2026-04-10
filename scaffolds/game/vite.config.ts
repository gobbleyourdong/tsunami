import { defineConfig } from 'vite'
import path from 'path'
import { existsSync } from 'fs'

// Find the engine — walk up from __dirname until we find engine/src/index.ts
function findEngine(): string {
  let dir = __dirname
  for (let i = 0; i < 6; i++) {
    const candidate = path.join(dir, 'engine', 'src')
    if (existsSync(path.join(candidate, 'index.ts'))) return candidate
    dir = path.dirname(dir)
  }
  // Fallback: relative to scaffold location (works when building from scaffolds/)
  return path.resolve(__dirname, '../../engine/src')
}

export default defineConfig({
  resolve: {
    alias: {
      '@engine': findEngine(),
    },
  },
  build: {
    outDir: 'dist',
    target: 'esnext',
  },
  server: {
    port: 5174,
  },
})
