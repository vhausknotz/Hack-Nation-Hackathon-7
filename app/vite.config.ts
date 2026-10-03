import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: { __ATLAS_BUILD__: JSON.stringify(new Date().toISOString()) },
});
