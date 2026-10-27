import { expect, test, providers } from "./mission-control-fixtures";
import { management, resource } from "./resource-monitoring-fixture";

for (const width of [320, 390, 1280]) for (const oldOutcome of ["success", "failure"] as const) for (const order of ["old-first", "latest-first"] as const) {
    test(`resource read order at ${width}px (${oldOutcome}, ${order})`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let latest = false;
        await page.route("**/api/v1/providers", route => route.fulfill({ json: providers.map(provider => ({ ...provider,
            name: provider.id === "proxmox" && latest ? "Proxmox refreshed" : provider.name, capabilities: ["resources"],
        })) }));
        await page.route("**/api/v1/providers/proxmox/management", route => route.fulfill({ json: { ...management, resources: [{ ...management.resources[0],
            intent_status: "configured", intent_reason: "matching_active_intent", expectation: "running", record_version: 1,
        }] } }));
        const inventory = (state: string, refreshed_at: string) => ({ provider_id: "proxmox", provider_name: "Proxmox", refreshed_at,
            resources: [{ ...resource, current_state: state, expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] },
                configured: false, needs_review: true, metadata: {} }],
            summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { [state]: 1 } }, metadata: {} });
        let releaseOld!: () => void, releaseLatest!: () => void;
        const oldGate = new Promise<void>(resolve => { releaseOld = resolve; });
        const latestGate = new Promise<void>(resolve => { releaseLatest = resolve; });
        let oldReads = 0, latestReads = 0;
        const oldBodies: Promise<unknown>[] = [];
        page.on("response", response => {
            if (response.headers()["x-atlas-fixture-observation"] === "old") oldBodies.push(response.finished());
        });
        await page.route("**/api/v1/providers/proxmox/resources", async route => {
            expect(route.request().method()).toBe("GET");
            const isLatest = latest;
            if (isLatest) { latestReads += 1; await latestGate; }
            else { oldReads += 1; await oldGate; }
            if (!isLatest && oldOutcome === "failure") return route.fulfill({ status: 503,
                headers: { "x-atlas-fixture-observation": "old" }, json: { private: "PRIVATE-OLD-OBSERVATION" } });
            return route.fulfill({ headers: { "x-atlas-fixture-observation": isLatest ? "latest" : "old" },
                json: inventory(isLatest ? "running" : "stopped", isLatest ? "2026-10-27T02:00:00Z" : "2026-10-27T01:00:00Z") });
        });
        await page.goto("/providers/proxmox");
        const row = page.getByTestId("resource-row-qemu-110");
        await expect(row.getByRole("heading", { name: resource.display_name, exact: true })).toBeVisible();
        await expect.poll(() => oldReads).toBeGreaterThan(0);
        const refreshPage = page.getByRole("button", { name: "Refresh", exact: true });
        await expect(refreshPage).toBeEnabled();
        latest = true;
        // A catalog name update starts a new inventory read without changing the provider ID.
        await refreshPage.click();
        await expect(page.getByRole("heading", { name: "Proxmox refreshed", exact: true })).toBeVisible();
        await expect.poll(() => latestReads).toBeGreaterThan(0);
        const finishOld = async () => {
            releaseOld();
            await expect.poll(() => oldBodies.length).toBe(oldReads);
            await Promise.all(oldBodies);
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        };
        if (order === "old-first") {
            await finishOld();
            await expect(page.getByRole("button", { name: "Refreshing...", exact: true })).toBeDisabled();
            await expect(row.getByText("Stopped", { exact: true })).toHaveCount(0);
            await expect(page.getByText(/could not load observed resources/)).toHaveCount(0);
        }
        releaseLatest();
        await expect(row.getByText("Running", { exact: true })).toBeVisible();
        await expect(row.getByText("Configured — matches observed state", { exact: true })).toBeVisible();
        const stamp = page.getByText(/Last successful inventory refresh:/);
        const latestStamp = await stamp.textContent();
        if (order === "latest-first") await finishOld();
        await page.waitForLoadState("networkidle");
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        await expect(stamp).toHaveText(latestStamp!);
        await expect(row.getByText("Running", { exact: true })).toBeVisible();
        await expect(row.getByText("Configured — matches observed state", { exact: true })).toBeVisible();
        await expect(row.getByText("Configured — does not match observed state", { exact: true })).toHaveCount(0);
        await expect(page.getByText(/could not load observed resources/)).toHaveCount(0);
        await expect(page.getByText("PRIVATE-OLD-OBSERVATION")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Refresh resources", exact: true })).toBeEnabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
