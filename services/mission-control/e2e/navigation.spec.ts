import { expect, test } from "./mission-control-fixtures";

const routes = [
    {
        label: "Mission Control",
        path: "/",
        assertion: async (page) => {
            await expect(page.getByRole("main", { name: "Mission Control" })).toBeVisible();
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
