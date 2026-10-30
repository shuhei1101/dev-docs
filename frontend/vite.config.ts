import { fileURLToPath } from "node:url";

import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const here = (path: string): string => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  root: here("."),
  plugins: [
    tanstackRouter({
      target: "react",
      routesDirectory: here("./src/routes"),
      generatedRouteTree: here("./src/route-tree.gen.ts"),
      autoCodeSplitting: false,
    }),
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  resolve: { alias: { "@": here("./src") } },
  build: { outDir: here("../src/dev_docs/screen"), emptyOutDir: true },
  server: { proxy: { "/_api": "http://127.0.0.1:8781" } },
});
