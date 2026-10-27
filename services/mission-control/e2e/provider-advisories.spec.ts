import { aceSummary, expect, test } from "./mission-control-fixtures";

const finding = { id: "reported-finding", severity: "warning", category: "state_mismatch", source: "proxmox", component: "proxmox",
    title: "Reported provider issue", message: "Reported provider evidence", recommendation: null, metric: {}, details: {}, affects_health: false, score_penalty: 0 };
const recommendation = { title: "Review provider issue", reason: "Review the reported evidence", priority: "low", confidence: 0.9, estimated_effort: "low", component: "proxmox" };

const malformed = {
    shape: { ...aceSummary, findings: null, private: "PRIVATE-SUMMARY-CANARY" },
    finding: { ...aceSummary, findings: [{ ...finding, source: { private: "PRIVATE-SUMMARY-CANARY" } }] },
    recommendation: { ...aceSummary, recommendations: [{ ...recommendation, priority: null }] },
};

for (const width of [320, 390, 1280]) for (const records of [false, true]) for (const failure of ["http", "shape", "finding", "recommendation"] as const) {
    test.describe(`Retained provider advisories at ${width}px (records: ${records}, ${failure})`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("distinguishes last reported results from a fresh empty response", async ({ page, rejectedMutationRequests }) => {
            let phase: "initial" | "failed" | "recovered" = "initial";
            await page.route("**/api/v1/ace/summary", route => {
                if (phase === "failed") return failure === "http"
                    ? route.fulfill({ status: 503, json: { detail: "unavailable" } })
                    : route.fulfill({ json: malformed[failure] });
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
            await expect(page.getByText("PRIVATE-SUMMARY-CANARY")).toHaveCount(0);
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

for (const width of [320, 390, 1280]) {
    for (const failure of ["shape", "finding", "recommendation"] as const) {
        test(`initial malformed summary ${failure} at ${width}px recovers through Refresh`, async ({ page, rejectedMutationRequests }) => {
            await page.setViewportSize({ width, height: 900 });
            let available = false;
            await page.route("**/api/v1/ace/summary", route => route.fulfill({ json: available ? aceSummary : malformed[failure] }));
            await page.goto("/providers/proxmox");
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toBeVisible();
            await expect(page.getByText("Provider not found", { exact: true })).toHaveCount(0);
            await expect(page.getByText("PRIVATE-SUMMARY-CANARY")).toHaveCount(0);
            available = true;
            await page.getByRole("button", { name: "Refresh", exact: true }).click();
            await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Diagnostics", exact: true })).toBeVisible();
            await expect(page.getByText("Atlas Core unavailable", { exact: true })).toHaveCount(0);
            expect(rejectedMutationRequests).toEqual([]);
        });
    }
    test(`free-form entity details at ${width}px keep the finding readable`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/ace/summary", route => route.fulfill({ json: { ...aceSummary, findings: [{ ...finding, details: {
            unavailable_entities: [
                { entity_id: { private: "PRIVATE-ENTITY-CANARY" }, name: ["PRIVATE-ENTITY-CANARY"], state: { private: "PRIVATE-ENTITY-CANARY" } },
                { entity_id: "sensor.power", name: "Power", state: "unavailable" },
                null, 42, [],
            ],
        } }] } }));
        await page.goto("/providers/proxmox");
        await expect(page.getByRole("heading", { name: finding.title, exact: true })).toBeVisible();
        await expect(page.getByText("Unknown entity", { exact: true })).toBeVisible();
        await expect(page.getByText("Power", { exact: true })).toBeVisible();
        await expect(page.getByText("Showing 2 of 2", { exact: true })).toBeVisible();
        await expect(page.getByText("PRIVATE-ENTITY-CANARY")).toHaveCount(0);
        await expect(page.getByText("Atlas Core unavailable", { exact: true })).toHaveCount(0);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
