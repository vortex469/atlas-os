import { aceSummary, expect, policies, providers, test } from "./mission-control-fixtures";

const longName = `archive${"a".repeat(180)}`;
for (const width of [320, 390, 1280]) for (const providerId of ["proxmox", "docker"]) {
    test.describe(`Provider reference panels at ${width}px (${providerId})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("uses complete rows and keeps long values readable without tall metric stacks", async ({ page, rejectedMutationRequests }) => {
            await page.route("**/api/v1/providers", route => route.fulfill({ json: [
                { ...providers[0], id: providerId, name: providerId === "docker" ? "Docker" : "Proxmox", capabilities: [] },
            ] }));
            await page.route("**/api/v1/policies", route => route.fulfill({ json: { ...policies,
                proxmox: { guests: { "110": { expected: "stopped" } } }, docker: { containers: { [longName]: { expected: "running" } } },
                intelligence: { providers: { [providerId]: { maximum_collection_duration_ms: 30, severity: "warning" } } },
            } }));
            await page.route("**/api/v1/intelligence/telemetry/history?*", route => route.fulfill({ json: [{ id: "layout-history", collected_at: "2026-10-26T12:00:00Z", telemetry: {
                ...aceSummary.telemetry, providers: [{ provider_id: providerId, provider_name: providerId === "docker" ? "Docker" : "Proxmox", status: "completed", duration_ms: 21, finding_count: 0 }],
            } }] }));
            await page.goto(`/providers/${providerId}`);
            const settings = page.locator("section").filter({ has: page.getByRole("heading", { name: providerId === "proxmox" ? "Legacy policy evidence" : "Operational Policy", exact: true }) });
            const history = page.locator("section").filter({ has: page.getByRole("heading", { name: "Intelligence History", exact: true }) });
            await expect(settings.locator("dl")).toBeVisible();
            const row = settings.locator("dl > div").last();
            const sizes = await row.evaluate(element => ({ row: element.getBoundingClientRect().width, panel: element.parentElement!.clientWidth }));
            expect(sizes.row).toBeGreaterThanOrEqual(sizes.panel - 2);
            expect(sizes.row).toBeLessThanOrEqual(sizes.panel + 1);
            if (providerId === "docker") {
                const value = settings.getByText(`${longName}: running`, { exact: true });
                await expect(value).toBeVisible();
                const bounds = await value.evaluate(element => {
                    const text = document.createRange(); text.selectNodeContents(element);
                    const rect = text.getBoundingClientRect(), parent = element.getBoundingClientRect();
                    const panel = element.closest("dl")!.getBoundingClientRect();
                    return { left: rect.left, right: rect.right, parentLeft: Math.max(parent.left, panel.left), parentRight: Math.min(parent.right, panel.right, document.documentElement.clientWidth) };
                });
                expect(bounds.left).toBeGreaterThanOrEqual(bounds.parentLeft - 1);
                expect(bounds.right).toBeLessThanOrEqual(bounds.parentRight + 1);
            }
            const first = await history.getByText("Snapshots", { exact: true }).boundingBox();
            const second = await history.getByText("Average", { exact: true }).boundingBox();
            expect(first).not.toBeNull(); expect(second).not.toBeNull();
            expect(Math.abs(first!.y - second!.y)).toBeLessThanOrEqual(1);
            const third = await history.getByText("Over threshold", { exact: true }).boundingBox();
            expect(third).not.toBeNull();
            if (width < 1024) expect(third!.y).toBeGreaterThan(first!.y + first!.height);
            else expect(Math.abs(first!.y - third!.y)).toBeLessThanOrEqual(1);

            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
