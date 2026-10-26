import { useNavigation } from "react-router-dom";

import { MainLayout } from "./MainLayout";

export function RouteLayout() {
    const navigation = useNavigation();
    return <MainLayout navigationPending={navigation.state === "loading"} />;
}
