import { defineConfig } from "@playwright/test";

import base from "./playwright.config";

// Reuse the read-only shell/navigation cases against generated assets.
// Development-only module interception tests remain in the regular suite.
export default defineConfig({
    ...base,
    testMatch: ["**/app-shell.spec.ts", "**/navigation.spec.ts"],
    use: { ...base.use, baseURL: "http://127.0.0.1:4173" },
    webServer: {
        command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: false,
        timeout: 120_000,
    },
});
