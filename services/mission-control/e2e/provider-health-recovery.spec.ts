import { expect, test, providers } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) for (const initialFailure of [false, true]) for (const failure of ["http", "capabilities", "name", "duplicate", "shape"] as const) {
    test.describe(`Provider health refresh at ${width}px (${failure}, initial: ${initialFailure})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("marks retained healthy facts as last reported and recovers through reads", async ({ page, rejectedMutationRequests }) => {
            let phase: "healthy" | "failed" | "offline" = "healthy";
            await page.route("**/api/v1/providers", route => {
                if (phase === "failed" || (phase === "healthy" && initialFailure)) {
                    if (failure === "http") return route.fulfill({ status: 503, json: { detail: "unavailable" } });
                    const malformed = failure === "capabilities" ? [{ ...providers[0], capabilities: null }]
                        : failure === "name" ? [{ ...providers[0], name: { private: "PRIVATE-CATALOG-CANARY" } }]
                        : failure === "duplicate" ? [providers[0], providers[0]] : { private: "PRIVATE-CATALOG-CANARY" };
                    return route.fulfill({ json: malformed });
                }
                return route.fulfill({ json: providers.map(provider => ({ ...provider,
                    health: { ...provider.health, status: phase === "offline" ? "offline" : "healthy",
                        message: phase === "offline" ? "Provider is not reachable." : "Provider is reachable." },
                })) });
            });
            await page.goto("/providers/proxmox");
            const overview = page.locator("section").filter({ has: page.getByRole("heading", { name: "Proxmox", level: 1 }) });
            if (!initialFailure) {
                await expect(overview.locator("[data-mc-status='success']")).toBeVisible();
                phase = "failed";
                await page.getByRole("button", { name: "Refresh", exact: true }).click();
            }
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toBeVisible();
            await expect(overview.locator("[data-mc-status='success']")).toHaveCount(0);
            await expect(page.getByText("PRIVATE-CATALOG-CANARY")).toHaveCount(0);
            await expect(page.getByText("Provider not found", { exact: true })).toHaveCount(0);
            if (!initialFailure) {
                await expect(overview.locator("[data-mc-status='neutral']")).toBeVisible();
                await expect(overview.getByText("Current provider health could not be refreshed. Last reported status: Healthy.", { exact: true })).toBeVisible();
                await expect(overview.getByText("Last reported message: Provider is reachable.", { exact: true })).toBeVisible();
            }
            phase = "offline";
            await page.getByRole("button", { name: "Refresh", exact: true }).click();
            await expect(overview.locator("[data-mc-status='error']")).toBeVisible();
            await expect(overview.getByText("Provider is not reachable.", { exact: true })).toBeVisible();
            await expect(overview.getByText(/Last reported message:/)).toHaveCount(0);
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toHaveCount(0);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
