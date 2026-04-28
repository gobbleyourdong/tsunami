import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  server: {
    port: 9123,
    strictPort: false,
  },
  build: {
    target: 'es2022',
    // No rollupOptions.input — vite picks up index.html automatically; the
    // raymarch3d POC lives at raymarch3d/index.html and is reachable at
    // /raymarch3d/ during dev.
  },
});
