import { atlas } from "./atlas";
import type {
    ProviderResourceCollection,
    UpdateResourceExpectationResult,
} from "../types/resources";

export async function getProviderResources(
    providerId: string,
): Promise<ProviderResourceCollection> {
    const response = await atlas.get<ProviderResourceCollection>(
        `/providers/${encodeURIComponent(providerId)}/resources`,
    );

    return response.data;
}

export async function refreshProviderResources(
    providerId: string,
): Promise<ProviderResourceCollection> {
    const response = await atlas.post<ProviderResourceCollection>(
        `/providers/${encodeURIComponent(providerId)}/discovery/refresh`,
    );

    return response.data;
}

export async function updateProviderResourceExpectation(
    providerId: string,
    resourceId: string,
    expectation: string,
    confirmed: boolean,
): Promise<UpdateResourceExpectationResult> {
    const response = await atlas.put<UpdateResourceExpectationResult>(
        `/providers/${encodeURIComponent(providerId)}/resources/${encodeURIComponent(
            resourceId,
        )}/expectation`,
        {
            expectation,
            confirmed,
        },
    );

    return response.data;
}
