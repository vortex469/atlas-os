import { atlas } from "./atlas";
import type {
    ProviderResourceCollection,
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
