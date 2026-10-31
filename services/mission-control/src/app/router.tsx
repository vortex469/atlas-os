import type { ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";

import { RouteLayout } from "../layouts/RouteLayout";
import { MissionControlPage } from "../pages/MissionControlPage";
import { PageErrorPage } from "../pages/PageErrorPage";
import { NotFoundPage } from "../pages/NotFoundPage";

// A rejected lazy import can leave an initial deep link without page content.
// Keep an eager recovery screen available even when that module never loads.
async function loadPage(load: () => Promise<{ Component: ComponentType }>) {
    try {
        return await load();
    } catch {
        return { Component: PageErrorPage };
    }
}

export const router = createBrowserRouter([
    {
        path: "/",
        element: <RouteLayout />,
        hydrateFallbackElement: <p role="status" className="p-8 text-slate-300">Loading page...</p>,
        children: [
            {
                index: true,
                element: <MissionControlPage />,
            },
            {
                path: "operations",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/OperationsPage")).OperationsPage })),
            },
            {
                path: "operations/request",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/MaintenanceRequestPage")).MaintenanceRequestPage })),
            },
            {
                path: "operations/history",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/OperationalHistoryPage")).OperationalHistoryPage })),
            },
            {
                path: "operations/actions/:auditId",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/ActionHistoryDetailPage")).ActionHistoryDetailPage })),
            },
            {
                path: "providers",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/ProvidersPage")).ProvidersPage })),
            },
            {
                path: "providers/:providerId",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/ProviderPage")).ProviderPage })),
            },
            {
                path: "discovery",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/DiscoveryPage")).DiscoveryPage })),
            },
            {
                path: "discovery/items/:itemId",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/DiscoveryItemPage")).DiscoveryItemPage })),
            },
            {
                path: "execution-candidates",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/ExecutionCandidatesPage")).ExecutionCandidatesPage })),
            },
            {
                path: "execution-candidates/:candidateId",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/ExecutionCandidateDetailPage")).ExecutionCandidateDetailPage })),
            },
            {
                path: "installation/candidate-records/:candidateRecordId/readiness-review",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/InstallationReadinessReviewPage")).InstallationReadinessReviewPage })),
            },
            {
                path: "candidate-planning/:sessionId",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/PlanningSessionPage")).PlanningSessionPage })),
            },
            {
                path: "candidate-planning/:sessionId/workflow",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/WorkflowShellPage")).WorkflowShellPage })),
            },
            {
                path: "workflows",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/WorkflowDashboardPage")).WorkflowDashboardPage })),
            },
            {
                path: "workflows/:workflowId/audit",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/WorkflowAuditPage")).WorkflowAuditPage })),
            },
            {
                path: "workflows/:workflowId",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/WorkflowPage")).WorkflowPage })),
            },
            {
                path: "forge",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/ForgePage")).ForgePage })),
            },
            {
                path: "operator/login",
                lazy: () => loadPage(async () => ({ Component: (await import("../pages/OperatorLoginPage")).OperatorLoginPage })),
            },
            {
                path: "*",
                element: <NotFoundPage />,
            },
        ].map((route) => ({ ...route, errorElement: <PageErrorPage /> })),
    },
]);
