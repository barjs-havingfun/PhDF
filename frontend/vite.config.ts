import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  // Relative asset paths so the built app also loads from the local filesystem.
  base: "./",
  server: { port: 5173, strictPort: true },
});
