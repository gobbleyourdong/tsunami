import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import path from "path"

export default defineConfig({
  // Use relative base so the built dist/ renders when opened via
  // file:// (e.g. the vision gate's playwright.goto). Default '/' makes
  // /assets/X.js unresolvable off a filesystem root.
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
