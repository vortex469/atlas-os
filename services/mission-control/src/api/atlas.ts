import axios from "axios";
import { parse } from "yaml";

import type { DeploymentAnalysisResponse } from "../features/forge/types";

export const atlas = axios.create({
    baseURL: "/atlas-core",
    timeout: 15000,
});

export async function analyzeCompose(
    compose: string,
): Promise<DeploymentAnalysisResponse> {
    const response =
        await atlas.post<DeploymentAnalysisResponse>(
            "/analysis/deployments",
            {
                source: "compose",
                reference: "forge",
                document: parse(compose),
            },
        );

    return response.data;
}