import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  resolve: {
    alias: {
      // Allow deep imports like '@engine/mechanics', '@engine/components', etc.
      '@engine/': resolve(__dirname, '../../engine/src/') + '/',
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    open: false,
  },
  build: {
    target: 'es2022',
    sourcemap: true,
  },
})
