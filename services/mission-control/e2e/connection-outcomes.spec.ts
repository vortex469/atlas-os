import { expect, test } from "@playwright/test";
import { installMissionControlMocks, providers } from "./mission-control-fixtures";

const schema = { provider_id: "proxmox", provider_name: "Proxmox", editable: true, testable: true,
    metadata: {}, fields: [{ key: "host", label: "Host", kind: "host", current_value: "before.invalid" }] };

// One exact synthetic fixture PUT is allowed; reloads remain GET-only.
for (const width of [320, 390, 1280]) for (const outcome of ["lost", "malformed", "foreign"] as const) {
    test.describe(`Connection outcome ${outcome} at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("pauses an uncertain save until a successful explicit reload without replay", async ({ page, baseURL }) => {
            const mutations: string[] = [];
            await installMissionControlMocks(page, "available", mutations);
            await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider, capabilities: ["connection"] })) }));
            let writes = 0;
            let reads = 0;
            const origin = new URL(baseURL!).origin;
            await page.route("**/api/v1/providers/proxmox/connection", route => {
                if (route.request().method() === "GET") {
                    reads += 1;
                    if (reads === 2) return route.fulfill({ status: 503, json: { detail: "Reload temporarily unavailable." } });
                    return route.fulfill({ json: reads > 2 ? { ...schema, fields: [{ ...schema.fields[0], current_value: "stored.invalid" }] } : schema });
                }
                expect(route.request().method()).toBe("PUT");
                expect(new URL(route.request().url()).origin).toBe(origin);
                expect(route.request().postDataJSON()).toEqual({ confirmed: true, values: { host: "before.invalid" } });
                writes += 1;
                return route.fulfill(outcome === "lost"
                    ? { status: 503, json: { detail: "private-save-canary" } }
                    : { json: { provider_id: outcome === "foreign" ? "foreign" : "proxmox",
                        connection_schema: outcome === "malformed" ? { ...schema, fields: [null] } : schema,
                        updated_at: new Date().toISOString(), message: "private-save-canary" } });
            });
            await page.goto("/providers/proxmox");
            await expect(page.getByLabel("Host", { exact: true })).toBeVisible();
            page.once("dialog", async dialog => {
                expect(dialog.message()).toBe("Save connection settings for Proxmox?");
                await dialog.accept();
            });
            await page.getByRole("button", { name: "Save Connection", exact: true }).click();
            await expect(page.getByText("Save outcome not confirmed", { exact: true })).toBeVisible();
            await expect(page.getByText("unverified", { exact: true })).toBeVisible();
            await expect(page.getByRole("button", { name: "Save Connection", exact: true })).toBeDisabled();
            await expect(page.getByRole("button", { name: "Test Connection", exact: true })).toBeDisabled();
            await expect(page.getByLabel("Host", { exact: true })).toHaveValue("before.invalid");
            await expect(page.locator("main")).not.toContainText("private-save-canary");
            await page.getByRole("button", { name: "Reload settings", exact: true }).click();
            await expect(page.getByText("Mission Control could not load the connection settings for Proxmox.", { exact: true })).toBeVisible();
            await expect(page.getByText("Save outcome not confirmed", { exact: true })).toBeVisible();
            await expect(page.getByRole("button", { name: "Save Connection", exact: true })).toBeDisabled();
            await page.getByRole("button", { name: "Reload settings", exact: true }).click();
            await expect(page.getByLabel("Host", { exact: true })).toHaveValue("stored.invalid");
            await expect(page.getByRole("button", { name: "Save Connection", exact: true })).toBeEnabled();
            await expect(page.getByText("Save outcome not confirmed", { exact: true })).toHaveCount(0);
            await expect(page.getByText("Connection settings saved.", { exact: true })).toHaveCount(0);
            expect(writes).toBe(1);
            expect(reads).toBe(3);
            expect(mutations).toEqual([`PUT ${origin}/api/v1/providers/proxmox/connection`]);
        });
    });
}
