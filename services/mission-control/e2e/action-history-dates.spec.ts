import { expect, test } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test(`action history explains its date and display time zones at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/operations");

        await expect(page.getByRole("heading", { name: "Action history", exact: true })).toBeVisible();
        await expect(page.getByText("Atlas is keeping 0 of 5000 entries for up to 90 days.", { exact: true })).toBeVisible();
        await expect(page.getByText("Completed actions and their results. Times use your local time.", { exact: true })).toBeVisible();
        await expect(page.getByText("Atlas has not recorded any actions yet.", { exact: true })).toBeVisible();
        await expect(page.getByLabel("From date")).toBeHidden();
        await expect(page.getByLabel("Provider")).toBeHidden();
        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByLabel("From date")).toBeVisible();
        await expect(page.getByLabel("Provider")).toBeVisible();
        await expect(page.getByText("Selected dates cover full UTC days.", { exact: true })).toBeVisible();
        await expect(page.getByLabel("From date")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        await expect(page.getByLabel("To date")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
