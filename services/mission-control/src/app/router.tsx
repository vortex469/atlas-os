import { createBrowserRouter } from "react-router-dom";

import { DiscoveryItemPage } from "../pages/DiscoveryItemPage";
import { DiscoveryPage } from "../pages/DiscoveryPage";
import { ExecutionCandidateDetailPage } from "../pages/ExecutionCandidateDetailPage";
import { ExecutionCandidatesPage } from "../pages/ExecutionCandidatesPage";
import { ForgePage } from "../pages/ForgePage";
import { MainLayout } from "../layouts/MainLayout";
import { ActionHistoryDetailPage } from "../pages/ActionHistoryDetailPage";
import { MissionControlPage } from "../pages/MissionControlPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { OperationsPage } from "../pages/OperationsPage";
import { OperationalHistoryPage } from "../pages/OperationalHistoryPage";
import { MaintenanceRequestPage } from "../pages/MaintenanceRequestPage";
import { OperatorLoginPage } from "../pages/OperatorLoginPage";
import { PlanningSessionPage } from "../pages/PlanningSessionPage";
import { ProviderPage } from "../pages/ProviderPage";
import { WorkflowPage } from "../pages/WorkflowPage";
import { WorkflowDashboardPage } from "../pages/WorkflowDashboardPage";
import { WorkflowShellPage } from "../pages/WorkflowShellPage";
import { WorkflowAuditPage } from "../pages/WorkflowAuditPage";
export const router = createBrowserRouter([
    {
        path: "/",
        element: <MainLayout />,
        children: [
            {
                index: true,
                element: <MissionControlPage />,
            },
            {
                path: "operations",
                element: <OperationsPage />,
            },
            {
                path: "operations/request",
                element: <MaintenanceRequestPage />,
            },
            {
                path: "operations/history",
                element: <OperationalHistoryPage />,
            },
            {
                path: "operations/actions/:auditId",
                element: <ActionHistoryDetailPage />,
            },
            {
                path: "providers/:providerId",
                element: <ProviderPage />,
            },
            {
                path: "discovery",
                element: <DiscoveryPage />,
            },
            {
                path: "discovery/items/:itemId",
                element: <DiscoveryItemPage />,
            },
            {
                path: "execution-candidates",
                element: <ExecutionCandidatesPage />,
            },
            {
                path: "execution-candidates/:candidateId",
                element: <ExecutionCandidateDetailPage />,
            },
            {
                path: "candidate-planning/:sessionId",
                element: <PlanningSessionPage />,
            },
            {
                path: "candidate-planning/:sessionId/workflow",
                element: <WorkflowShellPage />,
            },
            {
                path: "workflows",
                element: <WorkflowDashboardPage />,
            },
            {
                path: "workflows/:workflowId/audit",
                element: <WorkflowAuditPage />,
            },
            {
                path: "workflows/:workflowId",
                element: <WorkflowPage />,
            },
            {
                path: "forge",
                element: <ForgePage />,
            },
            {
                path: "operator/login",
                element: <OperatorLoginPage />,
            },
        ],
    },
    {
        path: "*",
        element: <NotFoundPage />,
    },
]);
