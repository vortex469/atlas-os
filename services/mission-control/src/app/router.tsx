import { createBrowserRouter } from "react-router-dom";

import { MainLayout } from "../layouts/MainLayout";
import { MissionControlPage } from "../pages/MissionControlPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { ProviderPage } from "../pages/ProviderPage";
import { ForgePage } from "../pages/ForgePage";

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
                path: "providers/:providerId",
                element: <ProviderPage />,
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
