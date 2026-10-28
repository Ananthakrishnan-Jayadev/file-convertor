import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built files in dist/ are served by the FastAPI backend (`fileconvert serve`).
export default defineConfig({
  plugins: [react()],
});
