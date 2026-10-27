import { expect, test } from "@playwright/test";
import { deploymentAnalysisFixture } from "../src/test/deploymentAnalysis";

for (const width of [320, 390, 1280]) for (const failure of ["syntax", "sections"] as const) {
    test(`Forge ${failure} input at ${width}px stays editable and sends only the corrected document`, async ({ page, baseURL }) => {
        await page.setViewportSize({ width, height: 900 });
        const origin = new URL(baseURL!).origin;
        let analyses = 0;
        const unexpected: string[] = [];
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
            return route.fulfill({ json: deploymentAnalysisFixture() });
        });
        await page.goto("/forge");
        await page.getByLabel("Deployment name").fill("Compose preview");
        const badCompose = failure === "syntax" ? "services:\n  web: [PUBLIC-COMPOSE-CANARY\n" : "[]";
        await page.getByLabel("Compose document").fill(badCompose);
        await page.getByRole("button", { name: "Analyze document", exact: true }).click();
        const alert = page.getByRole("alert");
        if (failure === "syntax") await expect(alert).toHaveText(/^Compose document could not be read\. Check YAML formatting near line \d+, column \d+\.$/);
        else await expect(alert).toHaveText('Use a Compose document with named sections, such as "services:".');
        await expect(alert).not.toContainText("PUBLIC-COMPOSE-CANARY");
        await expect(page.getByLabel("Compose document")).toHaveValue(badCompose);
        await expect(page.getByRole("status")).toBeEmpty();
        await expect(page.getByRole("heading", { name: "Deployment Brief", exact: true })).toHaveCount(0);
        expect(analyses).toBe(0);
        if (failure === "syntax" && width !== 320) {
            await page.evaluate(() => window.scrollTo(0, 0));
            await page.screenshot({ path: `/tmp/atlas-compose-input-error-${width}.png`, fullPage: true });
        }
        await page.getByLabel("Compose document").fill("services:\n  web:\n    image: example.invalid/fixture:one\n");
        await expect(alert).toHaveCount(0);
        expect(analyses).toBe(0);
        await page.getByRole("button", { name: "Analyze document", exact: true }).click();
        await expect(page.getByRole("status")).toHaveText("Analysis available. Review the summary and proposed steps below.");
        expect(analyses).toBe(1);
        expect(unexpected).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}
