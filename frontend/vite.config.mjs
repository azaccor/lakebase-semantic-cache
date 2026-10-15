import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built on Databricks Apps by `npm run build` (root package.json) into server/static,
// which FastAPI serves. `npm run dev` proxies /api to a local backend on :8000.
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  plugins: [react()],
  build: { outDir: fileURLToPath(new URL("../server/static", import.meta.url)), emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
