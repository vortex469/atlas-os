import { expect, test } from "./mission-control-fixtures";

test("Mission Control application shell renders with primary navigation", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Mission Control 2.0").first()).toBeVisible();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
    await expect(page.getByText("browser-regression-baseline")).toBeVisible();
    await expect(page.getByText("Mission Control command center", { exact: true })).toHaveCount(1);

    await expect(page.getByRole("link", { name: "Mission Control" })).toHaveAttribute("href", "/");
    await expect(page.getByRole("link", { name: "Operations" })).toHaveAttribute("href", "/operations");
    await expect(page.getByRole("link", { name: "Operational History" })).toHaveAttribute("href", "/operations/history");
    await expect(page.getByRole("link", { name: "Maintenance" })).toHaveAttribute("href", "/operations/request");
    await expect(page.getByRole("link", { name: "Discovery" })).toHaveAttribute("href", "/discovery");
    await expect(page.getByRole("link", { name: "Execution Candidates" })).toHaveAttribute("href", "/execution-candidates");
    await expect(page.getByRole("link", { name: "Workflows" })).toHaveAttribute("href", "/workflows");
    await expect(page.getByRole("link", { name: "Forge" })).toHaveAttribute("href", "/forge");

    await expect(page.getByText("Knowledge").locator("..")).toContainText("Soon");
    await expect(page.getByText("Developer").locator("..")).toContainText("Soon");
    await expect(page.getByText("Settings").locator("..")).toContainText("Soon");
});

test("Mission Control dashboard loads from controlled Core and Agent responses", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Baseline browser fixture: Atlas presentation data loaded.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflow Inbox" })).toBeVisible();
    await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
    await expect(page.getByRole("link", { name: "View Execution Candidates" })).toHaveAttribute("href", "/execution-candidates");
    await expect(page.getByRole("heading", { name: "Atlas Agent" })).toBeVisible();
    await expect(page.getByText("Working tree clean")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Providers" })).toBeVisible();
    await expect(page.getByText("Proxmox").first()).toBeVisible();
});

test.describe("Mobile navigation", () => {
    test.use({
        viewport: { width: 320, height: 844 },
    });

    test("mobile navigation opens, closes, and stays reachable at narrow widths", async ({ page }) => {
        await page.goto("/");

        await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
        await expect(page.getByRole("dialog")).toHaveCount(0);

        await page.getByRole("button", { name: "Open navigation" }).click();

        const dialog = page.getByRole("dialog", { name: "Mission Control navigation" });
        await expect(dialog).toBeVisible();
        for (const label of [
            "Mission Control",
            "Operations",
            "Operational History",
            "Maintenance",
            "Discovery",
            "Execution Candidates",
            "Workflows",
            "Forge",
        ]) {
            await expect(dialog.getByRole("link", { name: label })).toBeVisible();
        }

        await page.getByRole("button", { name: "Close navigation" }).click();
        await expect(page.getByRole("dialog")).toHaveCount(0);

        // The main content stays reachable and unobstructed at narrow widths.
        await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
        await expect(page.getByLabel("Current page: Mission Control")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });

    test("mobile links preserve history and resize clears the drawer", async ({ page }) => {
        await page.goto("/forge");
        const trigger = page.getByRole("button", { name: "Open navigation" });
        await trigger.click();
        await page.getByRole("dialog").getByRole("link", { name: "Discovery" }).click();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(page.getByLabel("Current page: Discovery")).toBeVisible();
        await trigger.click();
        await page.goBack();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(page.getByLabel("Current page: Forge")).toBeVisible();
        await page.goForward();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await trigger.click();
        await page.setViewportSize({ width: 1280, height: 800 });
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(page.getByRole("complementary", { name: "Primary sidebar" })).toBeVisible();
        expect(await page.evaluate(() => document.body.style.overflow)).toBe("");
        await page.setViewportSize({ width: 320, height: 844 });
        await expect(trigger).toBeVisible();
        await expect(page.getByRole("dialog")).toHaveCount(0);
    });

    test("mobile navigation closes on Escape with focus returned to the trigger", async ({ page }) => {
        await page.goto("/");

        const trigger = page.getByRole("button", { name: "Open navigation" });
        await trigger.focus();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("dialog")).toBeVisible();

        const dialog = page.getByRole("dialog");
        await dialog.getByRole("button", { name: "Close navigation" }).focus();
        await page.keyboard.press("Shift+Tab");
        await expect(dialog.getByRole("link", { name: "Forge" })).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(dialog.getByRole("button", { name: "Close navigation" })).toBeFocused();
        await page.keyboard.press("Escape");

        await expect(page.getByRole("dialog")).toHaveCount(0);
        await expect(trigger).toBeFocused();
    });
});

test.describe("Atlas Core unavailable", () => {
    test.use({ mockMode: "core-unavailable" });

    test("renders the unavailable state safely", async ({ page }) => {
        await page.goto("/");

        await expect(page.getByRole("alert").filter({ hasText: "Atlas Core unavailable" })).toBeVisible();
        await expect(page.getByText("Mission Control could not retrieve the latest state from Atlas Core.")).toBeVisible();
        await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
        await expect(page.getByText("Release unavailable", { exact: true })).toBeVisible();
    });
});
