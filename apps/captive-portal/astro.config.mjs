// @ts-check
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

// Static output: the portal ships HTML with no framework runtime. Interactivity is
// added as small scripts, and a UI framework island only where a screen truly needs
// one (see ADR-0005).
export default defineConfig({
  output: "static",
  server: { port: 3000 },
  vite: { plugins: [tailwindcss()] },
});
