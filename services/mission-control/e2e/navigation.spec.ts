import { expect, test } from "./mission-control-fixtures";

const routes = [
    {
        label: "Overview",
        path: "/",
        assertion: async (page) => {
            await expect(page.getByRole("main", { name: "Overview" })).toBeVisible();
        },
    },
    {
        label: "Action history",
        path: "/operations",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Action History" })).toBeVisible();
        },
    },
    {
        label: "Maintenance history",
        path: "/operations/history",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Maintenance history" })).toBeVisible();
        },
    },
    {
        label: "Request maintenance",
        path: "/operations/request",
        expectedPath: "/operator/login",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Operator login" })).toBeVisible();
        },
    },
    {
        label: "Catalog",
        path: "/discovery",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Browse the catalog" })).toBeVisible();
            await expect(page.getByText("Fixture Application")).toBeVisible();
        },
    },
    {
        label: "Change proposals",
        path: "/execution-candidates",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Change proposals" })).toBeVisible();
            await expect(page.getByRole("link", { name: "Review Update Compose Stack proposal" })).toBeVisible();
        },
    },
    {
        label: "Workflows",
        path: "/workflows",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        },
    },
    {
        label: "Deployment analysis",
        path: "/forge",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Deployment analysis" })).toBeVisible();
        },
    },
] satisfies Array<{
    label: string;
    path: string;
    expectedPath?: string;
    assertion: (page: import("@playwright/test").Page) => Promise<void>;
}>;

for (const route of routes) {
    test(`enabled primary navigation reaches ${route.label}`, async ({ page }) => {
        await page.goto("/");
        await page.getByRole("link", { name: route.label, exact: true }).click();

        await expect(page).toHaveURL(new RegExp(`${route.expectedPath ?? route.path}(?:[?#].*)?$`));
        await route.assertion(page);
    });
}

test("operator login route remains directly reachable", async ({ page }) => {
    await page.goto("/operator/login");

    await expect(page.getByRole("heading", { name: "Operator login" })).toBeVisible();
    await expect(page.getByLabel("Operator ID")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

for (const width of [320, 390, 1280]) {
    test(`missing-page recovery stays readable at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 844 });
        await page.goto("/this-screen-does-not-exist");

        const heading = page.getByRole("heading", { name: "Page not found", exact: true });
        await expect(heading).toBeVisible();
        await expect(page.getByText("This address does not match a Mission Control screen. Use the navigation to choose a screen, or return to Mission Control.")).toBeVisible();
        await expect(page.getByText("404", { exact: true })).toHaveCount(0);
        const padding = await heading.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(padding).toBe("16px");
        } else {
            expect(Number.parseFloat(padding ?? "0px")).toBeGreaterThan(16);
        }
        const returnLink = page.getByRole("link", { name: "Return to Mission Control", exact: true });
        await expect(returnLink).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await returnLink.click();
        await expect(page.getByRole("main", { name: "Overview" })).toBeVisible();
    });
}
