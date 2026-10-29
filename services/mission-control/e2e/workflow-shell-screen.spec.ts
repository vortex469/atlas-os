import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 1280]) {
    test(`workflow setup loading and recovery fit at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let releasePlanningRead!: () => void;
        const planningRead = new Promise<void>((resolve) => { releasePlanningRead = resolve; });
        let readCount = 0;

        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/candidate-planning/layout-session", async (route) => {
            readCount += 1;
            await planningRead;
            await route.fulfill({ status: 404, json: { detail: "Planning session is not available in this fixture." } });
        });
        await page.goto("/candidate-planning/layout-session/workflow");

        const loadingMessage = page.getByText("Loading workflow summary…", { exact: true });
        await expect(loadingMessage).toBeVisible();
        const loadingPadding = await loadingMessage.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(loadingPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(loadingPadding ?? "0px")).toBeGreaterThan(16);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        releasePlanningRead();
        const recoveryAlert = page.getByRole("alert");
        await expect(recoveryAlert).toContainText("Workflow summary unavailable");
        await expect(recoveryAlert).toContainText("Atlas couldn’t load the workflow setup. Check the planning session before trying again.");
        const technicalDetails = recoveryAlert.locator("details");
        await expect(technicalDetails).not.toHaveAttribute("open");
        await expect(technicalDetails).toContainText("Planning session was not found.");
        await expect(technicalDetails.getByText("Planning session was not found.", { exact: true })).toBeHidden();
        await expect(recoveryAlert.getByRole("link", { name: "Back to planning session" })).toBeVisible();
        const recoveryPadding = await recoveryAlert.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(recoveryPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(recoveryPadding ?? "0px")).toBeGreaterThan(16);
        }
        expect(readCount).toBe(1);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
