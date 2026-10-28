import { expect, test } from "./mission-control-fixtures";

for (const width of [390, 1280]) {
    test(`action history explains its date and display time zones at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/operations");

        await expect(page.getByRole("heading", { name: "Action History", exact: true })).toBeVisible();
        await expect(page.getByText("Dates cover UTC days. Entry times use your browser’s local time.", { exact: true })).toBeVisible();
        await expect(page.getByLabel("From date")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        await expect(page.getByLabel("To date")).toHaveAttribute("aria-describedby", "audit-date-filter-help");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
