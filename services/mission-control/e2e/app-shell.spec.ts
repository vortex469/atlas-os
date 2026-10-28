import { expect, test } from "./mission-control-fixtures";

test("Mission Control application shell renders with primary navigation", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Mission Control 2.0").first()).toBeVisible();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
    await expect(page.getByText("browser-regression-baseline")).toBeVisible();
    await expect(page.getByText("Mission Control command center", { exact: true })).toHaveCount(1);

    await expect(page.getByRole("link", { name: "Mission Control", exact: true })).toHaveAttribute("href", "/");
    await expect(page.getByRole("link", { name: "Action history", exact: true })).toHaveAttribute("href", "/operations");
    await expect(page.getByRole("link", { name: "Maintenance history", exact: true })).toHaveAttribute("href", "/operations/history");
    await expect(page.getByRole("link", { name: "Request maintenance", exact: true })).toHaveAttribute("href", "/operations/request");
    await expect(page.getByRole("link", { name: "Discovery", exact: true })).toHaveAttribute("href", "/discovery");
    await expect(page.getByRole("link", { name: "Change proposals", exact: true })).toHaveAttribute("href", "/execution-candidates");
    await expect(page.getByRole("link", { name: "Workflows", exact: true })).toHaveAttribute("href", "/workflows");
    await expect(page.getByRole("link", { name: "Forge", exact: true })).toHaveAttribute("href", "/forge");

    const navigation = page.getByRole("navigation", { name: "Primary" }).first();
    for (const unavailable of ["Knowledge", "Developer", "Settings", "Soon"]) {
        await expect(navigation.getByText(unavailable)).toHaveCount(0);
    }
});

test("Mission Control dashboard loads from controlled Core and Agent responses", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Operator Attention" })).toBeVisible();
    await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
    await expect(page.getByRole("link", { name: "Inspect executions →", exact: true })).toHaveAttribute("href", "/workflows");
    await expect(page.getByRole("heading", { name: "Agent state" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent Activity" })).toBeVisible();
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
            "Action history",
            "Maintenance history",
            "Request maintenance",
            "Discovery",
            "Change proposals",
            "Workflows",
            "Forge",
        ]) {
            await expect(dialog.getByRole("link", { name: label, exact: true })).toBeVisible();
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
        await page.getByRole("dialog").getByRole("link", { name: "Discovery", exact: true }).click();
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
        await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe("");
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
        await expect(dialog.getByRole("link", { name: "Forge", exact: true })).toBeFocused();
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

        await expect(page.getByRole("region", { name: "Atlas overall state" })).toContainText("Evidence unavailable.");
        await expect(page.getByRole("region", { name: "Atlas overall state" })).toContainText("Unknown");
        await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeVisible();
        await expect(page.getByText("Release unavailable", { exact: true })).toBeVisible();
    });
});

for (const width of [390, 1280]) {
    test(`keyboard users can skip navigation at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 844 });
        await page.goto("/providers?view=all");
        await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
        await page.keyboard.press("Tab");
        const skip = page.getByRole("link", { name: "Skip to page content" });
        await expect(skip).toBeFocused();
        await expect(skip).toBeInViewport();
        await page.keyboard.press("Enter");
        await expect(page.locator("#mc-page-content")).toBeFocused();
        await expect(page).toHaveURL(/\/providers\?view=all$/);
        await page.keyboard.press("Tab");
        expect(await page.evaluate(() => Boolean(document.activeElement?.closest("#mc-page-content")))).toBe(true);
    });
}
