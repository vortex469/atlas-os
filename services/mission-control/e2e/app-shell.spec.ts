import { expect, test } from "./mission-control-fixtures";

test("Mission Control application shell renders with primary navigation", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("Operating Console")).toBeVisible();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
    await expect(page.getByText("browser-regression-baseline")).toBeVisible();

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

test.describe("Atlas Core unavailable", () => {
    test.use({ mockMode: "core-unavailable" });

    test("renders the unavailable state safely", async ({ page }) => {
        await page.goto("/");

        await expect(page.getByRole("alert").filter({ hasText: "Atlas Core unavailable" })).toBeVisible();
        await expect(page.getByText("Mission Control could not retrieve the latest state from Atlas Core.")).toBeVisible();
        await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
    });
});
