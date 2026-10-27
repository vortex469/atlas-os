import { discoveryProposalFixture } from "../src/test/discoveryProposal.fixture";
import { homeAssistantGoldenPlan } from "../src/test/installationPlan.fixture";
import { expect, test, discoveryItemsPage } from "./mission-control-fixtures";

for (const width of [320, 390, 1280]) {
    test.describe(`Discovery recovery at ${width}px`, () => {
        test.use({ viewport: { width, height: 900 } });
        test("retries submitted search without showing old results or applying draft edits", async ({ page, rejectedMutationRequests }) => {
            const queries: string[] = [];
            const typeQueries: Array<string | null> = [];
            let itemReads = 0;
            let summaryReads = 0;
            page.on("request", request => {
                const path = new URL(request.url()).pathname;
                if (path === "/api/v1/discovery/items") itemReads += 1;
                if (path === "/api/v1/discovery") summaryReads += 1;
            });
            await page.route("**/api/v1/discovery/search**", async route => {
                expect(route.request().method()).toBe("GET");
                queries.push(new URL(route.request().url()).searchParams.get("q")!);
                typeQueries.push(new URL(route.request().url()).searchParams.get("type"));
                if (queries.length === 1) return route.fulfill({ status: 503, json: { detail: "Search temporarily unavailable." } });
                const entry = { ...discoveryItemsPage.entries[0], item: { ...discoveryItemsPage.entries[0].item, id: "redis", name: "Redis" } };
                return route.fulfill({ json: { results: [{ entry, item: entry.item, evidence: [] }], total: 1, limit: 25, offset: 0, has_more: false } });
            });
            await page.goto("/discovery");
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Browse the catalog", exact: true })).toBeVisible();
            const itemType = page.getByRole("combobox", { name: "Item type", exact: true, includeHidden: true });
            await expect(itemType).toHaveCount(1);
            await expect(itemType).toBeHidden();
            const catalogDetails = page.getByText("Catalog details", { exact: true });
            await catalogDetails.focus();
            await page.keyboard.press("Enter");
            await expect(page.getByText("v1", { exact: true })).toBeVisible();
            await page.keyboard.press("Enter");
            await expect(page.getByText("v1", { exact: true })).toBeHidden();
            const moreFilters = page.getByText("More filters", { exact: true });
            await moreFilters.focus();
            await page.keyboard.press("Enter");
            await expect(itemType).toBeVisible();
            await itemType.selectOption("application");
            await expect(page.getByText("Search to apply your changes.", { exact: true })).toBeVisible();
            await moreFilters.focus();
            await page.keyboard.press("Enter");
            await expect(itemType).toBeHidden();
            expect(itemReads).toBe(1);
            expect(summaryReads).toBe(1);
            expect(queries).toEqual([]);
            await page.evaluate(() => window.scrollTo(0, 0));
            if (width !== 320) await page.screenshot({ path: `/tmp/atlas-compact-discovery-${width}.png`, fullPage: true });
            await page.getByLabel("Keyword search").fill("redis");
            await page.getByRole("button", { name: "Search", exact: true }).click();
            await expect(page.getByText("Discovery catalog unavailable", { exact: true })).toBeVisible();
            await expect(page.getByText("Results unavailable", { exact: true })).toBeVisible();
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toHaveCount(0);
            await expect(page.getByText("1 item found", { exact: true })).toHaveCount(0);
            await expect(page.getByText("Filters applied to these results.", { exact: true })).toHaveCount(0);
            await page.getByLabel("Keyword search").fill("draft-change");
            await expect(page.getByText("Search to apply your changes.", { exact: true })).toBeVisible();
            await page.getByRole("button", { name: "Retry catalog request", exact: true }).click();
            await expect(page.getByRole("link", { name: "Redis", exact: true })).toBeVisible();
            await expect(page.getByLabel("Keyword search")).toHaveValue("draft-change");
            await expect(page.getByText("Filters applied to these results.", { exact: true })).toBeVisible();
            await expect(page.getByText("Search to apply your changes.", { exact: true })).toBeVisible();
            expect(queries).toEqual(["redis", "redis"]);
            expect(typeQueries).toEqual(["application", "application"]);
            expect(itemReads).toBe(1);
            expect(summaryReads).toBe(3);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
        });
    });
}

