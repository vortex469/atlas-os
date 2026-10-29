import { expect, test } from "@playwright/test";
import { journey } from "./repository-journey-fixture";
import { installMaintenanceRequestJourney } from "./maintenance-request-journey-fixture";
import { capability } from "./maintenance-selector-fixture";

for (const width of [320, 1280]) {
    test(`maintenance request restores the operator session at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installMaintenanceRequestJourney(page, baseURL);
        let releaseSessionRead!: () => void;
        const sessionRead = new Promise<void>((resolve) => { releaseSessionRead = resolve; });
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/api/v1/operator-auth/session", async (route) => {
            await sessionRead;
            await route.fulfill({ status: 401, json: { detail: "Sign in required." } });
        });
        await page.goto("/operations/request");

        const loadingMessage = page.getByText("Restoring operator session…", { exact: true });
        await expect(loadingMessage).toBeVisible();
        const padding = await loadingMessage.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(padding).toBe("16px");
        } else {
            expect(Number.parseFloat(padding ?? "0px")).toBeGreaterThan(16);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        releaseSessionRead();
        await page.waitForURL(/\/operator\/login$/);
        expect(fixture.entryWrites).toEqual([]);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        expect(fixture.entryUnexpected).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`maintenance request through audit keeps approval and execution separate at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installMaintenanceRequestJourney(page, baseURL);
        await page.setViewportSize({ width, height: 844 });
        await page.goto("/operations/request");
        await page.getByLabel("Operator ID").fill("browser-operator");
        await page.getByLabel("Password").fill("fixture-only-password");
        await page.getByRole("button", { name: "Sign in", exact: true }).click();
        const requestHeading = page.getByRole("heading", { name: "Request a restart proposal", exact: true });
        await expect(requestHeading).toBeVisible();
        const requestPadding = await requestHeading.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(requestPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(requestPadding ?? "0px")).toBeGreaterThan(16);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await expect(page.getByText("VM type", { exact: true })).toBeVisible();
        const target = page.getByRole("radio", { name: /Browser fixture VM/ });
        const targetCard = page.locator("label").filter({ has: target });
        await expect(targetCard).toContainText("VM ID 110");
        await expect(targetCard).toContainText("Host fixture-node");
        await expect(target).not.toBeChecked();
        await expect(page.getByRole("button", { name: "Request restart proposal" })).toBeDisabled();
        expect(fixture.entryWrites).toHaveLength(1);
        expect(fixture.writes).toHaveLength(0);
        await target.check();
        await page.getByRole("button", { name: "Request restart proposal" }).click();
        await expect(page.getByRole("heading", { name: "Restart proposal ready for review" })).toBeVisible();
        expect(fixture.entryWrites).toEqual(fixture.expectedEntryWrites);
        expect(fixture.writes).toHaveLength(0);
        await page.getByRole("link", { name: "Review restart proposal" }).click();
        await expect(page).toHaveURL(new RegExp(`/execution-candidates/${journey.candidate}$`));
        const progress = page.getByRole("region", { name: "Planning progress" });
        await expect(progress.locator('[aria-current="step"]')).toHaveText("ProposalCurrent step");
        await expect(progress.getByRole("listitem")).toHaveCount(4);
        await page.getByRole("button", { name: "Start planning", exact: true }).click();
        await page.getByRole("link", { name: "Continue planning", exact: true }).click();
        await page.getByRole("button", { name: "Generate Plan", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Maintenance plan", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Candidate plan", exact: true })).toHaveCount(0);
        await expect(page.getByText("Proxmox virtual machine 110", { exact: true })).toBeVisible();
        const planReferences = page.getByText("Plan references", { exact: true });
        await planReferences.click();
        await expect(page.getByText("proxmox/qemu/110", { exact: true })).toBeVisible();
        await planReferences.click();
        await expect(progress.locator('[aria-current="step"]')).toHaveText("PlanCurrent step");
        await expect(progress).not.toContainText("Commit");
        expect(fixture.repositoryPlanReads).toBe(0);
        await page.getByRole("button", { name: "Create Workflow", exact: true }).click();
        await page.getByRole("link", { name: "Open Workflow", exact: true }).click();
        await expect(progress.locator('[aria-current="step"]')).toHaveText("WorkflowCurrent step");
        await expect(progress.getByRole("listitem")).toHaveCount(4);
        await page.getByRole("button", { name: "Prepare change for review", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Maintenance request", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Review maintenance request", exact: true })).toBeVisible();
        await expect(page.getByText("Maintenance request needs approval.", { exact: true })).toBeVisible();
        await expect(page.getByText("Proxmox virtual machine 110", { exact: true })).toBeVisible();
        const supportFile = page.getByText("Optional support file", { exact: true });
        const supportDetails = supportFile.locator("xpath=ancestor::details");
        await expect(supportDetails).not.toHaveAttribute("open");
        await supportFile.click();
        await expect(supportDetails).toContainText("Prepare a sanitized support file to review.");
        await expect(supportDetails.getByRole("button", { name: "Prepare support file", exact: true })).toBeVisible();
        expect(fixture.writes).toHaveLength(5);
        const requestReferences = page.getByText("Request references", { exact: true });
        await requestReferences.click();
        await expect(
            requestReferences.locator("xpath=ancestor::details").getByText("proxmox/qemu/110", { exact: true }),
        ).toBeVisible();
        await requestReferences.click();
        await expect(page.getByRole("button", { name: "Approve maintenance request", exact: true })).toBeEnabled();
        await expect(page.getByRole("button", { name: "Run approved maintenance", exact: true })).toHaveCount(0);
        expect(fixture.writes).toHaveLength(5);
        await page.getByRole("button", { name: "Approve maintenance request", exact: true }).click();
        await expect(page.getByRole("button", { name: "Run approved maintenance", exact: true })).toBeEnabled();
        expect(fixture.writes).toHaveLength(6);
        await page.getByRole("button", { name: "Run approved maintenance", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Verified", exact: true })).toBeVisible();
        const statusSummary = page.getByRole("region", { name: "Maintenance status summary" });
        await expect(statusSummary.getByRole("heading", { name: "Healthy", exact: true })).toBeVisible();
        const diagnosticEvidence = statusSummary.locator("details");
        await expect(diagnosticEvidence).not.toHaveAttribute("open");
        await expect(diagnosticEvidence.getByText("Target fingerprint", { exact: true })).toBeHidden();
        await expect(page.getByRole("heading", { name: "Maintenance progress", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Execution timeline", exact: true })).toHaveCount(0);
        const maintenanceStatus = page.getByRole("region", { name: "Maintenance status" });
        await expect(maintenanceStatus.getByText("Technical evidence", { exact: true })).toBeVisible();
        const technicalEvidence = maintenanceStatus.locator("details").filter({ hasText: "Technical evidence" });
        await expect(technicalEvidence).not.toHaveAttribute("open");
        await expect(technicalEvidence.getByText("Workflow ID", { exact: true })).toBeHidden();
        const maintenanceStages = page.getByRole("list", { name: "Maintenance workflow stages" });
        await expect(maintenanceStages.getByText("Maintenance request approval", { exact: true })).toBeVisible();
        await expect(maintenanceStages.getByText("Run maintenance", { exact: true })).toBeVisible();
        await expect(maintenanceStages.getByRole("listitem")).toHaveCount(7);
        await expect(maintenanceStages.getByText("Review", { exact: true })).toHaveCount(0);
        await expect(maintenanceStages.getByText("Commit", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Maintenance workflow completed. Review the recorded operational outcome.", { exact: true })).toBeVisible();
        await expect(page.getByRole("button", { name: /Approve Verification|Approve Commit|Run approved maintenance/ })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(fixture.repositoryPlanReads).toBe(0);
        expect(fixture.writes).toEqual(fixture.expectedWrites);
        await page.getByRole("link", { name: "Open Audit", exact: true }).click();
        const auditHeading = page.getByRole("heading", { name: "Maintenance audit", exact: true });
        await expect(auditHeading).toBeVisible();
        await expect(page.getByRole("heading", { name: "Verified", exact: true })).toBeVisible();
        const auditMaintenanceStatus = page.getByRole("region", { name: "Maintenance status" });
        const auditTechnicalEvidence = auditMaintenanceStatus.locator("details");
        await expect(auditTechnicalEvidence).not.toHaveAttribute("open");
        await expect(auditTechnicalEvidence.getByText("Workflow ID", { exact: true })).toBeHidden();
        await expect(auditMaintenanceStatus.getByText("Diagnostic evidence", { exact: true })).toHaveCount(0);
        await expect(page.getByText(/Maintenance status:/)).toContainText("Maintenance workflow completed.");
        await expect(page.getByRole("heading", { name: "Commit Request", exact: true })).toHaveCount(0);
        const auditPadding = await auditHeading.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(auditPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(auditPadding ?? "0px")).toBeGreaterThan(16);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(fixture.writes).toEqual(fixture.expectedWrites);
        expect(fixture.unexpected).toEqual([]);
        expect(fixture.entryUnexpected).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`locks the request screen after an unconfirmed proposal response at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installMaintenanceRequestJourney(page, baseURL);
        await page.setViewportSize({ width, height: 844 });
        let proposalRequests = 0;
        await page.route("**/api/v1/execution-candidates/operator-intents", async (route) => {
            if (route.request().method() === "POST") {
                proposalRequests += 1;
                return route.fulfill({ status: 503, json: { detail: "fixture-only unavailable" } });
            }
            return route.fallback();
        });

        await page.goto("/operations/request");
        await page.getByLabel("Operator ID").fill("browser-operator");
        await page.getByLabel("Password").fill("fixture-only-password");
        await page.getByRole("button", { name: "Sign in", exact: true }).click();
        await page.getByRole("radio", { name: /Browser fixture VM/ }).check();
        await page.getByRole("button", { name: "Request restart proposal" }).click();

        await expect(page.getByRole("alert")).toContainText("Check proposals before trying again.");
        await expect(page.getByRole("link", { name: "Check whether a proposal was created" })).toHaveAttribute("href", "/execution-candidates");
        await expect(page.getByRole("radio", { name: /Browser fixture VM/ })).toBeDisabled();
        await expect(page.getByRole("button", { name: "Refresh" })).toBeDisabled();
        await expect(page.getByRole("button", { name: "Request restart proposal" })).toBeDisabled();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(proposalRequests).toBe(1);
        expect(fixture.entryWrites).toEqual(["/operator-auth/login"]);
        expect(fixture.entryUnexpected).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`explains when the maintenance resource list is empty at ${width}px`, async ({ page, baseURL }) => {
        const fixture = await installMaintenanceRequestJourney(page, baseURL);
        await page.setViewportSize({ width, height: 844 });
        let resourceReads = 0;
        await page.route(`**/api/v1/execution-candidates/operator-intents/capabilities/${capability.selector_id}/resources`, async (route) => {
            if (route.request().method() === "GET") {
                resourceReads += 1;
                return route.fulfill({ json: {
                    execution_intent: "restart-service",
                    provider_id: "proxmox",
                    resource_type: "qemu",
                    generated_at: "2026-10-26T00:00:00Z",
                    resources: [],
                } });
            }
            return route.fallback();
        });

        await page.goto("/operations/request");
        await page.getByLabel("Operator ID").fill("browser-operator");
        await page.getByLabel("Password").fill("fixture-only-password");
        await page.getByRole("button", { name: "Sign in", exact: true }).click();

        await expect(page.getByText("No VMs are available to select right now. Use Refresh to check again.")).toBeVisible();
        await expect(page.getByRole("button", { name: "Refresh" })).toBeEnabled();
        await expect(page.getByRole("button", { name: "Request restart proposal" })).toBeDisabled();
        await expect(page.getByRole("radio")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.getByRole("button", { name: "Refresh" }).click();
        await expect.poll(() => resourceReads).toBe(2);
        expect(fixture.entryWrites).toEqual(["/operator-auth/login"]);
        expect(fixture.writes).toEqual([]);
        expect(fixture.entryUnexpected).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
    });
}
