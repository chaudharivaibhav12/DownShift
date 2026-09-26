import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Builds into web/dist. server/app.py serves that when it exists and falls back to the
// original vanilla console when it doesn't, so `git clone && uvicorn` still works with no Node.
export default defineConfig({
  plugins: [svelte()],
  build: { outDir: "../web/dist", emptyOutDir: true },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