for (const width of [320, 390, 1280]) {
    for (const search of [false, true]) {
        test(`malformed ${search ? "search" : "list"} response recovers at ${width}px`, async ({ page, rejectedMutationRequests }) => {
            await page.setViewportSize({ width, height: 900 });
            let reads = 0;
            const errors: string[] = [];
            page.on("pageerror", error => errors.push(error.message));
            await page.route(search ? "**/api/v1/discovery/search**" : "**/api/v1/discovery/items?**", async route => {
                expect(route.request().method()).toBe("GET");
                reads += 1;
                const entry = discoveryItemsPage.entries[0];
                const entries = reads === 1 ? [{ ...entry, item: { ...entry.item, tags: [{}] } }] : [entry];
                return route.fulfill({ json: { ...discoveryItemsPage, ...(search
                    ? { results: entries.map(entry => ({ entry, item: entry.item, evidence: [] })) }
                    : { entries }) } });
            });
            await page.goto("/discovery");
            if (search) {
                await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toBeVisible();
                await page.getByLabel("Keyword search").fill("fixture");
                await page.getByRole("button", { name: "Search", exact: true }).click();
            }
            await expect(page.getByText("The catalog results could not be read. Try again.", { exact: true })).toBeVisible();
            await expect(page.getByText("Results unavailable", { exact: true })).toBeVisible();
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toHaveCount(0);
            expect(reads).toBe(1);
            await page.getByRole("button", { name: "Retry catalog request", exact: true }).click();
            await expect(page.getByRole("link", { name: "Fixture Application", exact: true })).toBeVisible();
            expect(reads).toBe(2);
            expect(errors).toEqual([]);
            expect(rejectedMutationRequests).toEqual([]);
        });
    }
}

