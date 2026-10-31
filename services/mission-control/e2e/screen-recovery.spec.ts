import { discoveryItemsPage, executionCandidates, expect, providers, test } from "./mission-control-fixtures";
import { operationalDiagnostic, operationalLifecycle } from "../src/test/operationalLifecycle";
import { workflowAudit } from "../src/test/workflowAudit";
import { workflowDetail } from "../src/test/workflowDetail";
import type { Locator } from "@playwright/test";

async function expectResponsiveMainPadding(content: Locator, width: number) {
    const padding = await content.evaluate((element) => {
        const main = element.closest("main");
        return main ? getComputedStyle(main).paddingLeft : null;
    });
    if (width < 640) {
        expect(padding).toBe("16px");
    } else {
        expect(Number.parseFloat(padding ?? "0px")).toBeGreaterThan(16);
    }
}

for (const width of [320, 1280]) {
    test(`workflow review and audit keep responsive spacing while loading at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let releaseWorkflowRead!: () => void;
        let releaseAuditRead!: () => void;
        const workflowRead = new Promise<void>((resolve) => { releaseWorkflowRead = resolve; });
        const auditRead = new Promise<void>((resolve) => { releaseAuditRead = resolve; });
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows/loading-workflow/implementation-request", async (route) => {
            await workflowRead;
            return route.fulfill({ json: workflowDetail({ workflow_id: "loading-workflow" }) });
        });
        await page.route("**/agent-api/api/v1/agent/workflows/loading-workflow/audit", async (route) => {
            await auditRead;
            const fixture = workflowAudit();
            return route.fulfill({ json: workflowAudit({
                workflow_id: "loading-workflow",
                workflow: { ...fixture.workflow, workflow_id: "loading-workflow" },
            }) });
        });

        try {
            await page.goto("/workflows/loading-workflow");
            const workflowLoading = page.getByRole("status").filter({ hasText: "Loading workflow..." });
            await expect(workflowLoading).toBeVisible();
            await expectResponsiveMainPadding(workflowLoading, width);
            releaseWorkflowRead();
            await expect(page.getByRole("heading", { name: "Review workflow", exact: true })).toBeVisible();

            await page.getByRole("link", { name: "View workflow history", exact: true }).click();
            const auditLoading = page.getByRole("status").filter({ hasText: "Loading workflow history…" });
            await expect(auditLoading).toBeVisible();
            await expectResponsiveMainPadding(auditLoading, width);
            releaseAuditRead();
            await expect(page.getByRole("heading", { name: "Workflow history", exact: true })).toBeVisible();
            expect(rejectedMutationRequests).toEqual([]);
        } finally {
            releaseWorkflowRead();
            releaseAuditRead();
        }
    });
}

for (const width of [320, 1280]) {
    test(`maintenance history uses responsive spacing while loading at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let releaseHistoryRead!: () => void;
        const historyRead = new Promise<void>((resolve) => { releaseHistoryRead = resolve; });
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows**", async (route) => {
            await historyRead;
            return route.fulfill({ json: { items: [], total: 0, limit: 10, offset: 0 } });
        });

        try {
            await page.goto("/operations/history");
            const loadingMessage = page.getByRole("status").filter({ hasText: "Loading maintenance history…" });
            await expect(loadingMessage).toBeVisible();
            await expectResponsiveMainPadding(loadingMessage, width);
            releaseHistoryRead();
            const emptyState = page.getByText("No maintenance requests yet.", { exact: true });
            await expect(emptyState).toBeVisible();
            await expectResponsiveMainPadding(emptyState, width);
            expect(rejectedMutationRequests).toEqual([]);
        } finally {
            releaseHistoryRead();
        }
    });
}

test("provider action catalog reload recovers after an unavailable read", async ({ page, rejectedMutationRequests }) => {
    let reads = 0;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/v1/providers/proxmox/actions", (route) => {
        reads += 1;
        return reads === 1
            ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
            : route.fulfill({ json: [] });
    });
    await page.goto("/providers/proxmox");
    await expect(page.getByRole("heading", { name: "Provider actions are unavailable" })).toBeVisible();
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByText("No actions are available for this provider.")).toBeVisible();
    expect(reads).toBe(2);
    expect(rejectedMutationRequests).toEqual([]);
});

for (const width of [320, 390, 1280]) {
    test(`provider details fit the screen at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/providers/proxmox");
        const heading = page.getByRole("heading", { name: "Proxmox", exact: true });
        await expect(heading).toBeVisible();
        await expect(page.getByRole("heading", { name: "Diagnostics" })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Recommendations" })).toBeVisible();
        await expect(page.getByText("Last checked (local time)")).toBeVisible();
        await expect(page.getByText("Last checked (local time)").locator("xpath=following-sibling::p/time")).toHaveAttribute("datetime", /Z$/);
        const spacing = await heading.evaluate((element) => {
            const page = element.closest("main");
            const overview = element.closest("section");
            return {
                page: page ? getComputedStyle(page).paddingLeft : null,
                overview: overview ? getComputedStyle(overview).paddingLeft : null,
            };
        });
        if (width < 640) {
            expect(spacing).toEqual({ page: "16px", overview: "20px" });
        } else {
            expect(Number.parseFloat(spacing.page ?? "0px")).toBeGreaterThan(16);
            expect(Number.parseFloat(spacing.overview ?? "0px")).toBeGreaterThan(20);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

test("provider details show one notice when supported features cannot be loaded", async ({ page, rejectedMutationRequests }) => {
    await page.route("**/api/v1/providers", (route) => route.fulfill({
        json: providers.map((provider) => ({ ...provider, capabilities: null })),
    }));
    await page.goto("/providers/proxmox");

    await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
    await expect(page.locator("p[role='status']")).toHaveText("Atlas couldn't load this provider's supported features. Some sections are hidden.");
    await expect(page.getByRole("heading", { name: "Diagnostics" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Resources and monitoring" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Connection" })).toHaveCount(0);
    expect(rejectedMutationRequests).toEqual([]);
});

for (const width of [320, 1280]) {
    test(`provider resource monitoring fits the screen at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", (route) => route.fulfill({
            json: providers.map((provider) => ({ ...provider, capabilities: ["resources"] })),
        }));
        await page.route("**/api/v1/providers/proxmox/resources", (route) => route.fulfill({ json: {
            provider_id: "proxmox",
            provider_name: "Proxmox",
            refreshed_at: "2026-10-31T10:00:00Z",
            resources: [{
                provider_id: "proxmox",
                resource_id: "110",
                display_name: "Frigate",
                resource_type: "qemu",
                current_state: "running",
                expectation: { value: null, label: "Needs review", state: "needs_review", allowed_values: [] },
                configured: false,
                missing: false,
                needs_review: true,
                metadata: {},
            }],
            summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } },
            metadata: {},
        } }));
        await page.route("**/api/v1/providers/proxmox/management", (route) => route.fulfill({ json: {
            schema_version: "provider-management-v2",
            provider_id: "proxmox",
            provider_name: "Proxmox",
            sections: ["connection", "discovery", "resources", "monitoring", "diagnostics", "actions"].map((section) => ({
                section,
                availability: "available",
                read_only_descriptor: true,
                grants_permission: false,
                grants_execution: false,
            })),
            resource_types: [{
                provider_id: "proxmox",
                resource_type: "qemu",
                resource_readable: true,
                authoritative_identity_supported: true,
                provider_intent_capability_supported: true,
                provider_intent_mutation_available: false,
                supported_expectations: ["running", "stopped", "ignored"],
                operationally_requestable: false,
                grants_permission: false,
                grants_execution: false,
            }],
            resources: [{
                provider_id: "proxmox",
                resource_id: "110",
                resource_type: "qemu",
                display_name: "Frigate",
                current_state: "running",
                missing: false,
                identity_assurance: "authoritative",
                management_fingerprint: `provider-management-fingerprint-v1:${"a".repeat(64)}`,
                intent_authority: "provider_intent",
                intent_status: "needs_review",
                intent_reason: "no_active_intent",
                expectation: null,
                record_version: null,
                legacy_review_available: false,
                legacy_expectation: null,
                replacement_detected: false,
                mutation_available: false,
                operationally_requestable: false,
                grants_execution: false,
            }],
            provider_intent_activation: "activated",
            provider_intent_authority_status: "available",
            grants_permission: false,
            grants_execution: false,
        } }));

        await page.goto("/providers/proxmox");
        await expect(page.getByRole("heading", { name: "Resources and monitoring" })).toBeVisible();
        await expect(page.getByText("Sign in with permission to edit monitoring expectations.")).toBeVisible();
        const resourceCard = page.getByTestId("resource-row-qemu-110");
        const resourceCardWidth = await resourceCard.evaluate((element) => ({
            client: element.clientWidth,
            content: element.scrollWidth,
        }));
        expect(resourceCardWidth.content).toBeLessThanOrEqual(resourceCardWidth.client);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 1280]) {
    test(`provider loading state keeps compact phone spacing at ${width}px`, async ({ page }) => {
        let releaseProviderRead!: () => void;
        const providerRead = new Promise<void>((resolve) => { releaseProviderRead = resolve; });
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", async (route) => {
            await providerRead;
            await route.fulfill({ json: providers });
        });
        await page.goto("/providers/proxmox");
        const loadingMessage = page.getByRole("status").getByText("Loading provider details…", { exact: true });
        await expect(loadingMessage).toBeVisible();
        const spacing = await loadingMessage.evaluate((element) => {
            const page = element.closest("main");
            const panel = element.closest("section");
            return {
                page: page ? getComputedStyle(page).paddingLeft : null,
                panel: panel ? getComputedStyle(panel).paddingLeft : null,
            };
        });
        if (width < 640) {
            expect(spacing).toEqual({ page: "16px", panel: "20px" });
        } else {
            expect(Number.parseFloat(spacing.page ?? "0px")).toBeGreaterThan(16);
            expect(Number.parseFloat(spacing.panel ?? "0px")).toBeGreaterThan(20);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        releaseProviderRead();
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
    });
}

