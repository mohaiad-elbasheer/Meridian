import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // Base path for GitHub Pages project sites (e.g. /Meridian/); "/" everywhere else.
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
