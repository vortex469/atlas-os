import { expect, test } from "./mission-control-fixtures";

const routes = [
    {
        label: "Mission Control",
        path: "/",
        assertion: async (page) => {
            await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
        },
    },
    {
        label: "Operations",
        path: "/operations",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Action History" })).toBeVisible();
        },
    },
    {
        label: "Operational History",
        path: "/operations/history",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Operational workflow history" })).toBeVisible();
        },
    },
    {
        label: "Maintenance",
        path: "/operations/request",
        expectedPath: "/operator/login",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Operator login" })).toBeVisible();
        },
    },
    {
        label: "Discovery",
        path: "/discovery",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Provider-neutral catalog" })).toBeVisible();
            await expect(page.getByText("Fixture Application")).toBeVisible();
        },
    },
    {
        label: "Execution Candidates",
        path: "/execution-candidates",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Candidate planning intake" })).toBeVisible();
            await expect(page.getByText("candidate-browser-baseline")).toBeVisible();
        },
    },
    {
        label: "Workflows",
        path: "/workflows",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();
            await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
        },
    },
    {
        label: "Forge",
        path: "/forge",
        assertion: async (page) => {
            await expect(page.getByRole("heading", { name: "Atlas Forge" })).toBeVisible();
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
        await page.getByRole("link", { name: route.label }).click();

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
