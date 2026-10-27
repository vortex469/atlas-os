import { expect, providers, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) for (const records of [false, true]) for (const failure of ["http", "shape"] as const) {
    test(`provider directory recovery at ${width}px (${records ? "listed" : "empty"}, ${failure})`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let phase: "initial" | "pending" | "failed" | "recovered" = "initial";
        let finish: (() => void) | undefined;
        let reads = 0;
        await page.route("**/api/v1/providers", async route => {
            reads += 1;
            if (phase === "pending") await new Promise<void>(resolve => { finish = resolve; });
            if (phase === "failed") return route.fulfill(failure === "http"
                ? { status: 503, json: { private: "PRIVATE-CATALOG-CANARY" } }
                : { json: { private: "PRIVATE-CATALOG-CANARY" } });
            return route.fulfill({ json: phase === "initial"
                ? records ? [providers[0], { ...providers[0], id: "docker", name: "Docker" }] : []
                : records ? [] : [{ ...providers[0], id: "docker", name: "Docker", health: { ...providers[0].health, status: "offline", message: "New reported condition" } }],
            });
        });
        await page.goto("/providers");
        const refresh = page.getByRole("button", { name: "Refresh", exact: true });
        if (records) {
            await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
            await page.getByRole("searchbox", { name: "Search providers" }).fill("Proxmox");
        } else await expect(page.getByText("No providers are listed yet.", { exact: true })).toBeVisible();
        phase = "pending";
        await refresh.click();
        await expect(page.getByRole("status")).toHaveText("Refreshing providers…");
        await expect(refresh).toBeDisabled();
        await expect.poll(() => Boolean(finish)).toBe(true);
        if (records) {
            const list = page.getByRole("region", { name: "Provider list", exact: true });
            await expect(page.getByRole("searchbox", { name: "Search providers" })).toHaveValue("Proxmox");
            await expect(list.getByText("Unknown · Stale evidence", { exact: true })).toBeVisible();
            await expect(list.locator("[data-mc-status='success']")).toHaveCount(0);
            await expect(list.getByText("Last reported: Mocked provider is reachable.", { exact: true })).toBeVisible();
            await expect(list.getByRole("link", { name: "Open Proxmox provider", exact: true })).toHaveAttribute("href", "/providers/proxmox");
        } else {
            await expect(page.getByText("No providers were listed in the last successful refresh.", { exact: true })).toBeVisible();
            await expect(page.getByText("No providers are listed yet.", { exact: true })).toHaveCount(0);
        }
        phase = "failed";
        finish!();
        await expect(page.getByRole("alert")).toContainText("Provider list could not be refreshed");
        await expect(page.getByRole("alert")).toContainText("Showing the last reported provider list. Current provider health could not be checked.");
        await expect(page.getByText("PRIVATE-CATALOG-CANARY")).toHaveCount(0);
        if (records) {
            await page.getByRole("searchbox", { name: "Search providers" }).fill("missing");
            await expect(page.getByText("No providers match your search.", { exact: true })).toBeVisible();
            await page.getByRole("button", { name: "Clear search", exact: true }).click();
            await expect(page.getByRole("heading", { name: "Docker", exact: true })).toBeVisible();
            await expect(page.getByRole("region", { name: "Provider list" }).locator("[data-mc-status='success']")).toHaveCount(0);
        }
        phase = "recovered";
        await page.getByRole("button", { name: "Try again", exact: true }).click();
        await expect(page.getByRole("alert")).toHaveCount(0);
        if (records) {
            await expect(page.getByText("No providers are listed yet.", { exact: true })).toBeVisible();
            await expect(page.getByRole("region", { name: "Provider list" })).toHaveCount(0);
        } else {
            await expect(page.getByRole("heading", { name: "Docker", exact: true })).toBeVisible();
            await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
            await expect(page.getByText("New reported condition", { exact: true })).toBeVisible();
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(reads).toBe(3);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
