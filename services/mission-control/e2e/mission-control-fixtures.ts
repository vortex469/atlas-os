/* eslint-disable react-hooks/rules-of-hooks */
import { expect, test as base } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

type MockMode = "available" | "core-unavailable";

type MissionControlFixtures = {
    mockMode: MockMode;
    rejectedMutationRequests: string[];
};

const isoNow = "2026-09-06T12:00:00.000Z";

const aceSummary = {
    score: 92,
    status: "healthy",
    summary: "Baseline browser fixture: Atlas presentation data loaded.",
    findings: [],
    assessments: [],
    recommendations: [
        {
            title: "Review pending workflow approvals",
            reason: "One workflow is awaiting operator review.",
            priority: "medium",
            confidence: 0.86,
            estimated_effort: "5 minutes",
            component: "atlas-agent",
        },
    ],
    telemetry: {
        provider_collection_duration_ms: 37,
        provider_timeout_seconds: 3,
        providers: [
            {
                provider_id: "proxmox",
                provider_name: "Proxmox",
                status: "completed",
                duration_ms: 21,
                finding_count: 0,
            },
        ],
    },
};

const health = {
    atlas: "healthy",
    services: {
        proxmox: {
            provider_id: "proxmox",
            status: "healthy",
            latency_ms: 12,
            http_status: 200,
            message: "Mocked provider is reachable.",
            details: {},
        },
    },
};

const providers = [
    {
        id: "proxmox",
        name: "Proxmox",
        workspace: "homelab",
        priority: "critical",
        version: "mock-v1",
        description: "Virtualization provider fixture for browser regression coverage.",
        icon: "server",
        capabilities: ["vm-inventory"],
        health: {
            status: "healthy",
            latency_ms: 12,
            http_status: 200,
            message: "Mocked provider is reachable.",
            details: { critical: true },
        },
    },
];

const policies = {
    proxmox: { guests: {} },
    docker: { containers: {} },
    homeassistant: { ignored_entities: [] },
    opnsense: {
        pending_update_warning_threshold: null,
        reboot_required_severity: "warning",
    },
    frigate: { cameras: {}, stalled_camera_severity: "warning" },
    obsidian: {
        minimum_note_count: 1,
        stale_after_days: null,
        insufficient_notes_severity: "warning",
        stale_severity: "warning",
        scan_truncated_severity: "warning",
    },
    qdrant: {
        expected_collections: [],
        missing_collection_severity: "warning",
        empty_instance_severity: "warning",
    },
    n8n: {
        expected_active_workflows: [],
        inactive_workflow_severity: "warning",
        scan_truncated_severity: "warning",
        empty_instance_severity: "warning",
    },
    intelligence: { providers: {} },
};

const policyStatus = {
    status: "healthy",
    source_exists: true,
    checked_at: isoNow,
    loaded_at: isoNow,
    duration_ms: 4,
    error: null,
    diagnostics: [],
};

const workflows = [
    {
        workflow_id: "workflow-browser-baseline",
        workflow_source: "candidate",
        workflow_state: "awaiting_implementation_approval",
        planning_session_id: "plan-browser-baseline",
        candidate_id: "candidate-browser-baseline",
        candidate_fingerprint: "candidate-fingerprint",
        plan_fingerprint: "plan-fingerprint",
        implementation_approval_status: "pending",
        repository: "/workspace/atlas",
        working_directory: "/workspace/atlas",
        translator_version: "mock-v1",
        affected_files: ["services/mission-control/src/App.tsx"],
        effect_kind: "repository_change",
        execution_intent: "update-compose-stack",
        target_id: "atlas",
    },
];

const workflowPage = {
    items: workflows,
    total: workflows.length,
    limit: 200,
    offset: 0,
};

