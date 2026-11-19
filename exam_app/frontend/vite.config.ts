import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.VITE_API_PROXY || "http://13.233.27.70",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
