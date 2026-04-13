import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
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
  return path.resolve(__dirname, '../engine/src')
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@engine': findEngine(),
      // QA-1 Fire 91/92: the gamedev adapter (fine-tuned model) imports from
      // `tsunami-engine` as if it were a published npm package. That package
      // doesn't exist — the engine is wired via this vite alias. Accept both
      // forms so the adapter's training pattern resolves. The canonical
      // import remains `@engine`; `tsunami-engine` is an ergonomic alias.
      'tsunami-engine': findEngine(),
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