const executionCandidates = [
    {
        id: "candidate-browser-baseline",
        source_recommendation_id: "recommendation-1",
        source_subsystem: "ace",
        recommendation_class: "maintenance",
        catalog_item_id: null,
        target_id: "atlas",
        target_type: "service",
        execution_category: "update",
        execution_intent: "update-compose-stack",
        status: "eligible",
        required_approval_level: "standard",
        rationale: "Browser fixture candidate.",
        constraints: [],
        evidence_ids: [],
        compatibility_assessment_id: null,
        compatibility_status: "compatible",
        relationship_ids: [],
        created_at: isoNow,
        expires_at: "2026-09-07T12:00:00.000Z",
    },
    {
        id: "candidate-not-eligible",
        source_recommendation_id: "recommendation-2",
        source_subsystem: "ace",
        recommendation_class: "maintenance",
        target_id: "atlas-agent",
        target_type: "service",
        execution_category: "restart",
        execution_intent: "restart-service",
        status: "not_eligible",
        required_approval_level: "standard",
        rationale: "Not eligible browser fixture candidate.",
        constraints: [],
        evidence_ids: [],
        compatibility_status: "blocked",
        relationship_ids: [],
        created_at: isoNow,
        expires_at: null,
    },
    {
        id: "candidate-expired",
        source_recommendation_id: "recommendation-3",
        source_subsystem: "ace",
        recommendation_class: "maintenance",
        target_id: "home-assistant",
        target_type: "service",
        execution_category: "update",
        execution_intent: "update-container-image",
        status: "expired",
        required_approval_level: "standard",
        rationale: "Expired browser fixture candidate.",
        constraints: [],
        evidence_ids: [],
        compatibility_status: "unsupported",
        relationship_ids: [],
        created_at: isoNow,
        expires_at: isoNow,
    },
];

const executionCandidatePage = {
    candidates: executionCandidates,
    total: executionCandidates.length,
    limit: 100,
    offset: 0,
    has_more: false,
};

const agentInfo = {
    app_name: "atlas-agent",
    version: "browser-fixture",
    environment: "test",
    repository_root: "/workspace/atlas",
    supported_workflow_phases: ["planning", "implementation", "verification"],
    supported_verification_statuses: ["passed", "failed"],
    install_container: {
        contract_schema: "agent-install-container-validation-v1",
        operation: "install-container",
        mode: "validate-only",
        capability_status: "unsupported",
        default_enabled: false,
        execution_supported: false,
        dispatch_allowed: false,
        mutation_allowed: false,
        replay_allowed: false,
        runtime: "unsupported",
        filesystem: "read-only",
        network: "none",
        home_assistant_status: "blocked",
        validation_result_available: false,
    },
};

const repository = {
    root: "/workspace/atlas",
    branch: "main",
    head_commit: "0123456789abcdef",
    is_clean: true,
    modified_files: [],
    staged_files: [],
    untracked_files: [],
};

const discoveryMetadata = {
    generated_at: isoNow,
    total_items: 1,
    item_types: ["application"],
    statuses: ["active"],
    tags: ["browser-fixture"],
    capabilities: ["read-only"],
};

const discoveryItemsPage = {
    entries: [
        {
            id: "fixture-app",
            name: "Fixture Application",
            item_type: "application",
            status: "active",
            summary: "Read-only browser regression fixture item.",
            description: "Read-only browser regression fixture item.",
            tags: ["browser-fixture"],
            capabilities: ["read-only"],
            links: [],
            evidence_ids: [],
            relationship_ids: [],
            created_at: isoNow,
            updated_at: isoNow,
        },
    ],
    total: 1,
    limit: 25,
    offset: 0,
    has_more: false,
};

const actionHistoryPage = {
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
    has_more: false,
};

const actionHistorySummary = {
    total_entries: 0,
    succeeded_entries: 0,
    failed_entries: 0,
    oldest_entry_at: null,
    newest_entry_at: null,
    retention_days: 90,
};

function json(route: Route, body: unknown, status = 200) {
    return route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
    });
}

