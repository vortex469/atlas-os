import { aceSummary, expect, test } from "./mission-control-fixtures";

const long = "a".repeat(180);
const finding = { id: "layout-finding", severity: `reported${long}`, category: `category${long}`, source: "proxmox", component: "proxmox",
    title: `Finding${long}`, message: `Evidence${long}`, recommendation: null, metric: {}, affects_health: true, score_penalty: 10,
    details: { unavailable_entities: Array.from({ length: 6 }, (_, index) => ({ entity_id: `sensor.${index}${long}`, name: `Sensor ${index}`, state: `reported${long}` })) } };
const recommendation = { title: `Recommendation${long}`, reason: `Reason${long}`, priority: `priority${long}`, confidence: 0.9,
    estimated_effort: `effort${long}`, component: "proxmox" };

for (const width of [320, 390, 1280]) for (const kind of ["finding", "recommendation"] as const) {
    test(`advisory ${kind} fits ${width}px with keyboard-accessible details`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/ace/summary", route => route.fulfill({ json: { ...aceSummary,
            findings: kind === "finding" ? [finding] : [], recommendations: kind === "recommendation" ? [recommendation] : [],
        } }));
        await page.goto("/providers/proxmox");
        const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: kind === "finding" ? finding.title : recommendation.title, exact: true }) });
        await expect(card).toBeVisible();
        const verifyBounds = async () => {
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            const panel = await card.boundingBox();
            expect(panel).not.toBeNull();
            expect(panel!.x).toBeGreaterThanOrEqual(0);
            expect(panel!.x + panel!.width).toBeLessThanOrEqual(width + 1);
            const bounds = await card.evaluate(element => {
                const panel = element.getBoundingClientRect();
                return [...element.querySelectorAll("h3,p,span,dd,dt,summary")].filter(item => item.getClientRects().length > 0 && Boolean(item.textContent?.trim())).map(item => {
                    const range = document.createRange(); range.selectNodeContents(item);
                    const text = range.getBoundingClientRect();
                    return { text: item.textContent, left: text.left, right: text.right, panelLeft: panel.left, panelRight: panel.right };
                });
            });
            for (const b of bounds) {
                expect(b.left, b.text!).toBeGreaterThanOrEqual(b.panelLeft - 1);
                expect(b.right, b.text!).toBeLessThanOrEqual(b.panelRight + 1);
            }
        };
        await verifyBounds();
        const metadata = card.locator("dl");
        await expect(metadata).toBeHidden();
        const toggle = card.locator("summary").filter({ hasText: kind === "finding" ? "Finding details" : "Recommendation details" });
        await toggle.focus();
        await page.keyboard.press("Enter");
        await expect(metadata).toBeVisible();
        await expect(card.getByText(kind === "finding" ? `Category${long}` : recommendation.estimated_effort, { exact: true })).toBeVisible();
        await verifyBounds();
        await page.keyboard.press("Space");
        await expect(metadata).toBeHidden();
        if (kind === "finding") {
            await expect(card.getByText("Showing 5 of 6", { exact: true })).toBeVisible();
            const expand = card.getByRole("button", { name: "View details", exact: true });
            await expand.focus();
            await page.keyboard.press("Enter");
            await expect(card.getByText("Showing 6 of 6", { exact: true })).toBeVisible();
            await expect(card.getByText("Sensor 5", { exact: true })).toBeVisible();
            await verifyBounds();
            await card.getByRole("button", { name: "Collapse", exact: true }).click();
            await expect(card.getByText("Showing 5 of 6", { exact: true })).toBeVisible();
        }
        expect(rejectedMutationRequests).toEqual([]);
    });
}
