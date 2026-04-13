import { defineConfig } from 'vite'

export default defineConfig({
  root: 'demos',
  publicDir: '../public',
  server: {
    port: 5173,
    open: false,
  },
  resolve: {
    alias: {
      '@engine': '/src',
    },
  },
  assetsInclude: ['**/*.wgsl'],
})
