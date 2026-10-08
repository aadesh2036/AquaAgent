import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// Contracts come from ../shared (BACKBONE §0.4) — never re-declared in the frontend.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@contracts": fileURLToPath(new URL("../shared/contracts/contracts.ts", import.meta.url)),
      "@netconfig": fileURLToPath(new URL("../config/networks/net_epa_tutorial_v1.json", import.meta.url)),
      "@units": fileURLToPath(new URL("../shared/units.ts", import.meta.url)),
    },
  },
  server: { port: 5173, fs: { allow: [".."] } },
});
