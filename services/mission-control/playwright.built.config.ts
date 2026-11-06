import { defineConfig } from "@playwright/test";

import base from "./playwright.config";

// Reuse operator journeys against generated assets and isolated API fixtures.
// These two specs depend on Vite source-module URLs and stay in the dev suite.
export default defineConfig({
    ...base,
    testIgnore: ["**/page-loading.spec.ts", "**/screen-recovery.spec.ts"],
    use: { ...base.use, baseURL: "http://127.0.0.1:4173" },
    webServer: {
        command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: false,
        timeout: 120_000,
    },
});
