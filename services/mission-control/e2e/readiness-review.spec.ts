import { expect, test } from "./mission-control-fixtures";
import { fp, readinessGatedFixture, uuid4 } from "../src/test/installationReadinessReview";

for (const width of [390, 1280]) {
    test(`readiness review loads owner evidence without mutation controls at ${width}px`, async ({ page }) => {
        let reviewReads = 0;
        const evidenceReads: string[] = [];
        await page.route("**/api/v1/operator-auth/session", (route) => route.fulfill({
            json: { authenticated: true, expires_at: "2999-01-01T00:00:00Z", principal: {
                operator_id: "operator-a", authenticated_at: "2026-08-27T12:00:00Z", permissions: [], auth_method: "core_session",
            } }, headers: { "x-atlas-csrf-token": "fixture-only-csrf" },
        }));
        await page.route(`**/api/v1/installation/candidate-records/${uuid4}/**`, (route) => {
            expect(route.request().method()).toBe("GET");
            const path = new URL(route.request().url()).pathname.split("/").at(-1);
            if (path === "readiness-review") {
                reviewReads += 1;
                return reviewReads === 1
                    ? route.fulfill({ status: 503, json: { detail: "Temporarily unavailable." } })
                    : route.fulfill({ json: readinessGatedFixture });
            }
            evidenceReads.push(path!);
            if (path === "execution-permission-grants") return route.fulfill({ json: {
                grants: [], evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false,
            } });
            if (path === "execution-admissions") return route.fulfill({ json: {
                admissions: [], evidence_only: true, execution_start_allowed: false, runner_binding_allowed: false,
                execution_authorized: false, installation_allowed: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false,
            } });
            if (path === "runner-binding-plans") return route.fulfill({ json: {
                schema: "runner-binding-plan-collection-v1", plans: [], evidence_only: true, execution_authorized: false, mutation_allowed: false,
            } });
            return route.fulfill({ status: 404, json: { detail: "No optional evidence in fixture." } });
        });
        await page.setViewportSize({ width, height: 844 });
        await page.goto(`/installation/candidate-records/${uuid4}/readiness-review`);
        await expect(page.getByRole("heading", { name: "Review unavailable", exact: true })).toBeVisible();
        await page.getByRole("button", { name: "Reload review", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Readiness gated", exact: true })).toBeVisible();
        await expect(page.getByText("Evidence is recorded, but Atlas has not defined execution admission for this installation.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Evidence reviewed", exact: true })).toBeVisible();
        await expect(page.getByRole("list", { name: "Installation evidence chain" }).getByRole("listitem")).toHaveCount(14);
        await expect(page.getByText(uuid4, { exact: true }).first()).toBeHidden();
        await expect(page.getByText(fp.value, { exact: true }).first()).toBeHidden();
        await expect(page.getByText("execution_admission_not_defined", { exact: true })).toBeHidden();
        await page.getByText("Review record details", { exact: true }).click();
        await page.getByText("Blocker codes", { exact: true }).click();
        await expect(page.getByText("execution_admission_not_defined", { exact: true })).toBeVisible();
        await expect(page.getByText("Technical review details", { exact: true })).toBeVisible();
        await page.getByText("Technical review details", { exact: true }).click();
        await expect(page.getByRole("heading", { name: "Required linkage and fingerprints", exact: true })).toBeVisible();
        await expect(page.getByText("No execution permission evidence has been recorded.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Review unavailable", exact: true })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /record|approve|install|execute|start|deploy/i })).toHaveCount(0);
        await expect(page.getByRole("complementary", { name: "Read-only authority boundary" })).toBeVisible();
        await expect(page.getByLabel("Read-only authority boundary")).toContainText("Evidence review only. This page does not authorize installation or execution.");
        expect(evidenceReads).toContain("execution-permission-grants");
        expect(reviewReads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}
