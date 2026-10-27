import { atlas } from "./atlas";
import { parseResourceInventory } from "./resourceInventoryResponse";
import type {
    ProviderResourceCollection,
} from "../types/resources";

export async function getProviderResources(
    providerId: string,
): Promise<ProviderResourceCollection> {
    const response = await atlas.get<unknown>(
        `/providers/${encodeURIComponent(providerId)}/resources`,
    );

    return parseResourceInventory(response.data, providerId);
}

export async function refreshProviderResources(
    providerId: string,
): Promise<ProviderResourceCollection> {
    const response = await atlas.post<unknown>(
        `/providers/${encodeURIComponent(providerId)}/discovery/refresh`,
    );

    return parseResourceInventory(response.data, providerId);
}
