import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  server: {
    port: 9123,
    strictPort: false,
  },
  build: {
    target: 'es2022',
    rollupOptions: {
      input: {
        index: 'index.html',
        raymarch3d: 'raymarch3d/index.html',
      },
    },
  },
});
