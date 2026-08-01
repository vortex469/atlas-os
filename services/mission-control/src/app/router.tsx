import { createBrowserRouter } from "react-router-dom";

import { DiscoveryItemPage } from "../pages/DiscoveryItemPage";
import { DiscoveryPage } from "../pages/DiscoveryPage";
import { ForgePage } from "../pages/ForgePage";
import { MainLayout } from "../layouts/MainLayout";
import { ActionHistoryDetailPage } from "../pages/ActionHistoryDetailPage";
import { MissionControlPage } from "../pages/MissionControlPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { OperationsPage } from "../pages/OperationsPage";
import { ProviderPage } from "../pages/ProviderPage";
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
                path: "forge",
                element: <ForgePage />,
            },
        ],
    },
    {
        path: "*",
        element: <NotFoundPage />,
    },
]);
