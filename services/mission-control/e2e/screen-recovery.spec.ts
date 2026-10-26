import { executionCandidates, expect, providers, test } from "./mission-control-fixtures";

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
    await expect(page.getByText("Loading provider actions...")).toBeVisible();
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
            : route.fulfill({ json: { id: "other-record" } });
    });
    await page.goto("/operations/actions/record-recovery");
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("alert")).toContainText("does not match this audit link");
    await expect(page.getByRole("heading", { name: "Audit details" })).toBeVisible();
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "← Back to action history" }).click();
    await expect(page.getByRole("heading", { name: "Action History", exact: true })).toBeVisible();
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
    await page.getByRole("link", { name: "← Discovery Center" }).click();
    await expect(page.getByRole("heading", { name: "Provider-neutral catalog", exact: true })).toBeVisible();
});

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
            await expect(page.getByRole("heading", { name: "Planning unavailable" })).toBeVisible();
            await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
        } else {
            await expect(page.getByText("Planning is not available for this session.")).toBeVisible();
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
        await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    });
}

test("an empty provider catalog has a clear way back", async ({ page }) => {
    await page.route("**/api/v1/providers", (route) => route.fulfill({
        status: 200, contentType: "application/json", body: "[]",
    }));
    await page.goto("/providers/proxmox");
    await expect(page.getByRole("heading", { name: "Provider not found" })).toBeVisible();
    await expect(page.getByText("Not updated yet")).not.toBeVisible();
    await page.getByRole("link", { name: "Return to Mission Control" }).click();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
});

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
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByText("workflow-browser-baseline")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflows unavailable" })).not.toBeVisible();
    expect(attempts).toBe(2);
});

test("a broken page keeps navigation and hides raw error details", async ({ page }) => {
    await page.route("**/api/v1/discovery/items?**", (route) => route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ entries: [null], total: 1, offset: 0, limit: 25, has_more: false }),
    }));
    await page.goto("/discovery");
    await expect(page.getByRole("heading", { name: "This page could not load" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Reload page" })).toBeVisible();
    await expect(page.getByText("Unexpected Application Error!")).toHaveCount(0);
    await expect(page.getByText(/TypeError:|Cannot read properties/)).toHaveCount(0);
    await page.getByRole("link", { name: "Return to Mission Control" }).click();
    await expect(page.getByRole("main", { name: "Mission Control command center" })).toBeVisible();
});

test("maintenance history keeps unavailable requests findable and details optional", async ({ page }) => {
    let reads = 0;
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
        if (path.includes("/workflows/maintenance-test/")) {
            await route.fulfill({ status: 503, json: { detail: "Unavailable" } });
            return;
        }
        await route.fallback();
    });
    await page.goto("/operations/history");
    await expect(page.getByRole("heading", { name: "VM 110" })).toBeVisible();
    await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("unavailable");
    await expect(page.getByRole("heading", { name: "VM 110" })).toBeVisible();
    await expect(page.getByText("A diagnostic network failure is not an operational failure.")).toBeVisible();
    await expect(page.getByText("Workflow State", { exact: true })).toBeHidden();
    await page.getByText("Workflow details", { exact: true }).click();
    await expect(page.getByText("Workflow State", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open workflow" })).toHaveAttribute("href", "/workflows/maintenance-test");
    expect(reads).toBe(1);
});

for (const width of [390, 1280]) {
    test(`provider registry is reachable and links back from details at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/");
        await page.getByRole("link", { name: "View provider registry", exact: true }).click();
        await expect(page).toHaveURL(/\/providers$/);
        await expect(page.getByRole("heading", { name: "Providers", exact: true })).toBeVisible();
        await expect(page.getByLabel("Current page: Providers", { exact: true })).toBeVisible();
        await page.getByRole("link", { name: "Open Proxmox provider", exact: true }).click();
        await expect(page).toHaveURL(/\/providers\/proxmox$/);
        await expect(page.getByRole("heading", { name: "Proxmox", exact: true })).toBeVisible();
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
    await expect(page.getByRole("alert")).toHaveText("Providers could not loadTry again to get the latest provider list.Try again");
    await expect(page.getByText("PRIVATE_SERVER_ERROR")).toHaveCount(0);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("link", { name: "Open Proxmox provider" })).toBeVisible();
    expect(attempts).toBe(2);
});

for (const expires_at of [null, "2999-02-30T00:00:00Z"]) {
    test(`proposal planning stays review-only and validates expiry ${expires_at ?? "none"}`, async ({ page }) => {
        const proposal = { ...executionCandidates[0], expires_at };
        await page.route("**/api/v1/execution-candidates/*", (route) => route.fulfill({ json: proposal }));
        await page.goto(`/execution-candidates/${proposal.id}`);
        await expect(page.getByRole("heading", { name: "Update Compose Stack", exact: true, level: 1 })).toBeVisible();
        await expect(page.getByText(proposal.id, { exact: true })).toHaveCount(1);
        await expect(page.getByText("Review this proposal before planning. Planning does not approve or apply a change.")).toBeVisible();
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
    await expect(page.getByText("other-proposal", { exact: true })).toHaveCount(0);
});

test("a missing proposal is distinct from a service outage", async ({ page }) => {
    await page.route("**/api/v1/execution-candidates/*", (route) => route.fulfill({
        status: 404, json: { detail: "PRIVATE_BACKEND_DETAIL" },
    }));
    await page.goto("/execution-candidates/missing-proposal");
    await expect(page.getByRole("heading", { name: "Change proposal not found" })).toBeVisible();
    await expect(page.getByText("PRIVATE_BACKEND_DETAIL")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Start planning" })).toHaveCount(0);
});
