import { discoveryItemsPage, executionCandidates, expect, providers, test } from "./mission-control-fixtures";
import { operationalLifecycle } from "../src/test/operationalLifecycle";

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
    await page.getByRole("button", { name: "Reload actions" }).click();
    await expect(page.getByText("No actions are available for this provider.")).toBeVisible();
    expect(reads).toBe(2);
    expect(rejectedMutationRequests).toEqual([]);
});

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
    await expect(page.getByRole("heading", { name: "Provider actions", exact: true })).toBeVisible();
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
    await expect(page.getByRole("alert")).toContainText("does not match this audit link");
    await expect(page.getByRole("alert")).not.toContainText("Try again.");
    await expect(page.getByRole("heading", { name: "Audit details" })).toBeVisible();
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "← Back to action history" }).click();
    await expect(page.getByRole("heading", { name: "Action history", exact: true })).toBeVisible();
});

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
            : route.fulfill({ json: { workflow_id: "other", workflow: { workflow_id: "other" } } });
    });
    await page.goto("/workflows/audit-recovery/audit");
    await expect(page.getByRole("heading", { name: "Workflow audit unavailable" })).toBeVisible();
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("alert")).toContainText("does not match this workflow");
    await expect(page.getByRole("alert")).not.toContainText("Try loading it again.");
    await expect(page.getByRole("link", { name: "← Back to Workflow" })).toHaveAttribute("href", "/workflows/audit-recovery");
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("discovery refuses another catalog item's details", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/api/v1/discovery/items/requested-item", (route) => route.fulfill({ json: { item: { id: "other" } } }));
    await page.route("**/api/v1/discovery/items/requested-item/relationships", (route) => route.fulfill({ json: { item_id: "requested-item", incoming: [], outgoing: [] } }));
    await page.goto("/discovery/items/requested-item");
    await expect(page.getByRole("alert")).toContainText("does not match this item");
    await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "← Catalog" }).click();
    await expect(page.getByRole("heading", { name: "Browse the catalog", exact: true })).toBeVisible();
});

