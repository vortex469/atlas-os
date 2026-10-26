import { aceSummary, expect, test } from "./mission-control-fixtures";

const finding = { id: "reported-finding", severity: "warning", category: "state_mismatch", source: "proxmox", component: "proxmox",
    title: "Reported provider issue", message: "Reported provider evidence", recommendation: null, metric: {}, details: {}, affects_health: false, score_penalty: 0 };
const recommendation = { title: "Review provider issue", reason: "Review the reported evidence", priority: "low", confidence: 0.9, estimated_effort: "low", component: "proxmox" };

for (const width of [320, 390, 1280]) for (const records of [false, true]) {
    test.describe(`Retained provider advisories at ${width}px (records: ${records})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("distinguishes last reported results from a fresh empty response", async ({ page, rejectedMutationRequests }) => {
            let phase: "initial" | "failed" | "recovered" = "initial";
            await page.route("**/api/v1/ace/summary", route => {
                if (phase === "failed") return route.fulfill({ status: 503, json: { detail: "unavailable" } });
                return route.fulfill({ json: { ...aceSummary, findings: phase === "initial" && records ? [finding] : [],
                    recommendations: phase === "initial" && records ? [recommendation] : [] } });
            });
            await page.goto("/providers/proxmox");
            await expect(page.getByRole("heading", { name: "Diagnostics", exact: true })).toBeVisible();
            if (records) await expect(page.getByRole("heading", { name: finding.title, exact: true })).toBeVisible();
            phase = "failed";
            await page.getByRole("button", { name: "Refresh", exact: true }).click();
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toBeVisible();
            await expect(page.getByText(/no current findings/i)).toHaveCount(0);
            await expect(page.getByText(/no current recommendations/i)).toHaveCount(0);
            await expect(page.getByText("Diagnostics could not be refreshed. Showing the last reported findings.", { exact: true })).toBeVisible();
            await expect(page.getByText("Recommendations could not be refreshed. Showing the last reported recommendations.", { exact: true })).toBeVisible();
            if (records) {
                await expect(page.getByRole("heading", { name: finding.title, exact: true })).toBeVisible();
                await expect(page.getByRole("heading", { name: recommendation.title, exact: true })).toBeVisible();
            } else {
                await expect(page.getByText("No findings were reported in the last successful refresh.", { exact: true })).toBeVisible();
                await expect(page.getByText("No recommendations were reported in the last successful refresh.", { exact: true })).toBeVisible();
            }
            phase = "recovered";
            await page.getByRole("button", { name: "Refresh", exact: true }).click();
            await expect(page.getByText("No diagnostic findings were reported for this provider.", { exact: true })).toBeVisible();
            await expect(page.getByText("No recommendations were reported for this provider.", { exact: true })).toBeVisible();
            await expect(page.getByText(/Showing the last reported/)).toHaveCount(0);
            await expect(page.getByRole("heading", { name: finding.title, exact: true })).toHaveCount(0);
            await expect(page.getByRole("heading", { name: recommendation.title, exact: true })).toHaveCount(0);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}