for (const width of [320, 390, 1280]) {
    test(`malformed Discovery item recovers after reload at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        let reads = 0;
        let recovered = false;
        const errors: string[] = [];
        page.on("pageerror", error => errors.push(error.message));
        const entry = discoveryItemsPage.entries[0];
        await page.route("**/api/v1/discovery/items/fixture-app", async route => {
            reads += 1;
            return route.fulfill({ json: !recovered
                ? { ...entry, item: { ...entry.item, tags: [{}] } } : entry });
        });
        await page.goto("/discovery/items/fixture-app");
        await expect(page.getByRole("alert").filter({ hasText: "Discovery catalog unavailable" })).toContainText("The catalog item could not be read. Reload to try again.");
        await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toHaveCount(0);
        const initialReads = reads;
        expect(initialReads).toBeGreaterThan(0);
        recovered = true;
        await page.getByRole("button", { name: "Reload page", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
        expect(reads).toBe(initialReads * 2);
        const compatibilityBox = await page.getByRole("heading", { name: "Compatibility assessment", exact: true }).boundingBox();
        const evidenceBox = await page.getByRole("heading", { name: "Release evidence", exact: true }).boundingBox();
        expect(compatibilityBox!.y).toBeLessThan(evidenceBox!.y);
        const labels = page.locator("details").filter({ has: page.locator("summary", { hasText: "Capabilities and tags" }) });
        await expect(labels.getByRole("heading", { name: "Tags", exact: true })).toBeHidden();
        const toggle = labels.locator("summary");
        await toggle.focus();
        await page.keyboard.press("Enter");
        await expect(labels.getByText("browser-fixture", { exact: true })).toBeVisible();
        await expect(labels.getByText("read-only", { exact: true })).toBeVisible();
        await page.keyboard.press("Enter");
        await expect(labels.getByText("browser-fixture", { exact: true })).toBeHidden();
        expect(reads).toBe(initialReads * 2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        if (width !== 320) await page.screenshot({ path: `/tmp/atlas-compact-item-labels-${width}.png`, fullPage: true });
        expect(errors).toEqual([]);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed compatibility keeps the Discovery item readable at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const entry = discoveryItemsPage.entries[0];
        let reads = 0;
        let recovered = false;
        const errors: string[] = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/api/v1/discovery/items/fixture-app", route => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/compatibility", route => {
            reads += 1;
            expect(route.request().method()).toBe("GET");
            return route.fulfill({ json: { item_id: "fixture-app", target_id: "atlas", target_type: "atlas",
                status: "insufficient_information", checked_at: "2026-10-27T12:00:00Z",
                findings: recovered ? [] : null, evidence: [], unknown_facts: ["Host resources are unknown."] } });
        });
        await page.goto("/discovery/items/fixture-app");
        await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
        await expect(page.getByText("The compatibility result could not be read. Try again.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Compatibility status", exact: true })).toHaveCount(0);
        expect(reads).toBe(1);
        recovered = true;
        await page.getByRole("button", { name: "Retry compatibility check", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Compatibility status", exact: true })).toBeVisible();
        await expect(page.getByText("Host resources are unknown.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
        expect(reads).toBe(2);
        expect(errors).toEqual([]);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed release evidence keeps the Discovery item readable at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const entry = discoveryItemsPage.entries[0];
        let reads = 0;
        let recovered = false;
        const errors: string[] = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/api/v1/discovery/items/fixture-app", route => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/evidence", route => {
            reads += 1;
            expect(route.request().method()).toBe("GET");
            return route.fulfill({ json: { schema_version: "discovery-merged-item-v1", catalog_item_id: "fixture-app",
                curated: entry, conflict_state: "none", dynamic_claims: [], source_states: recovered ? [] : {} } });
        });
        await page.goto("/discovery/items/fixture-app");
        await expect(page.getByText("The release evidence could not be read. Reload the page to try again.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
        await expect(page.getByText("Dynamic evidence unavailable", { exact: true })).toBeVisible();
        await expect(page.getByText("No conflict", { exact: true })).toHaveCount(0);
        const initialReads = reads;
        expect(initialReads).toBeGreaterThan(0);
        recovered = true;
        await page.reload();
        await expect(page.getByText("Curated catalog only", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
        expect(reads).toBe(initialReads * 2);
        expect(errors).toEqual([]);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    for (const malformed of ["unknown status", "unsupported grounded claim"]) {
        test(`unreadable image evidence (${malformed}) keeps the Discovery item at ${width}px`, async ({ page, rejectedMutationRequests }) => {
            await page.setViewportSize({ width, height: 900 });
            const entry = discoveryItemsPage.entries[0];
            let reads = 0;
            let recovered = false;
            const errors: string[] = [];
            page.on("pageerror", error => errors.push(error.message));
            await page.route("**/api/v1/discovery/items/fixture-app", route => route.fulfill({ json: entry }));
            await page.route("**/api/v1/discovery/items/fixture-app/image-grounding", route => {
                reads += 1;
                expect(route.request().method()).toBe("GET");
                return route.fulfill({ json: { schema_version: "discovery-image-grounding-projection-v1", catalog_item_id: "fixture-app",
                    status: recovered ? "no_deployment_binding" : malformed === "unknown status" ? "future" : "grounded",
                    release_version: null, deployment_binding: null, observed_image: null, accepted_evidence: [] } });
            });
            await page.goto("/discovery/items/fixture-app");
            await expect(page.getByText("The image evidence could not be read. Reload the page to try again.", { exact: true })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
            await expect(page.getByText("Grounded", { exact: true })).toHaveCount(0);
            const initialReads = reads;
            expect(initialReads).toBeGreaterThan(0);
            recovered = true;
            await page.reload();
            await expect(page.locator("p").filter({ hasText: /^No deployment binding$/ })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Fixture Application", exact: true })).toBeVisible();
            expect(reads).toBe(initialReads * 2);
            expect(errors).toEqual([]);
            expect(rejectedMutationRequests).toEqual([]);
        });
    }
}

for (const width of [320, 390, 1280]) {
    test(`unreadable installation plan keeps the Discovery item at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        const plan = homeAssistantGoldenPlan();
        const entry = { ...discoveryItemsPage.entries[0], item: { ...discoveryItemsPage.entries[0].item, id: "home-assistant", name: "Home Assistant" } };
        let reads = 0;
        let destinationReads = 0;
        page.on("request", request => {
            if (new URL(request.url()).pathname === "/api/v1/installation/destinations") destinationReads += 1;
        });
        let recovered = false;
        const errors: string[] = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.route("**/api/v1/discovery/items/home-assistant", route => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/home-assistant/installation-plan", route => {
            reads += 1;
            expect(route.request().method()).toBe("GET");
            return route.fulfill({ json: recovered ? plan : { ...plan, blockers: null } });
        });
        await page.goto("/discovery/items/home-assistant");
        await expect(page.getByText("Installation plan is currently unavailable.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Home Assistant", exact: true })).toBeVisible();
        await expect(page.getByText("Ready for operator review only; no execution authority has been granted.", { exact: true })).toHaveCount(0);
        await expect(page.getByText(plan.fingerprint.value, { exact: true })).toHaveCount(0);
        await expect(page.getByRole("heading", { name: "Prospective installation destination", exact: true })).toHaveCount(0);
        expect(destinationReads).toBe(0);
        const initialReads = reads;
        expect(initialReads).toBeGreaterThan(0);
        recovered = true;
        await page.reload();
        await expect(page.getByText("9 unresolved blockers; this plan is not executable.", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Home Assistant", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Prospective installation destination", exact: true })).toBeVisible();
        await expect.poll(() => destinationReads).toBeGreaterThan(0);
        const planPanel = page.getByRole("region", { name: "Installation plan review", exact: true });
        const fingerprint = planPanel.getByText(plan.fingerprint.value, { exact: true });
        await expect(fingerprint).toHaveCount(1);
        await expect(fingerprint).toBeHidden();
        const disclosure = planPanel.getByText("Plan identity and evidence", { exact: true });
        for (const name of ["Blockers", "Required operator confirmations", "Risks", "Missing facts"]) {
            const heading = planPanel.getByRole("heading", { name, exact: true });
            await expect(heading).toBeVisible();
            expect((await heading.boundingBox())!.y).toBeLessThan((await disclosure.boundingBox())!.y);
        }
        const readsBeforeDetails = reads;
        const destinationsBeforeDetails = destinationReads;
        await disclosure.focus();
        await page.keyboard.press("Enter");
        await expect(fingerprint).toBeVisible();
        await expect(planPanel.getByRole("heading", { name: "Accepted evidence", exact: true })).toBeVisible();
        await page.keyboard.press("Enter");
        await expect(fingerprint).toBeHidden();
        expect(reads).toBe(readsBeforeDetails);
        expect(destinationReads).toBe(destinationsBeforeDetails);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await planPanel.evaluate(el => window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 96));
        if (width !== 320) await page.screenshot({ path: `/tmp/atlas-plan-review-after-${width}.png` });
        expect(reads).toBe(initialReads * 2);
        expect(errors).toEqual([]);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    for (const malformed of ["object reason", "string navigation flag"]) {
        test(`unreadable Discovery proposal (${malformed}) stays unavailable at ${width}px`, async ({ page, rejectedMutationRequests }) => {
            await page.setViewportSize({ width, height: 900 });
            await page.clock.install({ time: new Date("2026-08-15T00:05:00Z") });
            const proposal = discoveryProposalFixture();
            const entry = { ...discoveryItemsPage.entries[0], item: { ...discoveryItemsPage.entries[0].item, id: "frigate", name: "Frigate" } };
            let reads = 0;
            let recovered = false;
            const errors: string[] = [];
            page.on("pageerror", error => errors.push(error.message));
            await page.route("**/api/v1/discovery/items/frigate", route => route.fulfill({ json: entry }));
            await page.route("**/api/v1/discovery/proposals?**", route => {
                reads += 1;
                expect(route.request().method()).toBe("GET");
                const row = recovered ? { ...proposal, actionable_navigation: false } : malformed === "object reason"
                    ? { ...proposal, reason: {} } : { ...proposal, actionable_navigation: "false" };
                return route.fulfill({ json: { proposals: [row], total: 1, limit: 25 } });
            });
            await page.goto("/discovery/items/frigate");
            await expect(page.getByText("Proposal context is temporarily unavailable. Discovery and provider state were not affected.", { exact: true })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Frigate", exact: true })).toBeVisible();
            await expect(page.getByRole("link", { name: "Continue to maintenance selection for frigate", exact: true })).toHaveCount(0);
            const initialReads = reads;
            expect(initialReads).toBeGreaterThan(0);
            recovered = true;
            await page.reload();
            await expect(page.getByRole("link", { name: "Review Discovery item for frigate", exact: true })).toBeVisible();
            await expect(page.getByRole("link", { name: "Continue to maintenance selection for frigate", exact: true })).toHaveCount(0);
            expect(reads).toBe(initialReads * 2);
            expect(errors).toEqual([]);
            expect(rejectedMutationRequests).toEqual([]);
        });
    }
}