for (const width of [390, 1280]) {
    test(`related proposals can retry without leaving the catalog item at ${width}px`, async ({ page, rejectedMutationRequests }) => {
        let reads = 0;
        const entry = discoveryItemsPage.entries[0];
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/discovery/items/fixture-app", (route) => route.fulfill({ json: entry }));
        await page.route("**/api/v1/discovery/items/fixture-app/relationships", (route) => route.fulfill({ json: {
            item_id: "fixture-app", incoming: [], outgoing: [],
        } }));
        await page.route("**/api/v1/discovery/proposals**", (route) => {
            reads += 1;
            return reads <= 2
                ? route.fulfill({ status: 503, json: { detail: "PRIVATE_PROPOSAL_ERROR" } })
                : route.fulfill({ json: { proposals: [], total: 0, limit: 25 } });
        });
        await page.goto("/discovery/items/fixture-app");

        const proposals = page.getByRole("region", { name: "Operator proposals" });
        await expect(proposals.getByRole("alert")).toContainText("Related proposals are temporarily unavailable");
        await expect(proposals.getByRole("alert")).not.toContainText("PRIVATE_PROPOSAL_ERROR");
        await proposals.getByRole("button", { name: "Retry related proposals" }).click();
        await expect(proposals.getByText("No related proposals are available.")).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(3);
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
            return reads <= 2
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
        await expect(evidence.getByRole("alert")).toContainText("Dynamic evidence unavailable");
        await expect(evidence.getByRole("alert")).not.toContainText("PRIVATE_EVIDENCE_ERROR");
        await evidence.getByRole("button", { name: "Retry source evidence" }).click();
        await expect(evidence.getByText("Curated catalog only")).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(3);
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
            return reads <= 2
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

        const grounding = page.getByRole("region", { name: "Image grounding" });
        await expect(grounding.getByRole("status")).toContainText("Image grounding is currently unavailable due to a local source or read failure.");
        await expect(grounding.getByRole("status")).not.toContainText("PRIVATE_GROUNDING_ERROR");
        await grounding.getByRole("button", { name: "Retry image grounding" }).click();
        await expect(grounding.getByText("No deployment binding").first()).toBeVisible();
        await expect(page.getByRole("heading", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(3);
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
        await expect(panel.getByText("1 unresolved blocker; this plan is not executable.")).toBeVisible();
        const details = panel.locator("details").filter({ hasText: "Plan details" });
        expect(await details.evaluate((element) => (element as HTMLDetailsElement).open)).toBe(false);
        await expect(panel.getByText("a".repeat(64))).toBeHidden();
        await panel.getByText("Plan details", { exact: true }).click();
        await expect(panel.getByText("a".repeat(64))).toBeVisible();
        expect(rejectedMutationRequests).toEqual([]);
        expect(await page.evaluate((maxWidth) => document.documentElement.scrollWidth <= maxWidth, width)).toBe(true);
    });
}

test("workflow recovery retries only the read and keeps a way back", async ({ page }) => {
    let reads = 0;
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/agent-api/**/workflows/recovery-workflow/implementation-request", (route) => {
        reads += 1;
        return reads === 1
            ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
            : route.fulfill({ json: { workflow_id: "different-workflow" } });
    });
    await page.goto("/workflows/recovery-workflow");
    await expect(page.getByRole("heading", { name: "Workflow unavailable" })).toBeVisible();
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("alert")).toContainText("does not match this page");
    await expect(page.getByRole("alert")).not.toContainText("Try loading it again.");
    expect(reads).toBe(2);
    await expect(page.getByRole("button", { name: "Approve Implementation" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "← All workflows" }).click();
    await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
});

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
        if (wrongIdentity) {
            await expect(page.getByRole("heading", { name: "Planning session unavailable" })).toBeVisible();
            await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
        } else {
            await expect(page.getByText("Planning is unavailable for this session.")).toBeVisible();
        }
        await expect(page.getByRole("button", { name: "Generate Plan" })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Create Workflow" })).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    test(`unknown pages retain navigation at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await page.goto("/page-that-does-not-exist");
        await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
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

for (const width of [390, 1280]) {
    test(`an empty provider catalog has a clear way back at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.route("**/api/v1/providers", (route) => route.fulfill({
            status: 200, contentType: "application/json", body: "[]",
        }));
        await page.goto("/providers/proxmox");
        await expect(page.getByRole("heading", { name: "Provider not found" })).toBeVisible();
        await expect(page.getByText("Not updated yet")).not.toBeVisible();
        await expect(page.getByText("This provider is not in the current catalog.")).toBeVisible();
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
        if (width < 1024) await page.getByRole("button", { name: "Open navigation" }).click();
        await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
        if (width < 1024) await page.getByRole("button", { name: "Close navigation" }).click();
        await expect(page.getByRole("heading", { name: "This page could not load" })).toHaveCount(0);
        await expect(page.getByText(/TypeError:|Cannot read properties/)).toHaveCount(0);
        await page.getByRole("button", { name: "Retry catalog load" }).click();

        await expect(page.getByRole("link", { name: "Fixture Application" })).toBeVisible();
        expect(reads).toBe(2);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

for (const width of [390, 1280]) {
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
        await expect(page.getByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        await expect(page.getByText("proxmox/qemu/110", { exact: true })).toBeHidden();
        await expect(page.getByRole("combobox", { name: "Latest result", exact: true })).toBeVisible();
        await expect(page.getByRole("combobox", { name: "Requested action", exact: true })).toBeHidden();
        await page.getByText("More filters", { exact: true }).click();
        await expect(page.getByRole("combobox", { name: "Requested action", exact: true })).toBeVisible();
        await page.getByRole("combobox", { name: "Requested action", exact: true }).selectOption("restart-service");
        await expect(page.getByText("Additional filters are applied")).toBeVisible();
        await page.getByRole("combobox", { name: "Latest result", exact: true }).selectOption("unavailable");
        await expect(page.getByRole("heading", { name: "Virtual machine 110" })).toBeVisible();
        await expect(page.getByText("A diagnostic network failure is not an operational failure.")).toBeVisible();
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await expect(page.getByText("Workflow State", { exact: true })).toBeHidden();
        await page.getByText("Workflow details", { exact: true }).click();
        await expect(page.getByText("Workflow State", { exact: true })).toBeVisible();
        await expect(page.getByText("proxmox/qemu/110", { exact: true })).toBeVisible();
        await expect(page.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/maintenance-test");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(reads).toBe(1);
    });
}

for (const width of [390, 1280]) {
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

        await expect(page.getByRole("alert")).toContainText("Could not load maintenance history.");
        await expect(page.getByRole("alert")).toContainText("A loading problem does not tell us whether maintenance failed.");
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
    test(`provider registry is reachable and links back from details at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/");
        await page.getByRole("link", { name: "View provider registry", exact: true }).click();
        await expect(page).toHaveURL(/\/providers$/);
        await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
        await expect(page.getByLabel("Current page: Providers", { exact: true })).toBeVisible();
        await expect(page.getByText("Check time unavailable.", { exact: true })).toHaveCount(0);
        await page.getByRole("link", { name: "Open Proxmox provider", exact: true }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
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
    await expect(page.getByRole("heading", { name: "Providers could not load" })).toBeVisible();
    await expect(page.getByText("Try again to get the latest provider list.")).toHaveCount(0);
    await expect(page.getByText("PRIVATE_SERVER_ERROR")).toHaveCount(0);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("link", { name: "Open Proxmox provider" })).toBeVisible();
    expect(attempts).toBe(2);
});

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
        await expect(alert).toContainText("Mission Control could not load this execution candidate.");
        await expect(alert).not.toContainText("PRIVATE_BACKEND_DETAIL");
        await alert.getByRole("button", { name: "Retry loading proposal" }).click();
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
        await expect(alert).toContainText("History unavailable");
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
