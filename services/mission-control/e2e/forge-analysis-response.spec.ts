import { expect, test } from "@playwright/test";
import { changedDeploymentAnalysis, deploymentAnalysisFixture } from "../src/test/deploymentAnalysis";

for (const width of [320, 390, 1280]) for (const failure of ["shape", "ports", "approval"] as const) {
    test(`unreadable Forge ${failure} at ${width}px offers explicit retry without replaying analysis`, async ({ page, baseURL }) => {
        await page.setViewportSize({ width, height: 900 });
        const origin = new URL(baseURL!).origin;
        const unexpected: string[] = [];
        let analyses = 0;
        await page.route("**/*", route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin !== origin || request.method() !== "GET") {
                unexpected.push(`${request.method()} ${url.pathname}`);
                return route.abort();
            }
            if (url.pathname === "/api/v1") return route.fulfill({ json: { release: "fixture" } });
            if (url.pathname.startsWith("/api/v1/") || url.pathname.startsWith("/agent-api/")) return route.fulfill({ status: url.pathname.endsWith("/operator-auth/session") ? 401 : 404, json: { detail: "Unavailable in analysis fixture." } });
            return route.continue();
        });
        await page.route("**/api/v1/analysis/deployments", route => {
            expect(route.request().method()).toBe("POST");
            expect(route.request().postDataJSON()).toEqual({ source: "compose", reference: "Compose preview", document: { services: { web: { image: "example.invalid/fixture:one" } } } });
            analyses += 1;
            const readable = deploymentAnalysisFixture();
            readable.result.analysis.plan.risk = "critical";
            const unreadable = failure === "shape" ? { private: "PUBLIC-ANALYSIS-CANARY" }
                : failure === "ports" ? changedDeploymentAnalysis("result.analysis.plan.components.0.ports.0.protocol", { private: "PUBLIC-ANALYSIS-CANARY" })
                : changedDeploymentAnalysis("result.planning.proposal.approval_required", "false");
            return route.fulfill({ json: analyses === 1 ? unreadable : readable });
        });
        await page.goto("/forge");
        await page.getByLabel("Deployment name").fill("Compose preview");
        const composeDocument = "services:\n  web:\n    image: example.invalid/fixture:one\n";
        await page.getByLabel("Compose document").fill(composeDocument);
        await page.getByRole("button", { name: "Analyze document", exact: true }).click();
        await expect(page.getByRole("alert")).toHaveText("The analysis report is incomplete or unreadable. Analyze the document again.");
        await expect(page.getByRole("button", { name: "Analyze document", exact: true })).toBeEnabled();
        await expect(page.getByRole("status")).toBeEmpty();
        await expect(page.getByRole("heading", { name: "Deployment Brief", exact: true })).toHaveCount(0);
        await expect(page.locator("body")).not.toContainText("PUBLIC-ANALYSIS-CANARY");
        expect(analyses).toBe(1);
        if (failure === "shape" && width !== 320) {
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-unreadable-forge-${width}.png`, fullPage: true });
        }
        await page.getByLabel("Compose document").fill(`${composeDocument}\n`);
        await expect(page.getByRole("alert")).toHaveCount(0);
        expect(analyses).toBe(1);
        await page.getByRole("button", { name: "Analyze document", exact: true }).click();
        await expect(page.getByRole("status")).toHaveText("Analysis available. Review the summary and proposed steps below.");
        await expect(page.getByText("Highest reported risk: critical", { exact: true })).toBeVisible();
        const analysis = page.locator("section").filter({ has: page.getByRole("heading", { name: "Analysis", exact: true }) });
        await expect(analysis.getByText("critical", { exact: true })).toHaveClass([/text-red-300/, /text-red-300/]);
        await expect(page.getByText("Planner requests approval", { exact: true })).toBeVisible();
        expect(analyses).toBe(2);
        expect(unexpected).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (failure === "shape" && width !== 320) {
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-readable-forge-risk-${width}.png`, fullPage: true });
        }
    });
}
