import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@engine': path.resolve(__dirname, '../../engine/src'),
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
