/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

/** Font CSS (Fontsource, KaTeX) lists WOFF / TTF fallbacks after WOFF2. Every web view PhDF
 *  runs in reads WOFF2, so drop the fallbacks and their files stay out of the build (~2 MB). */
function woff2Only(): Plugin {
  const fallback = /,\s*url\([^)]*\.(?:woff|ttf)\)\s*format\(["']?(?:woff|truetype)["']?\)/g;
  return {
    name: "phdf-woff2-only",
    enforce: "pre",
    transform(code, id) {
      if (id.split("?")[0].endsWith(".css") && fallback.test(code)) {
        fallback.lastIndex = 0;
        return { code: code.replace(fallback, ""), map: null };
      }
    },
  };
}

export default defineConfig({
  plugins: [woff2Only(), svelte()],
  // Relative asset paths so the built app also loads from the local filesystem.
  base: "./",
  server: { port: 5173, strictPort: true },
  test: { include: ["src/**/*.test.ts"] },
});
