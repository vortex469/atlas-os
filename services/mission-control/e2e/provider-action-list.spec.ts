import { expect, test } from "./mission-control-fixtures";
const action = { id: "unload-model", label: "Unload Model", description: "Unload a model from memory.", icon: "power",
    enabled: true, requires_confirmation: true, destructive: false,
    parameters: { model: { type: "string", required: true, description: "Loaded model name.", example: "example:model" } } };
for (const width of [320, 390, 1280]) for (const failure of ["http", "shape", "flag", "parameter", "duplicate"] as const) {
    test(`action list recovery at ${width}px (${failure}) never runs an unconfirmed action`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let recovered = false;
        let reads = 0;
        await page.route("**/api/v1/providers/proxmox/actions", route => {
            reads += 1;
            if (recovered) return route.fulfill({ json: [action] });
            if (failure === "http") return route.fulfill({ status: 503, json: { private: "PRIVATE-ACTION-CANARY" } });
            const malformed = failure === "shape" ? { private: "PRIVATE-ACTION-CANARY" }
                : failure === "flag" ? [{ ...action, enabled: "false" }]
                : failure === "parameter" ? [{ ...action, parameters: { model: { required: true, description: { private: "PRIVATE-ACTION-CANARY" } } } }]
                : [action, { ...action, requires_confirmation: false }];
            return route.fulfill({ json: malformed });
        });
        await page.goto("/providers/proxmox");
        await expect(page.getByText("Action list unavailable", { exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: "Unload Model", exact: true })).toHaveCount(0);
        await expect(page.getByText("PRIVATE-ACTION-CANARY")).toHaveCount(0);
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
        recovered = true;
        await page.getByRole("button", { name: "Reload action list", exact: true }).click();
        const run = page.getByRole("button", { name: "Unload Model", exact: true });
        await expect(run).toBeVisible();
        await expect(run).toBeDisabled();
        await page.getByLabel("model", { exact: false }).fill("example:model");
        await expect(run).toBeEnabled();
        await expect(page.getByText("Confirmation required", { exact: true })).toBeVisible();
        let confirmations = 0;
        page.once("dialog", async dialog => { confirmations += 1; await dialog.dismiss(); });
        await run.click();
        expect(confirmations).toBe(1);
        await expect(page.getByText("Action completed", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Action list unavailable", { exact: true })).toHaveCount(0);
        expect(reads).toBe(2);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