for (const width of [320, 1280]) {
    test(`provider loading state keeps compact spacing at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let releaseProviderRead!: () => void;
        const providerRead = new Promise<void>((resolve) => { releaseProviderRead = resolve; });
        let readCount = 0;

        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", async (route) => {
            readCount += 1;
            await providerRead;
            await route.fulfill({ json: providers });
        });
        await page.goto("/providers/proxmox");

        const loadingMessage = page.getByRole("status").getByText("Loading provider details…", { exact: true });
        await expect(loadingMessage).toBeVisible();
        const spacing = await loadingMessage.evaluate((element) => {
            const page = element.closest("main");
            const panel = element.closest("section");
            return {
                page: page ? getComputedStyle(page).paddingLeft : null,
                panel: panel ? getComputedStyle(panel).paddingLeft : null,
            };
        });
        if (width < 640) {
            expect(spacing).toEqual({ page: "16px", panel: "20px" });
        } else {
            expect(Number.parseFloat(spacing.page ?? "0px")).toBeGreaterThan(16);
            expect(Number.parseFloat(spacing.panel ?? "0px")).toBeGreaterThan(20);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

        releaseProviderRead();
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
        expect(readCount).toBe(1);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`provider action fields use readable labels at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers/proxmox/actions", route => route.fulfill({ json: [{
            id: "inspect-resource",
            label: "Inspect Resource",
            description: "Read provider resource details.",
            icon: "info",
            requires_confirmation: false,
            destructive: false,
            enabled: true,
            parameters: { resource_id: {
                type: "string", required: true, description: "Provider resource to inspect.", example: "110",
            } },
        }] }));
        await page.goto("/providers/proxmox");

        const action = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Inspect Resource" }) });
        await expect(action.getByLabel("Resource ID")).toBeVisible();
        await expect(action.getByLabel("Resource ID")).toHaveAttribute("placeholder", "110");
        await expect(action.getByText("resource_id", { exact: true })).toHaveCount(0);
        expect(await page.evaluate(maxWidth => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

test("switching provider routes clears action parameters before the next catalog arrives", async ({ page }) => {
    const action = { id: "review-model", label: "Review model", description: "Mock action for form isolation.",
        icon: "info", requires_confirmation: true, destructive: false, enabled: true,
        parameters: { model: { type: "string", required: true } } };
    let releaseNext!: () => void;
    const nextCatalog = new Promise<void>((resolve) => { releaseNext = resolve; });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/v1/providers", (route) => route.fulfill({ json: [providers[0], { ...providers[0], id: "ollama", name: "Ollama" }] }));
    await page.route("**/api/v1/providers/proxmox/actions", (route) => route.fulfill({ json: [action] }));
    await page.route("**/api/v1/providers/ollama/actions", async (route) => {
        await nextCatalog;
        await route.fulfill({ json: [action] });
    });
    await page.goto("/providers/proxmox");
    await page.getByLabel(/model/i).fill("previous-provider-value");
    // Exercise the app's public router without reloading the document, so this
    // covers a parameter change while the provider page remains mounted.
    await page.evaluate(async () => {
        const modulePath = "/src/app/router.tsx";
        const { router } = await import(modulePath);
        await router.navigate("/providers/ollama");
    });
    await expect(page.getByText("Loading available actions…")).toBeVisible();
    await expect(page.getByLabel(/model/i)).toHaveCount(0);
    releaseNext();
    await expect(page.getByLabel(/model/i)).toHaveValue("");
    await expect(page.getByRole("button", { name: "Review model", exact: true })).toBeDisabled();
    await expect(page.getByRole("heading", { name: "Direct provider actions", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("action history recovers a read without showing another record", async ({ page }) => {
    let reads = 0;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/v1/ops/actions/record-recovery", (route) => {
        reads += 1;
        return reads === 1
            ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
            : route.fulfill({ json: {
                id: "other-record",
                provider_id: "proxmox",
                provider_name: "Proxmox",
                action_id: "restart-service",
                action_label: "Restart service",
                status: "succeeded",
                success: true,
                message: "The service restarted.",
                confirmed: true,
                destructive: true,
                parameter_names: [],
                request_id: null,
                started_at: "2026-10-25T15:00:00Z",
                completed_at: "2026-10-25T15:00:01Z",
                duration_ms: 1000,
            } });
    });
    await page.goto("/operations/actions/record-recovery");
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("alert")).toContainText("does not match this link");
    await expect(page.getByRole("alert")).not.toContainText("Try again.");
    await expect(page.getByRole("heading", { name: "Action details" })).toBeVisible();
    await expect(page.getByTestId("mc-context")).toContainText("Current page: Action details");
    await expect(page).toHaveTitle("Action details | Atlas Mission Control");
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "← Back to action history" }).click();
    await expect(page.getByRole("heading", { name: "Action history", exact: true })).toBeVisible();
});

for (const width of [320, 1280]) {
    test(`action history detail loading uses responsive spacing at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let releaseEntryRead!: () => void;
        const entryRead = new Promise<void>((resolve) => { releaseEntryRead = resolve; });
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/api/v1/ops/actions/loading-entry", async (route) => {
            await entryRead;
            return route.fulfill({ json: {
                id: "loading-entry",
                provider_id: "proxmox",
                provider_name: "Proxmox",
                action_id: "restart-service",
                action_label: "Restart service",
                status: "succeeded",
                success: true,
                message: "The service restarted.",
                confirmed: true,
                destructive: true,
                parameter_names: [],
                request_id: null,
                started_at: "2026-10-25T15:00:00Z",
                completed_at: "2026-10-25T15:00:01Z",
                duration_ms: 1000,
            } });
        });

        try {
            await page.goto("/operations/actions/loading-entry");
            const loadingMessage = page.getByText("Loading action details…", { exact: true });
            await expect(loadingMessage).toBeVisible();
            await expectResponsiveMainPadding(page.getByRole("heading", { name: "Action details", exact: true }), width);
            const loadingCardPadding = await loadingMessage.evaluate((element) => {
                const card = element.parentElement;
                return card ? getComputedStyle(card).paddingLeft : null;
            });
            if (width < 640) {
                expect(loadingCardPadding).toBe("16px");
            } else {
                expect(Number.parseFloat(loadingCardPadding ?? "0px")).toBeGreaterThan(16);
            }
            releaseEntryRead();
            await expect(page.getByRole("heading", { name: "Restart service", exact: true })).toBeVisible();
            expect(rejectedMutationRequests).toEqual([]);
        } finally {
            releaseEntryRead();
        }
    });
}

test("readiness reload stays redacted for invalid review data", async ({ page }) => {
    const requestedId = "00000000-0000-4000-8000-000000000002";
    let reads = 0;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route(`**/api/v1/installation/candidate-records/${requestedId}/readiness-review`, (route) => {
        reads += 1;
        return reads === 1
            ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
            : route.fulfill({ json: { review: { candidate_record_id: "other-candidate", operator_id: "private-review-canary" } } });
    });
    await page.goto(`/installation/candidate-records/${requestedId}/readiness-review`);
    await page.getByRole("button", { name: "Reload review" }).click();
    await expect(page.getByRole("heading", { name: "Review unavailable" })).toBeVisible();
    await expect(page.getByText("private-review-canary", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Review permission evidence statement" })).toHaveCount(0);
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("audit recovery refuses another workflow without losing navigation", async ({ page }) => {
    let reads = 0;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/agent-api/**/workflows/audit-recovery/audit", (route) => {
        reads += 1;
        return reads === 1
            ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
            : route.fulfill({ json: workflowAudit({
                workflow_id: "other",
                workflow: { ...workflowAudit().workflow, workflow_id: "other" },
            }) });
    });
    await page.goto("/workflows/audit-recovery/audit");
    await expect(page.getByRole("heading", { name: "Workflow history unavailable" })).toBeVisible();
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("alert")).toContainText("Atlas returned a different workflow than this link requested. Try again to load the right history.");
    await expect(page.getByRole("alert")).not.toContainText("Try loading it again.");
    await expect(page.getByRole("link", { name: "← Back to Workflow" })).toHaveAttribute("href", "/workflows/audit-recovery");
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("discovery refuses another catalog item's details", async ({ page, rejectedMutationRequests }) => {
    let reads = 0;
    await page.setViewportSize({ width: 320, height: 844 });
    await page.route("**/api/v1/discovery/items/requested-item", (route) => {
        reads += 1;
        if (reads <= 2) return route.fulfill({ json: { item: { id: "other" } } });
        const entry = discoveryItemsPage.entries[0];
        return route.fulfill({ json: {
            ...entry,
            item: { ...entry.item, id: "requested-item", name: "Requested Item" },
        } });
    });
    await page.route("**/api/v1/discovery/items/requested-item/relationships", (route) => route.fulfill({ json: { item_id: "requested-item", incoming: [], outgoing: [] } }));
    await page.goto("/discovery/items/requested-item");
    const itemError = page.locator("main > div[role=alert]");
    await expect(itemError).toContainText("Atlas got details for a different catalog item. Try again.");
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { name: "Requested Item" })).toBeVisible();
    expect(reads).toBe(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "← Catalog" }).click();
    await expect(page.getByRole("heading", { name: "Browse the catalog", exact: true })).toBeVisible();
    expect(rejectedMutationRequests).toEqual([]);
});

test("catalog item details offer a clear recovery after a failed read", async ({ page, rejectedMutationRequests }) => {
    let reads = 0;
    let allowRecovery = false;
    const width = 390;
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/v1/discovery/items/retry-item", (route) => {
        reads += 1;
        if (!allowRecovery) return route.fulfill({ status: 503, json: { detail: "PRIVATE_BACKEND_DETAIL" } });
        const entry = discoveryItemsPage.entries[0];
        return route.fulfill({ json: { ...entry, item: { ...entry.item, id: "retry-item", name: "Recovered Item" } } });
    });
    await page.goto("/discovery/items/retry-item");

    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Catalog item unavailable");
    await expect(alert).toContainText("Atlas couldn’t load this catalog item. Try again to check its details.");
    await expect(alert).not.toContainText("PRIVATE_BACKEND_DETAIL");
    await expect(alert.locator("details")).not.toHaveAttribute("open");
    allowRecovery = true;
    await alert.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { name: "Recovered Item", exact: true })).toBeVisible();
    expect(reads).toBeGreaterThanOrEqual(2);
    expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    expect(rejectedMutationRequests).toEqual([]);
});

for (const width of [320, 390, 1280]) {
    test(`missing catalog item gives a simple recovery path at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        const dependentReads: string[] = [];
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/missing-item", route => route.fulfill({ status: 404, json: { detail: "Catalog item not found" } }));
        page.on("request", request => {
            const path = new URL(request.url()).pathname;
            if (path.startsWith("/api/v1/discovery/items/missing-item/") || path === "/api/v1/discovery/proposals") {
                dependentReads.push(path);
            }
        });
        await page.goto("/discovery/items/missing-item");

        await expect(page.getByTestId("mc-context")).toContainText("Current page: Catalog item details");
        await expect(page).toHaveTitle("Catalog item details | Atlas Mission Control");
        const notFound = page.getByRole("heading", { name: "Catalog item not found" }).locator("xpath=..");
        await expect(notFound.getByText("This catalog item is no longer available. Return to the catalog and choose a current item.", { exact: true })).toBeVisible();
        await expect(notFound.getByText("Catalog item ID: missing-item", { exact: true })).toBeHidden();
        await notFound.getByText("Technical details", { exact: true }).click();
        await expect(notFound.getByText("Catalog item ID: missing-item", { exact: true })).toBeVisible();
        await page.getByRole("link", { name: "← Catalog" }).click();
        await expect(page.getByRole("heading", { name: "Browse the catalog", exact: true })).toBeVisible();
        expect(dependentReads).toEqual([]);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(maxWidth => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const width of [390, 1280]) {
    test(`compatibility findings use clear labels and keep references optional at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        const baseEntry = discoveryItemsPage.entries[0];
        const entry = {
            ...baseEntry,
            item: {
                ...baseEntry.item,
                requirements: {
                    ...baseEntry.item.requirements,
                    resources: { ...baseEntry.item.requirements.resources, memory_mb_min: 4096 },
                },
            },
            metadata: { reviewed_for_d5: true, catalog_notes: ["Hardware acceleration is optional."] },
        };
        const checkedAt = "2026-10-28T12:00:00.000Z";
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/fixture-app", route => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/relationships", route => route.fulfill({ json: {
            item_id: "fixture-app", incoming: [], outgoing: [],
        } }));
        await page.route("**/api/v1/discovery/items/fixture-app/compatibility", route => route.fulfill({ json: {
            item_id: "fixture-app",
            target_id: "atlas",
            target_type: "atlas_environment",
            status: "compatible_with_warnings",
            checked_at: checkedAt,
            findings: [{
                id: "finding-browser-1",
                check_type: "resource",
                severity: "warning",
                status: "compatible_with_warnings",
                subject: "requirements.resources.memory_mb_min",
                message: "Memory is borderline.",
                evidence_ids: ["evidence-browser-1"],
            }],
            evidence: [{
                id: "evidence-browser-1",
                check_type: "resource",
                subject: "requirements.resources.memory_mb_min",
                status: "compatible_with_warnings",
                message: "Memory check.",
                source: "compatibility_context",
            }],
            unknown_facts: ["installed_services"],
        } }));
        await page.route("**/api/v1/discovery/items/fixture-app/evidence", route => route.fulfill({ json: {
            schema_version: "discovery-merged-item-v1",
            catalog_item_id: "fixture-app",
            curated: entry,
            dynamic_claims: [],
            source_states: [],
            conflict_state: "none",
        } }));
        await page.route("**/api/v1/discovery/items/fixture-app/image-grounding", route => route.fulfill({ json: {
            schema_version: "discovery-image-grounding-projection-v1",
            catalog_item_id: "fixture-app",
            status: "no_deployment_binding",
            release_version: null,
            deployment_binding: null,
            observed_image: null,
            accepted_evidence: [],
        } }));
        await page.route("**/api/v1/discovery/proposals**", route => route.fulfill({ json: {
            proposals: [], total: 0, limit: 25,
        } }));
        await page.goto("/discovery/items/fixture-app");

        await expect(page.getByTestId("mc-context")).toContainText("Current page: Catalog item details");
        await expect(page).toHaveTitle("Catalog item details | Atlas Mission Control");
        const itemHeader = page.getByRole("heading", { name: "Fixture Application" }).locator("xpath=..");
        await expect(page.getByRole("heading", { name: "What it supports" })).toBeVisible();
        await expect(page.getByRole("heading", { name: "What this item needs" })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Catalog notes" })).toBeVisible();
        await expect(page.getByText("Hardware acceleration is optional.", { exact: true })).toBeVisible();
        await expect(page.getByText(/Reviewed for D5/)).toHaveCount(0);
        await expect(page.getByText("Read only", { exact: true })).toBeVisible();
        await expect(itemHeader.getByText("Catalog item ID: fixture-app", { exact: true })).toBeHidden();
        await itemHeader.getByText("Technical details", { exact: true }).click();
        await expect(itemHeader.getByText("Catalog item ID: fixture-app", { exact: true })).toBeVisible();
        const sourceDetails = page.getByText("Catalog source details", { exact: true }).locator("xpath=ancestor::details");
        await expect(sourceDetails).not.toHaveAttribute("open");
        await expect(sourceDetails.getByText("browser-fixture", { exact: true })).toBeHidden();
        await sourceDetails.getByText("Catalog source details", { exact: true }).click();
        await expect(sourceDetails.getByText("browser-fixture", { exact: true })).toBeVisible();

        const summary = page.getByRole("heading", { name: "Compatibility summary" }).locator("xpath=..");
        const findings = page.getByRole("heading", { name: "What Atlas found" }).locator("xpath=..");
        const compatibilityY = await summary.evaluate((element) => element.getBoundingClientRect().top + window.scrollY);
        const requirementsY = await page.getByRole("heading", { name: "What this item needs" }).evaluate((element) => element.getBoundingClientRect().top + window.scrollY);
        const installationPlanY = await page.getByRole("heading", { name: "Installation plan review" }).evaluate((element) => element.getBoundingClientRect().top + window.scrollY);
        const releaseEvidenceY = await page.getByRole("heading", { name: "Release evidence" }).evaluate((element) => element.getBoundingClientRect().top + window.scrollY);
        expect(compatibilityY).toBeLessThan(requirementsY);
        expect(requirementsY).toBeLessThan(installationPlanY);
        expect(compatibilityY).toBeLessThan(installationPlanY);
        expect(installationPlanY).toBeLessThan(releaseEvidenceY);
        await expect(summary.getByText("Compatible with warnings", { exact: true })).toBeVisible();
        await expect(summary.getByText("Findings", { exact: true }).locator("xpath=..").locator("dd")).toHaveText("1");
        await expect(summary.getByText("Results", { exact: true })).toHaveCount(0);
        await expect(summary.getByText("Last checked", { exact: true })).toBeVisible();
        await expect(summary.getByText(checkedAt, { exact: true })).toBeHidden();
        await expect(findings.getByText("Warnings", { exact: true })).toBeVisible();
        await expect(findings.getByText("Compatible with warnings", { exact: true })).toBeVisible();
        await expect(findings.getByText("Memory is borderline.", { exact: true })).toBeVisible();
        await expect(findings.getByText("Installed services", { exact: true })).toBeVisible();
        await expect(findings.getByText("Finding code: finding-browser-1", { exact: true })).toBeHidden();
        await findings.getByText("Evidence details", { exact: true }).click();
        await expect(findings.getByText("Finding code: finding-browser-1", { exact: true })).toBeVisible();
        await expect(findings.getByText("Checked field: requirements.resources.memory_mb_min", { exact: true })).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(maxWidth => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const width of [390, 1280]) {
    test(`suggestions can retry without leaving the catalog item at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        const entry = discoveryItemsPage.entries[0];
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/fixture-app", (route) => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/relationships", (route) => route.fulfill({ json: {
            item_id: "fixture-app", incoming: [], outgoing: [],
        } }));
        await page.route("**/api/v1/discovery/proposals**", (route) => {
            reads += 1;
            return reads === 1
                ? route.fulfill({ status: 503, json: { detail: "PRIVATE_PROPOSAL_ERROR" } })
                : route.fulfill({ json: { proposals: [], total: 0, limit: 25 } });
        });
        await page.goto("/discovery/items/fixture-app");

        const proposals = page.getByRole("region", { name: "Suggestions" });
        await expect(proposals.getByRole("alert")).toContainText("Suggestions are temporarily unavailable");
        await expect(proposals.getByRole("alert")).not.toContainText("PRIVATE_PROPOSAL_ERROR");
        await proposals.getByRole("button", { name: "Retry suggestions" }).click();
        await expect(proposals.getByText("No suggestions are available.")).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(2);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const width of [390, 1280]) {
    test(`source evidence can retry without reloading the catalog item at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        const entry = discoveryItemsPage.entries[0];
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/fixture-app", (route) => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/relationships", (route) => route.fulfill({ json: {
            item_id: "fixture-app", incoming: [], outgoing: [],
        } }));
        await page.route("**/api/v1/discovery/items/fixture-app/evidence", (route) => {
            reads += 1;
            return reads === 1
                ? route.fulfill({ status: 503, json: { detail: "PRIVATE_EVIDENCE_ERROR" } })
                : route.fulfill({ json: {
                    schema_version: "discovery-merged-item-v1",
                    catalog_item_id: "fixture-app",
                    curated: entry,
                    dynamic_claims: [],
                    source_states: [],
                    conflict_state: "none",
                } });
        });
        await page.goto("/discovery/items/fixture-app");

        const evidence = page.getByRole("region", { name: "Release evidence" });
        await expect(evidence.getByRole("alert")).toContainText("Release information unavailable");
        await expect(evidence.getByRole("alert")).not.toContainText("PRIVATE_EVIDENCE_ERROR");
        await evidence.getByRole("button", { name: "Retry release check" }).click();
        await expect(evidence.getByText("Only catalog information is available")).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(2);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const width of [390, 1280]) {
    test(`temporary image-grounding failures can retry at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        const entry = discoveryItemsPage.entries[0];
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/fixture-app", (route) => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/relationships", (route) => route.fulfill({ json: {
            item_id: "fixture-app", incoming: [], outgoing: [],
        } }));
        await page.route("**/api/v1/discovery/items/fixture-app/image-grounding", (route) => {
            reads += 1;
            return reads === 1
                ? route.fulfill({ status: 503, json: { detail: "PRIVATE_GROUNDING_ERROR" } })
                : route.fulfill({ json: {
                    schema_version: "discovery-image-grounding-projection-v1",
                    catalog_item_id: "fixture-app",
                    status: "no_deployment_binding",
                    release_version: null,
                    deployment_binding: null,
                    observed_image: null,
                    accepted_evidence: [],
                } });
        });
        await page.goto("/discovery/items/fixture-app");

        const grounding = page.getByRole("region", { name: "Image check" });
        await expect(grounding.getByRole("status")).toContainText("Atlas could not finish checking the image. Try again.");
        await expect(grounding.getByRole("status")).not.toContainText("PRIVATE_GROUNDING_ERROR");
        await grounding.getByRole("button", { name: "Retry image check" }).click();
        await expect(grounding.getByText("No deployment mapping").first()).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(2);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const width of [390, 1280]) {
    test(`installation plan details stay collapsed until requested at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        const entry = discoveryItemsPage.entries[0];
        const plan = {
            schema_version: "installation-plan-v1",
            fingerprint: { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: "a".repeat(64) },
            application: { item_id: "fixture-app", catalog_entry_id: "fixture-app", display_name: "Fixture Application", release_version: null },
            status: "missing_deployment_artifact",
            deployment_artifact: { state: "missing", kind: "docker-compose", repository_path: null, service: null, content_digest: null },
            image: { state: "missing", reference: null, digest: null, release_version: null },
            accepted_evidence: [], provenance: [], compatibility: [], prerequisites: [], relationships: [], assumptions: [],
            blockers: [{ code: "missing_deployment_artifact", subject: "fixture-app" }],
            risks: [], missing_facts: [{ code: "deployment_artifact", subject: "fixture-app" }], required_operator_confirmations: [],
        };
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/fixture-app", (route) => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/relationships", (route) => route.fulfill({ json: {
            item_id: "fixture-app", incoming: [], outgoing: [],
        } }));
        await page.route("**/api/v1/discovery/items/fixture-app/installation-plan", (route) => route.fulfill({ json: plan }));
        await page.goto("/discovery/items/fixture-app");

        const panel = page.getByRole("region", { name: "Installation plan review" });
        await expect(panel.getByText("There is 1 issue to review. This plan does not authorize an installation.")).toBeVisible();
        const details = panel.locator("details").filter({ hasText: "View issues and plan details" });
        expect(await details.evaluate((element) => (element as HTMLDetailsElement).open)).toBe(false);
        await expect(panel.getByText("a".repeat(64))).toBeHidden();
        await panel.getByText("View issues and plan details", { exact: true }).click();
        await expect(panel.getByText("a".repeat(64))).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const width of [320, 390, 1280]) {
    test(`workflow read failure hides technical errors and keeps recovery at ${width}px`, async ({ page }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/agent-api/**/workflows/recovery-workflow/implementation-request", (route) => {
            reads += 1;
            return reads === 1
                ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
                : route.fulfill({ json: workflowDetail({ workflow_id: "different-workflow" }) });
        });
        await page.goto("/workflows/recovery-workflow");
        const alert = page.getByRole("alert");
        await expect(page.getByRole("heading", { name: "Workflow unavailable" })).toBeVisible();
        await expectResponsiveMainPadding(alert, width);
        await expect(alert).toContainText("Atlas couldn’t load this workflow, so its status is unknown.");
        const technicalDetails = alert.locator("details");
        await expect(technicalDetails).not.toHaveAttribute("open");
        await expect(alert.getByText("Unavailable", { exact: true })).toBeHidden();
        await page.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("alert")).toContainText("does not match this page");
        await expect(page.getByRole("alert")).not.toContainText("Try loading it again.");
        expect(reads).toBe(2);
        await expect(page.getByRole("button", { name: "Approve Implementation" })).toHaveCount(0);
        await expectResponsiveMainPadding(page.getByRole("alert"), width);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
        await page.getByRole("link", { name: "← All workflows" }).click();
        await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
    });
}

for (const wrongIdentity of [false, true]) {
    test(`planning refuses unavailable or mismatched sessions (${wrongIdentity})`, async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await page.route("**/agent-api/**/candidate-planning/browser-session", (route) => route.fulfill({ json: {
            session_id: wrongIdentity ? "other-session" : "browser-session",
            candidate_id: "browser-candidate", status: "ready_for_planning",
            planning_allowed: false, intake_status: "accepted_for_planning",
            intake_reason_codes: [], candidate_fingerprint: "browser-fingerprint",
            unsupported_reason: null, plan: null, planning_failure: null,
        } }));
        await page.goto("/candidate-planning/browser-session");
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Plan a change");
        await expect(page).toHaveTitle("Plan a change | Atlas Mission Control");
        if (wrongIdentity) {
            await expect(page.getByRole("heading", { name: "Planning session unavailable" })).toBeVisible();
            await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
        } else {
            await expect(page.getByText("Planning is unavailable for this session.")).toBeVisible();
        }
        await expect(page.getByRole("button", { name: "Generate Plan" })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Create Workflow" })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [320, 1280]) {
    test(`planning session read failure retries in place at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        let allowRecovery = false;
        let releaseInitialFailure!: () => void;
        const initialFailure = new Promise<void>((resolve) => { releaseInitialFailure = resolve; });
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/**/candidate-planning/retry-session", (route) => {
            reads += 1;
            if (!allowRecovery) {
                return initialFailure.then(() => route.fulfill({ status: 503, json: { detail: "Planning service temporarily unavailable." } }));
            }
            return route.fulfill({ json: {
                session_id: "retry-session",
                candidate_id: "browser-candidate",
                status: "ready_for_planning",
                planning_allowed: true,
                intake_status: "accepted_for_planning",
                intake_reason_codes: [],
                candidate_fingerprint: "browser-fingerprint",
                unsupported_reason: null,
                plan: null,
                planning_failure: null,
            } });
        });
        await page.goto("/candidate-planning/retry-session");
        const loadingMessage = page.getByText("Loading planning session…", { exact: true });
        await expect(loadingMessage).toBeVisible();
        const loadingPadding = await loadingMessage.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(loadingPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(loadingPadding ?? "0px")).toBeGreaterThan(16);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        releaseInitialFailure();
        await expect(page.getByRole("heading", { name: "Planning session unavailable" })).toBeVisible();
        const retryUrl = page.url();
        const recoveryPadding = await page.getByRole("alert").evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(recoveryPadding).toBe("16px");
        } else {
            expect(Number.parseFloat(recoveryPadding ?? "0px")).toBeGreaterThan(16);
        }
        let mainFrameNavigations = 0;
        page.on("framenavigated", (frame) => {
            if (frame === page.mainFrame()) mainFrameNavigations += 1;
        });

        const readsBeforeRetry = reads;
        allowRecovery = true;
        await page.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("heading", { name: "Plan this change" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Generate Plan" })).toBeEnabled();
        expect(page.url()).toBe(retryUrl);
        expect(mainFrameNavigations).toBe(0);
        expect(reads).toBeGreaterThan(readsBeforeRetry);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed saved plans keep workflow controls hidden at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/**/candidate-planning/malformed-plan", (route) => route.fulfill({ json: {
            session_id: "malformed-plan",
            candidate_id: "candidate-browser",
            status: "plan_ready",
            planning_allowed: true,
            intake_status: "accepted_for_planning",
            intake_reason_codes: [],
            candidate_fingerprint: "candidate-fingerprint",
            unsupported_reason: null,
            plan: {
                identifier: "plan-browser",
                session_id: "malformed-plan",
                candidate_id: "candidate-browser",
                candidate_fingerprint: "candidate-fingerprint",
                title: "Update service configuration",
                objective: "Review the proposed configuration change.",
                assumptions: [], constraints: [], proposed_steps: null,
                likely_affected_components: [], likely_affected_files: [], verification_strategy: [],
                rollback_considerations: [], unresolved_questions: [], evidence_ids: [],
                created_at: "2026-10-28T00:00:00Z", repository_branch: null, repository_head: null,
                revalidated_candidate_fingerprint: "candidate-fingerprint",
            },
            planning_failure: null,
        } }));
        await page.goto("/candidate-planning/malformed-plan");

        await expect(page.getByRole("heading", { name: "Planning session unavailable" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
        await expect(page.getByRole("button", { name: "Generate Plan" })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Create Workflow" })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    test(`unknown pages retain navigation at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.goto("/page-that-does-not-exist");
        await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Page not found");
        await expect(page).toHaveTitle("Page not found | Atlas Mission Control");
        if (viewport.width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
        }
        const navigation = page.getByRole("navigation", { name: "Primary" }).filter({ visible: true });
        await navigation.getByRole("link", { name: "Workflows", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [320, 390, 1280]) {
    test(`an empty provider catalog has a clear way back at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", (route) => route.fulfill({
            status: 200, contentType: "application/json", body: "[]",
        }));
        await page.goto("/providers/proxmox");
        const heading = page.getByRole("heading", { name: "Provider not found" });
        await expect(heading).toBeVisible();
        await expect(page.getByText("Not updated yet")).not.toBeVisible();
        await expect(page.getByText("Atlas doesn't list this provider right now.")).toBeVisible();
        const pagePadding = await heading.evaluate((element) => {
            const main = element.closest("main");
            return main ? getComputedStyle(main).paddingLeft : null;
        });
        if (width < 640) {
            expect(pagePadding).toBe("16px");
        } else {
            expect(Number.parseFloat(pagePadding ?? "0px")).toBeGreaterThan(16);
        }
        await page.getByRole("link", { name: "← All providers" }).click();
        await expect(page.getByRole("heading", { name: "Providers" })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("workflows recover from an initial outage without reloading", async ({ page }) => {
    let attempts = 0;
    await page.route("**/agent-api/**", async (route) => {
        if (new URL(route.request().url()).pathname.endsWith("/workflows")) {
            attempts += 1;
            if (attempts === 1) {
                await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Temporarily unavailable" }) });
                return;
            }
        }
        await route.fallback();
    });
    await page.goto("/workflows");
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).toBeVisible();
    await expect(page.getByText("Try loading your workflows again.")).toHaveCount(0);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).not.toBeVisible();
    expect(attempts).toBe(2);
});

for (const width of [390, 1280]) {
    test(`malformed catalog data has a read-only retry and keeps navigation at ${width}px`, async ({ page }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/api/v1/discovery/items?**", (route) => {
            reads += 1;
            return route.fulfill({ json: reads === 1
                ? { entries: [null], total: 1, offset: 0, limit: 25, has_more: false }
                : discoveryItemsPage });
        });
        await page.goto("/discovery");

        const alert = page.getByRole("alert");
        await expect(page.getByRole("heading", { name: "Browse the catalog" })).toBeVisible();
        await expect(alert).toContainText("Catalog could not be loaded");
        await expect(alert).toContainText("Your search filters are still selected.");
        await expect(page.getByText("Results unavailable", { exact: true })).toBeVisible();
        await expect(page.getByText("Items unavailable", { exact: true })).toHaveCount(0);
        if (width < 1024) await page.getByRole("button", { name: "Open navigation" }).click();
        await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
        if (width < 1024) await page.getByRole("button", { name: "Close navigation" }).click();
        await expect(page.getByRole("heading", { name: "This page could not load" })).toHaveCount(0);
        await expect(page.getByText(/TypeError:|Cannot read properties/)).toHaveCount(0);
        await expect(alert).toContainText("Atlas couldn't load these results. Your search filters are still selected.");
        await page.getByRole("button", { name: "Retry search" }).click();

        await expect(page.getByRole("link", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [320, 390, 1280]) {
    test(`maintenance history keeps unavailable requests findable and details optional at ${width}px`, async ({ page }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/agent-api/**", async (route) => {
            const path = new URL(route.request().url()).pathname;
            if (path.endsWith("/workflows")) {
                reads += 1;
                await route.fulfill({ json: {
                    items: [{ workflow_id: "maintenance-test", workflow_source: "candidate",
                        workflow_state: "completed", effect_kind: "operational_action",
                        execution_intent: "restart-service", candidate_id: null,
                        planning_session_id: null, repository: null, target_id: "VM 110",
                        last_result_summary: "", timeline: [] }],
                    total: 1, limit: 10, offset: 0,
                } });
                return;
            }
            if (path.endsWith("/workflows/maintenance-test/implementation-request")) {
                await route.fulfill({ json: workflowDetail({
                    workflow_id: "maintenance-test",
                    effect_kind: "operational_action",
                    workflow_state: "completed",
                    implementation_approval_status: "approved",
                }) });
                return;
            }
            if (path.endsWith("/workflows/maintenance-test/operational-lifecycle")) {
                await route.fulfill({ json: operationalLifecycle({ workflow_id: "maintenance-test" }) });
                return;
            }
            if (path.endsWith("/workflows/maintenance-test/recovery-diagnostic")) {
                await route.fulfill({ status: 503, json: { detail: "Unavailable" } });
                return;
            }
            await route.fallback();
        });
        await page.goto("/operations/history");
        const itemHeading = page.getByRole("heading", { name: "Virtual machine 110" });
        await expect(itemHeading).toBeVisible();
        await expect(page.getByText("Past requests and each request's latest maintenance status. This is not a live service check.", { exact: true })).toBeVisible();
        await expectResponsiveMainPadding(itemHeading, width);
        await expect(page.getByText("proxmox/qemu/110", { exact: true })).toBeHidden();
        await expect(page.getByRole("combobox", { name: "Latest maintenance status", exact: true })).toBeVisible();
        await expect(page.getByRole("combobox", { name: "Requested action", exact: true })).toBeHidden();
        await page.locator("summary").filter({ hasText: "More filters" }).click();
        await expect(page.getByRole("combobox", { name: "Completion", exact: true })).toBeVisible();
        await expect(page.getByRole("combobox", { name: "Requested action", exact: true })).toHaveCount(0);
        await page.getByRole("combobox", { name: "Completion", exact: true }).selectOption("terminal");
        await expect(page.getByText("Additional filters are applied")).toBeVisible();
        await page.getByRole("combobox", { name: "Latest maintenance status", exact: true }).selectOption("unavailable");
        await expect(page.getByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        await expect(page.getByText("A problem checking status does not mean the maintenance request failed.")).toBeVisible();
        await expect(page).toHaveURL(/\/operations\/history\?completion=terminal&status=unavailable$/);
        await page.getByText("Request details", { exact: true }).click();
        await expect(page.getByText("Request stage", { exact: true })).toBeVisible();
        await expect(page.getByText("Status record check", { exact: true })).toBeVisible();
        await expect(page.getByText("Not available", { exact: true })).toBeVisible();
        await expect(page.getByText("proxmox/qemu/110", { exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "Review maintenance request" })).toHaveAttribute("href", "/workflows/maintenance-test?completion=terminal&status=unavailable&returnTo=%2Foperations%2Fhistory");
        await page.getByRole("link", { name: "Review maintenance request" }).click();
        await expect(page.getByRole("heading", { name: "Review maintenance request" })).toBeVisible();
        await expect(page.getByRole("link", { name: "← Maintenance history" })).toHaveAttribute("href", "/operations/history?completion=terminal&status=unavailable");
        await page.getByRole("link", { name: "← Maintenance history" }).click();
        await expect(page.getByRole("heading", { name: "Maintenance history" })).toBeVisible();
        await expect(page.getByRole("combobox", { name: "Latest maintenance status", exact: true })).toHaveValue("unavailable");
        await page.locator("summary").filter({ hasText: "More filters" }).click();
        await expect(page.getByRole("combobox", { name: "Completion", exact: true })).toHaveValue("terminal");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(reads).toBe(2);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed maintenance history offers a read-only retry at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/agent-api/api/v1/agent/workflows**", route => {
            reads += 1;
            return route.fulfill({ json: reads === 1
                ? { items: [null], total: 1, limit: 10, offset: 0 }
                : { items: [], total: 0, limit: 10, offset: 0 } });
        });
        await page.goto("/operations/history");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Atlas couldn’t load maintenance history.");
        await expect(alert).toContainText("The latest maintenance status could not be confirmed.");
        await expectResponsiveMainPadding(alert, width);
        await expect(page.getByRole("heading", { name: "This page could not load" })).toHaveCount(0);
        if (width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
            await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
            await page.getByRole("button", { name: "Close navigation" }).click();
        }

        await page.getByRole("button", { name: "Refresh history" }).click();
        await expect(page.getByText("No maintenance requests yet.", { exact: true })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`maintenance history keeps the last loaded requests visible after refresh fails at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        let releaseRefresh!: () => void;
        const refreshGate = new Promise<void>((resolve) => { releaseRefresh = resolve; });
        await page.setViewportSize({ width, height: 844 });
        await page.route("**/agent-api/**", async (route) => {
            const path = new URL(route.request().url()).pathname;
            if (path.endsWith("/workflows")) {
                reads += 1;
                if (reads > 1) {
                    await refreshGate;
                    return route.fulfill({ status: 503, json: { detail: "Unavailable" } });
                }
                return route.fulfill({ json: {
                    items: [{ workflow_id: "stale-maintenance", workflow_source: "candidate",
                        workflow_state: "completed", effect_kind: "operational_action",
                        execution_intent: "restart-service", candidate_id: null,
                        planning_session_id: null, repository: null, target_id: "VM 110",
                        last_result_summary: "", timeline: [] }],
                    total: 1, limit: 10, offset: 0,
                } });
            }
            if (path.endsWith("/workflows/stale-maintenance/operational-lifecycle")) {
                return route.fulfill({ json: operationalLifecycle({ workflow_id: "stale-maintenance" }) });
            }
            if (path.endsWith("/workflows/stale-maintenance/recovery-diagnostic")) {
                return route.fulfill({ json: operationalDiagnostic({
                    correlation: { workflow_id: "stale-maintenance", request_id: "request-1", request_digest_match: true, agent_record_present: true, core_record_present: true },
                }) });
            }
            return route.fallback();
        });

        try {
            await page.goto("/operations/history");

            const item = page.getByRole("heading", { name: "Virtual machine 110" });
            await expect(item).toBeVisible();
            await page.getByRole("button", { name: "Refresh history" }).click();
            const refreshing = page.getByRole("status").filter({ hasText: "The last loaded requests remain visible" });
            await expect(refreshing).toBeVisible();
            await expect(item).toBeVisible();
            releaseRefresh();

            const alert = page.getByRole("alert");
            await expect(alert).toContainText("Atlas couldn’t refresh maintenance history.");
            await expect(alert).toContainText("last successful load");
            await expect(item).toBeVisible();
            await expect(page.getByRole("heading", { name: "Healthy", exact: true })).toBeVisible();
            expect(reads).toBe(2);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            expect(rejectedMutationRequests).toEqual([]);
        } finally {
            releaseRefresh();
        }
    });
}

for (const width of [390, 1280]) {
    test(`provider registry is reachable and links back from details at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/");
        await page.getByRole("link", { name: "View provider registry", exact: true }).click();
        await expect(page).toHaveURL(/\/providers$/);
        await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Providers");
        await expect(page.getByText("Check time unavailable.", { exact: true })).toHaveCount(0);
        await page.getByRole("link", { name: "Open Proxmox provider", exact: true }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Provider details");
        await expect(page).toHaveTitle("Provider details | Atlas Mission Control");
        await expect(page.getByText("Healthy", { exact: true })).toHaveCount(1);
        await expect(page.getByText("Status", { exact: true })).toHaveCount(0);
        await expect(page.getByText("HTTP response code", { exact: true })).toBeHidden();
        await page.getByText("Technical details", { exact: true }).click();
        await expect(page.getByText("HTTP response code", { exact: true })).toBeVisible();
        await page.getByRole("link", { name: /All providers/ }).click();
        await expect(page).toHaveURL(/\/providers$/);
        await expect(page.getByRole("link", { name: "Open Proxmox provider" })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
}

test("provider registry retries an unavailable read", async ({ page }) => {
    let attempts = 0;
    await page.route("**/api/v1/providers", async (route) => {
        attempts += 1;
        if (attempts === 1) {
            await route.fulfill({ status: 503, json: { detail: "PRIVATE_SERVER_ERROR" } });
            return;
        }
        await route.fallback();
    });
    await page.goto("/providers");
    await expect(page.getByRole("heading", { name: "Could not load providers" })).toBeVisible();
    await expect(page.getByRole("alert").getByRole("button")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(1);
    await expect(page.getByText("Try again to get the latest provider list.")).toHaveCount(0);
    await expect(page.getByText("PRIVATE_SERVER_ERROR")).toHaveCount(0);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("link", { name: "Open Proxmox provider" })).toBeVisible();
    expect(attempts).toBe(2);
});

for (const width of [390, 1280]) {
    test(`provider registry keeps last loaded status clearly marked after refresh fails at ${width}px`, async ({ page }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", async route => {
            reads += 1;
            return reads === 1
                ? route.fallback()
                : route.fulfill({ status: 503, json: { detail: "PRIVATE_SERVER_ERROR" } });
        });
        await page.goto("/providers");
        const list = page.getByRole("region", { name: "Provider list" });
        await expect(list.getByRole("heading", { name: "Proxmox" })).toBeVisible();
        await expect(list.getByText("Healthy", { exact: true })).toBeVisible();

        await page.getByRole("button", { name: "Refresh" }).click();
        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Could not refresh providers");
        await expect(alert.getByRole("button")).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Refresh" })).toHaveCount(1);
        await expect(alert).toContainText("Showing the last loaded list. Provider statuses may be out of date.");
        await expect(alert).not.toContainText("PRIVATE_SERVER_ERROR");
        await expect(list.getByRole("heading", { name: "Proxmox" })).toBeVisible();
        await expect(list.getByText("Last known report (out of date): Healthy.", { exact: true })).toBeVisible();
        await expect(list.getByText("Healthy", { exact: true })).toHaveCount(0);
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    });
}

for (const width of [390, 1280]) {
    test(`change proposal details can retry after a temporary read failure at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/execution-candidates/candidate-retry", (route) => {
            reads += 1;
            return reads <= 2
                ? route.fulfill({ status: 503, json: { detail: "PRIVATE_BACKEND_DETAIL" } })
                : route.fulfill({ json: { ...executionCandidates[0], id: "candidate-retry" } });
        });
        await page.goto("/execution-candidates/candidate-retry");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Change proposal unavailable");
        await expect(alert).toContainText("Atlas couldn’t load this change proposal. Try again to check its details.");
        await expect(alert).toContainText("Atlas couldn’t load this change proposal.");
        await expect(alert).not.toContainText("PRIVATE_BACKEND_DETAIL");
        await alert.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        expect(reads).toBe(3);
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

for (const expires_at of [null, "2999-02-30T00:00:00Z"]) {
    test(`proposal planning stays review-only and validates expiry ${expires_at ?? "none"}`, async ({ page }) => {
        const proposal = { ...executionCandidates[0], expires_at };
        await page.route("**/api/v1/execution-candidates/*", (route) => route.fulfill({ json: proposal }));
        await page.goto(`/execution-candidates/${proposal.id}`);
        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true })).toBeVisible();
        await expect(page.getByText("Review the proposed change and its limits before planning. Planning does not approve or apply a change.")).toBeVisible();
        const planning = page.getByRole("button", { name: "Start planning", exact: true });
        if (expires_at === null) await expect(planning).toBeEnabled();
        else {
            await expect(planning).toBeDisabled();
            await expect(page.getByText("Unverified expiry", { exact: true })).toBeVisible();
        }
        await expect(page.getByRole("button", { name: /execute|install|apply|approve|run now/i })).toHaveCount(0);
    });
}

test("a proposal with the wrong response identity cannot offer planning", async ({ page }) => {
    await page.route("**/api/v1/execution-candidates/*", (route) => route.fulfill({
        json: { ...executionCandidates[0], id: "other-proposal" },
    }));
    await page.goto(`/execution-candidates/${executionCandidates[0].id}`);
    await expect(page.getByRole("alert")).toContainText("The returned proposal does not match this page.");
    await expect(page.getByRole("button", { name: "Start planning" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "other-proposal" })).toHaveCount(0);
});

for (const width of [390, 1280]) {
    test(`a missing proposal is distinct from a service outage at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/execution-candidates/*", (route) => route.fulfill({
            status: 404, json: { detail: "PRIVATE_BACKEND_DETAIL" },
        }));
        await page.goto("/execution-candidates/missing-proposal");
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Proposal details");
        await expect(page).toHaveTitle("Proposal details | Atlas Mission Control");
        await expect(page.getByRole("heading", { name: "Change proposal not found" })).toBeVisible();
        await expect(page.getByText("This proposal is no longer available. Return to Change proposals and open a current proposal.")).toBeVisible();
        await expect(page.getByText("PRIVATE_BACKEND_DETAIL")).toHaveCount(0);
        const proposalId = page.getByText("Proposal ID: missing-proposal");
        await expect(proposalId).toBeHidden();
        await page.getByText("Technical details").click();
        await expect(proposalId).toBeVisible();
        await expect(page.getByRole("button", { name: "Start planning" })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [390, 1280]) {
    test(`malformed action history rows recover with a read-only refresh at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/ops/actions/page**", route => {
            reads += 1;
            return route.fulfill({ json: reads === 1
                ? { items: [null], total: 1, offset: 0, limit: 25, has_more: false }
                : { items: [], total: 0, offset: 0, limit: 25, has_more: false } });
        });
        await page.goto("/operations");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Action history unavailable");
        await expect(alert).toContainText("Mission Control could not load action history.");
        await expect(page.getByRole("heading", { name: "This page could not load" })).toHaveCount(0);
        if (width < 1024) {
            await page.getByRole("button", { name: "Open navigation" }).click();
            await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
            await page.getByRole("button", { name: "Close navigation" }).click();
        }

        await page.getByRole("button", { name: "Refresh history" }).click();
        await expect(page.getByText("No actions recorded", { exact: true })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`invalid retention details keep action deletion disabled at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/ops/actions/summary", route => route.fulfill({ json: {
            entry_count: 0,
            max_entries: 5000,
            retention_days: 0,
            oldest_entry_at: null,
            newest_entry_at: null,
        } }));
        await page.goto("/operations");

        await expect(page.getByText("Retention details are unavailable.", { exact: true })).toBeVisible();
        await page.getByText("Export or delete history", { exact: true }).click();
        await expect(page.getByRole("button", { name: "Delete expired entries" })).toBeDisabled();
        await expect(page.getByText("This page could not load")).toHaveCount(0);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed lifecycle details leave maintenance history readable at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/**", async (route) => {
            const path = new URL(route.request().url()).pathname;
            if (path.endsWith("/workflows")) {
                return route.fulfill({ json: {
                    items: [{ workflow_id: "malformed-maintenance", workflow_source: "candidate",
                        workflow_state: "completed", effect_kind: "operational_action",
                        execution_intent: "restart-service", candidate_id: null, planning_session_id: null,
                        repository: null, target_id: "110", last_result_summary: "verified", timeline: [] }],
                    total: 1, limit: 10, offset: 0,
                } });
            }
            if (path.endsWith("/workflows/malformed-maintenance/operational-lifecycle")) {
                return route.fulfill({ json: { ...operationalLifecycle({ workflow_id: "malformed-maintenance" }), target_label: 42 } });
            }
            if (path.endsWith("/workflows/malformed-maintenance/recovery-diagnostic")) {
                return route.fulfill({ json: operationalDiagnostic({
                    correlation: { ...operationalDiagnostic().correlation, workflow_id: "malformed-maintenance" },
                }) });
            }
            return route.fulfill({ status: 404, json: { detail: "Not found" } });
        });
        await page.goto("/operations/history");

        const itemHeading = page.getByRole("heading", { name: "Maintenance target 110" });
        await expect(itemHeading).toBeVisible();
        await expectResponsiveMainPadding(itemHeading, width);
        await expect(page.getByText("Could not load request details. Target and timing information may be incomplete. Use Refresh history to try again.")).toBeVisible();
        await expect(page.getByText("42", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Requested action: Restart Service", { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "Healthy", exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [390, 1280]) {
    test(`unknown recovery status is shown as unavailable at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/**", async (route) => {
            const path = new URL(route.request().url()).pathname;
            if (path.endsWith("/workflows")) {
                return route.fulfill({ json: {
                    items: [{ workflow_id: "malformed-diagnostic", workflow_source: "candidate",
                        workflow_state: "completed", effect_kind: "operational_action",
                        execution_intent: "restart-service", candidate_id: null, planning_session_id: null,
                        repository: null, target_id: "110", last_result_summary: "verified", timeline: [] }],
                    total: 1, limit: 10, offset: 0,
                } });
            }
            if (path.endsWith("/workflows/malformed-diagnostic/operational-lifecycle")) {
                return route.fulfill({ json: operationalLifecycle({ workflow_id: "malformed-diagnostic" }) });
            }
            if (path.endsWith("/workflows/malformed-diagnostic/recovery-diagnostic")) {
                return route.fulfill({ json: { ...operationalDiagnostic(), diagnostic_status: "execution_confirmed" } });
            }
            return route.fulfill({ status: 404, json: { detail: "Not found" } });
        });
        await page.goto("/operations/history");

        await expect(page.getByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        await expect(page.getByText("Requested action: Restart Service · Latest maintenance status: Unavailable", { exact: true })).toBeVisible();
        await expect(page.getByText("Maintenance status details unavailable")).toBeVisible();
        await expect(page.getByText("A problem checking status does not mean the maintenance request failed.")).toBeVisible();
        await expect(page.getByText("execution confirmed", { exact: false })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`malformed workflow audit can recover with a read-only retry at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows/audit-recovery/audit", (route) => {
            reads += 1;
            return reads === 1
                ? route.fulfill({ json: { ...workflowAudit(), workflow_id: "audit-recovery", timeline: [null] } })
                : route.fulfill({ json: workflowAudit({
                    workflow_id: "audit-recovery",
                    workflow: { ...workflowAudit().workflow, workflow_id: "audit-recovery" },
                }) });
        });
        await page.goto("/workflows/audit-recovery/audit");
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Workflow history");
        await expect(page).toHaveTitle("Workflow history | Atlas Mission Control");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Workflow history unavailable");
        await expectResponsiveMainPadding(alert, width);
        await expect(alert).toContainText("Atlas couldn’t load this workflow’s history. Try again to see its activity.");
        const technicalDetails = alert.locator("details");
        await expect(technicalDetails).not.toHaveAttribute("open", "");
        await expect(technicalDetails.getByText("Malformed workflow audit payload.")).not.toBeVisible();
        await technicalDetails.locator("summary").click();
        await expect(technicalDetails).toContainText("Malformed workflow audit payload.");
        await expect(page.getByRole("heading", { name: "Workflow history", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("heading", { name: "Workflow history", exact: true })).toBeVisible();
        await expectResponsiveMainPadding(page.getByRole("heading", { name: "Workflow history", exact: true }), width);
        await expect(page.getByText("candidate-123", { exact: true })).toHaveCount(1);
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}

for (const width of [320, 390, 1280]) {
    test(`unreadable workflow details hide stage controls until a valid read at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/agent-api/api/v1/agent/workflows/detail-recovery/implementation-request", (route) => {
            reads += 1;
            return reads === 1
                ? route.fulfill({ json: { workflow_id: "detail-recovery", effect_kind: "repository_change" } })
                : route.fulfill({ json: workflowDetail({ workflow_id: "detail-recovery" }) });
        });
        await page.goto("/workflows/detail-recovery");
        await expect(page.getByTestId("mc-context")).toContainText("Current page: Workflow details");
        await expect(page).toHaveTitle("Workflow details | Atlas Mission Control");

        const alert = page.getByRole("alert");
        await expect(alert).toContainText("Workflow unavailable");
        await expectResponsiveMainPadding(alert, width);
        await expect(alert).toContainText("Atlas couldn’t read this workflow’s details. Try again to reload them.");
        const technicalDetails = alert.locator("details");
        await expect(technicalDetails).not.toHaveAttribute("open");
        await expect(technicalDetails).toContainText("Malformed workflow detail payload.");
        await expect(technicalDetails.getByText("Malformed workflow detail payload.", { exact: true })).toBeHidden();
        await expect(page.getByRole("button", { name: "Approve Implementation" })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Run approved change" })).toHaveCount(0);

        await page.getByRole("button", { name: "Try again" }).click();
        await expect(page.getByRole("heading", { name: "Review workflow", exact: true })).toBeVisible();
        await expectResponsiveMainPadding(page.getByRole("heading", { name: "Review workflow", exact: true }), width);
        await expect(page.getByRole("button", { name: "Approve Implementation" })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(rejectedMutationRequests).toEqual([]);
    });
}
