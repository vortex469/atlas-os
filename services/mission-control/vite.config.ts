import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import type { ProxyOptions } from "vite";

// Match the production edge: backend identity comes from its own authentication.
const stripIdentityHeaders: ProxyOptions["configure"] = (proxy) => {
    proxy.on("proxyReq", (request) => {
        for (const header of ["x-atlas-operator", "x-auth-user", "x-user", "remote-user"]) request.removeHeader(header);
    });
};

export default defineConfig({
    plugins: [
        react(),
        tailwindcss(),
    ],
    server: {
        proxy: {
            "/api/v1": {
                target: "http://127.0.0.1:8643",
                changeOrigin: true,
                configure: stripIdentityHeaders,
            },
            "/agent-api": {
                target: "http://127.0.0.1:8090",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/agent-api(?=\/|\?|$)/, ""),
                configure: stripIdentityHeaders,
            },
        },
    },
});
