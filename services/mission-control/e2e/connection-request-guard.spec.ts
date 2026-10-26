import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";

const schema = { provider_id: "proxmox", provider_name: "Proxmox", editable: true, testable: true,
    updated_at: null, metadata: {}, fields: [{ key: "host", label: "Host", kind: "host", required: true,
        editable: true, secret: false, current_value: "fixture.invalid", secret_state: null, source: null,
        help_text: "", options: [], validation: {} }] };

// Exactly one synthetic confirmed write is allowed per case; no backend is used.
for (const width of [320, 390, 1280]) for (const mode of ["save", "test"] as const) {
    test.describe(`Connection request guard ${mode} at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("keeps one confirmed request active and blocks other connection controls", async ({ page, baseURL }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, "available", mutations);
            await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider, capabilities: ["connection"] })) }));
            let reads = 0;
            let writes = 0;
            let confirmations = 0;
            let release!: () => void;
            const pending = new Promise<void>(resolve => { release = resolve; });
            const origin = new URL(baseURL!).origin;
            const handleWrite = async (route: import("@playwright/test").Route) => {
                expect(new URL(route.request().url()).origin).toBe(origin);
                expect(route.request().method()).toBe(mode === "save" ? "PUT" : "POST");
                expect(route.request().postDataJSON()).toEqual({ confirmed: true, values: { host: "fixture.invalid" } });
                writes += 1;
                await pending;
                return route.fulfill({ json: mode === "save"
                    ? { provider_id: "proxmox", connection_schema: schema, updated_at: new Date().toISOString(), message: "Saved." }
                    : { provider_id: "proxmox", status: "success", message: "Connection OK.", tested_at: new Date().toISOString(), latency_ms: 1, diagnostics: {} } });
            };
            await page.route("**/api/v1/providers/proxmox/connection", route => {
                if (route.request().method() === "GET") { reads += 1; return route.fulfill({ json: schema }); }
                if (mode === "save") return handleWrite(route);
                return route.fallback();
            });
            if (mode === "test") await page.route("**/api/v1/providers/proxmox/connection/test", handleWrite);
            await page.goto("/providers/proxmox");
            await expect(page.getByLabel("Host", { exact: false })).toBeVisible();
            const initialReads = reads;
            page.on("dialog", async dialog => {
                confirmations += 1;
                expect(dialog.message()).toBe(mode === "save" ? "Save connection settings for Proxmox?" : "Run a live connection test for Proxmox?");
                await dialog.accept();
            });
            await page.evaluate(mode => {
                const buttons = Array.from(document.querySelectorAll("button"));
                const selected = buttons.find(button => button.textContent?.trim() === (mode === "save" ? "Save Connection" : "Test Connection"))!;
                const other = buttons.find(button => button.textContent?.trim() === (mode === "save" ? "Test Connection" : "Save Connection"))!;
                selected.click(); selected.click(); other.click();
                buttons.find(button => button.textContent?.trim() === "Reload settings")!.click();
            }, mode);
            await expect.poll(() => writes).toBe(1);
            expect(confirmations).toBe(1);
            expect(reads).toBe(initialReads);
            await expect(page.getByRole("button", { name: mode === "save" ? "Saving..." : "Testing...", exact: true })).toBeDisabled();
            release();
            await expect(page.getByRole("button", { name: mode === "save" ? "Save Connection" : "Test Connection", exact: true })).toBeEnabled();
            expect(writes).toBe(1);
            expect(mutations).toEqual([`${mode === "save" ? "PUT" : "POST"} ${origin}/api/v1/providers/proxmox/connection${mode === "test" ? "/test" : ""}`]);
        });
    });
}
