import { defineConfig } from 'vitest/config'
import path from 'path'
import { existsSync } from 'fs'

// Resolve the engine the same way vite.config.ts does — walk up
// looking for engine/src/index.ts. The game scaffold lives next to
// scaffolds/engine/ in the ark monorepo; deliverables live one extra
// level up under workspace/deliverables/<name>/, with a sibling
// `engine` symlink the project_init tool drops in. Either layout
// resolves cleanly.
function findEngine(): string {
  let dir = __dirname
  for (let i = 0; i < 6; i++) {
    const candidate = path.join(dir, 'engine', 'src')
    if (existsSync(path.join(candidate, 'index.ts'))) return candidate
    dir = path.dirname(dir)
  }
  return path.resolve(__dirname, '../engine/src')
}

const engineSrc = findEngine()

export default defineConfig({
  resolve: {
    alias: [
      { find: /^@engine\/(.*)$/, replacement: path.join(engineSrc, '$1') },
      { find: /^@engine$/, replacement: path.join(engineSrc, 'index.ts') },
      { find: /^tsunami-engine\/(.*)$/, replacement: path.join(engineSrc, '$1') },
      { find: /^tsunami-engine$/, replacement: path.join(engineSrc, 'index.ts') },
    ],
  },
  test: {
    include: ['tests/**/*.test.ts'],
    // jsdom: KeyboardInput.bind() uses window.addEventListener; the
    // FrameLoop tests stub their own globals so they don't depend on
    // the env, but jsdom is harmless for them.
    environment: 'jsdom',
    globals: false,
  },
})
