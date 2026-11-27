import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

declare const process: { env: Record<string, string | undefined> };
const api = process.env.SIGNAL_LAB_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: api, changeOrigin: true }, "/tap": api },
  },
  build: { chunkSizeWarningLimit: 1500 },
});