async function mockCore(route: Route, mode: MockMode) {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, "") || "/";

    if (request.method() !== "GET") {
        return json(route, { error: "Browser regression mocks reject mutations." }, 405);
    }

    if (path === "/operator-auth/session") {
        return json(route, { detail: "Unauthenticated browser fixture." }, 401);
    }

    if (mode === "core-unavailable") {
        return json(route, { detail: "Atlas Core unavailable in browser fixture." }, 503);
    }

    switch (path) {
        case "/":
            return json(route, { release: "browser-regression-baseline" });
        case "/ace/summary":
            return json(route, aceSummary);
        case "/health":
            return json(route, health);
        case "/providers":
            return json(route, providers);
        case "/policies":
            return json(route, policies);
        case "/policies/status":
            return json(route, policyStatus);
        case "/intelligence/telemetry/history":
            return json(route, [{ id: "telemetry-1", collected_at: isoNow, telemetry: aceSummary.telemetry }]);
        case "/intelligence/telemetry/history/retention":
            return json(route, {
                entry_count: 1,
                max_entries: 500,
                retention_days: 90,
                oldest_snapshot_at: isoNow,
                newest_snapshot_at: isoNow,
            });
        case "/execution-candidates":
            return json(route, executionCandidatePage);
        case "/ops/actions/page":
            return json(route, actionHistoryPage);
        case "/ops/actions/summary":
            return json(route, actionHistorySummary);
        case "/ops/actions/providers":
            return json(route, []);
        case "/discovery":
            return json(route, discoveryMetadata);
        case "/discovery/items":
            return json(route, discoveryItemsPage);
        default:
            return json(route, { detail: `Unhandled browser fixture Core path: ${path}` }, 404);
    }
}

async function mockAgent(route: Route) {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/agent-api/, "") || "/";

    if (request.method() !== "GET") {
        return json(route, { error: "Browser regression mocks reject mutations." }, 405);
    }

    switch (path) {
        case "/api/v1/agent/info":
            return json(route, agentInfo);
        case "/api/v1/agent/repository":
            return json(route, repository);
        case "/api/v1/agent/sprint":
        case "/api/v1/agent/verification":
        case "/api/v1/agent/review":
            return json(route, { detail: "Not published in browser fixture." }, 404);
        case "/api/v1/agent/approval/pending":
            return json(route, []);
        case "/api/v1/agent/workflows":
            return json(route, workflowPage);
        case "/api/v1/agent/workflows/workflow-browser-baseline/operational-lifecycle":
        case "/api/v1/agent/workflows/workflow-browser-baseline/recovery-diagnostic":
            return json(route, { detail: "Not needed by baseline browser route coverage." }, 404);
        default:
            return json(route, { detail: `Unhandled browser fixture Agent path: ${path}` }, 404);
    }
}

async function installMissionControlMocks(
    page: Page,
    mode: MockMode,
    rejectedMutationRequests: string[],
) {
    page.on("request", (request) => {
        if (
            ["POST", "PUT", "PATCH", "DELETE"].includes(request.method()) &&
            (request.url().includes("/api/v1") || request.url().includes("/agent-api"))
        ) {
            rejectedMutationRequests.push(`${request.method()} ${request.url()}`);
        }
    });

    await page.route("**/api/v1", (route) => mockCore(route, mode));
    await page.route("**/api/v1/**", (route) => mockCore(route, mode));
    await page.route("**/agent-api", (route) => mockAgent(route));
    await page.route("**/agent-api/**", (route) => mockAgent(route));
}

export const test = base.extend<MissionControlFixtures>({
    mockMode: ["available", { option: true }],
    // eslint-disable-next-line no-empty-pattern
    rejectedMutationRequests: async ({}, use) => {
        const requests: string[] = [];
        await use(requests);
        expect(requests).toEqual([]);
    },
    page: async ({ page, mockMode, rejectedMutationRequests }, use) => {
        await installMissionControlMocks(page, mockMode, rejectedMutationRequests);
        await use(page);
    },
});

export { expect } from "@playwright/test";
