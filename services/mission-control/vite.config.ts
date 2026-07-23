import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
    plugins: [
        react(),
        tailwindcss(),
    ],
    server: {
        proxy: {
            "/atlas-core": {
                target: "http://127.0.0.1:8643",
                changeOrigin: true,
                rewrite: (path) =>
                    path.replace(/^\/atlas-core/, ""),
            },
        },
    },
});