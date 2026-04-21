import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@engine/': resolve(__dirname, '../../engine/src/') + '/',
    },
  },
  server: {
    port: 5179,
    strictPort: false,
    open: false,
  },
  build: {
    target: 'es2022',
    sourcemap: true,
  },
})
