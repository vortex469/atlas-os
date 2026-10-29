import { expect, test } from "@playwright/test";

for (const width of [390, 1280]) {
    test(`Forge keeps analysis tied to current input at ${width}px`, async ({ page, baseURL }) => {
        const origin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
        let reads = 0;
        let unavailable = false;
        const unexpected: string[] = [];
        // This isolated fixture permits only the simulated analysis POST.
        // The shared GET-only fixture continues to reject every mutation.
        await page.route("**/*", (route) => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin !== origin || request.method() !== "GET") {
                unexpected.push(`${request.method()} ${url.pathname}`);
                return route.abort();
            }
            if (url.pathname === "/api/v1") return route.fulfill({ json: { release: "fixture" } });
            if (url.pathname.startsWith("/api/v1/") || url.pathname.startsWith("/agent-api/")) {
                return route.fulfill({ status: url.pathname.endsWith("/operator-auth/session") ? 401 : 404, json: { detail: "Unavailable in analysis fixture." } });
            }
            return route.continue();
        });
        await page.route("**/api/v1/analysis/deployments", async (route) => {
            const request = route.request();
            const body = request.postDataJSON();
            expect(new URL(request.url()).origin).toBe(origin);
            expect(request.method()).toBe("POST");
            expect(body).toEqual({ source: "compose", reference: reads === 0 ? "first-analysis" : "current-analysis",
                document: { services: { web: { image: "example.invalid/fixture:one" } } } });
            reads += 1;
            if (unavailable) return route.fulfill({ status: 503, json: { detail: "Analysis unavailable" } });
            return route.fulfill({ json: { result: {
                analysis: { analyzer: "fixture", elapsed_ms: 1, diagnostics: [], plan: {
                    id: "fixture-plan", name: body.reference, source: "compose", components: [{
                        id: "web", name: "web", kind: "service", image: "example.invalid/fixture:one",
                        ports: [
                            { host_port: 8080, container_port: 80, protocol: "tcp", public: true },
                            { host_port: null, container_port: 443, protocol: "tcp", public: false },
                        ],
                    }], risk: "low", requires_approval: true,
                } },
                planning: { planner: "fixture", elapsed_ms: 1, warnings: [], proposal: {
                    id: "fixture-proposal", summary: "Review this simulated analysis.", steps: [],
                    risk: body.reference === "current-analysis" ? "critical" : "low", approval_required: false,
                    rollback_supported: false, estimated_duration_minutes: null,
                } },
            } } });
        });
        await page.setViewportSize({ width, height: 844 });
        await page.goto("/forge");
        await page.getByLabel("Deployment name").fill("first-analysis");
        await page.getByLabel("Docker Compose file").fill("services:\n  web:\n    image: example.invalid/fixture:one\n");
        await page.getByRole("button", { name: "Analyze Deployment" }).click();
        await expect(page.getByText("first-analysis", { exact: true }).first()).toBeVisible();
        await page.getByLabel("Deployment name").fill("current-analysis");
        await expect(page.getByRole("heading", { name: "Deployment Brief" })).toHaveCount(0);
        unavailable = true;
        await page.getByRole("button", { name: "Analyze Deployment" }).click();
        await expect(page.getByRole("alert")).toBeVisible();
        await expect(page.getByRole("heading", { name: "Deployment Brief" })).toHaveCount(0);
        unavailable = false;
        await page.getByRole("button", { name: "Analyze Deployment" }).click();
        await expect(page.getByText("current-analysis", { exact: true }).first()).toBeVisible();
        await expect(page.getByText("Highest reported risk: critical", { exact: true })).toBeVisible();
        await expect(page.getByText("Planner does not request approval", { exact: true })).toBeVisible();
        await expect(page.getByText("Not estimated", { exact: true }).first()).toBeVisible();
        await expect(page.getByText("0 minutes", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("heading", { name: "Network ports" })).toBeVisible();
        await expect(page.getByText("Host port 8080 → service port 80/TCP", { exact: true })).toBeVisible();
        await expect(page.getByText("The binding may accept connections from other computers.", { exact: true })).toBeVisible();
        await expect(page.getByText("No fixed host port was specified in this file → service port 443/TCP", { exact: true })).toBeVisible();
        await expect(page.getByText("Access from other computers was not reported.", { exact: true })).toBeVisible();
        await expect(page.getByText("Public", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Internal", { exact: true })).toHaveCount(0);
        await expect(page.getByRole("alert")).toHaveCount(0);
        await expect(page.getByRole("button", { name: /approve|execute|deploy now/i })).toHaveCount(0);
        expect(reads).toBe(3);
        expect(unexpected).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}
