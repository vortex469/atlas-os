import axios from "axios";
import { parse } from "yaml";

import type { DeploymentAnalysisResponse } from "../features/forge/types";

const ATLAS_API_BASE_URL =
    import.meta.env.VITE_ATLAS_API_BASE_URL ?? "/api/v1";

export const atlas = axios.create({
    baseURL: ATLAS_API_BASE_URL,
    timeout: 15_000,
    headers: {
        Accept: "application/json",
    },
});

export async function analyzeCompose(
    compose: string,
    reference: string,
): Promise<DeploymentAnalysisResponse> {
    const response =
        await atlas.post<DeploymentAnalysisResponse>(
            "/analysis/deployments",
            {
                source: "compose",
                reference,
                document: parse(compose),
            },
        );

    return response.data;
}
