import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The built page ships inside the Python package, which serves it under
// /static/ (index.html at /). Files land flat in that folder: the server
// refuses any path with a slash in it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/",
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(import.meta.dirname, "../src/whatferry/ui/static"),
    emptyOutDir: true,
    assetsDir: "",
    // One script and one stylesheet; no inline modulepreload polyfill,
    // which the page's Content-Security-Policy would block.
    modulePreload: { polyfill: false },
  },
})
