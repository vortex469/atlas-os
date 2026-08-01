import { atlas } from "./atlas";
import type {
    ProviderConnectionSchema,
    TestProviderConnectionRequest,
    TestProviderConnectionResult,
    UpdateProviderConnectionRequest,
    UpdateProviderConnectionResult,
} from "../types/connections";

export async function getProviderConnection(
    providerId: string,
): Promise<ProviderConnectionSchema> {
    const response = await atlas.get<ProviderConnectionSchema>(
        `/providers/${encodeURIComponent(providerId)}/connection`,
    );

    return response.data;
}

export async function testProviderConnection(
    providerId: string,
    request: TestProviderConnectionRequest,
): Promise<TestProviderConnectionResult> {
    const response = await atlas.post<TestProviderConnectionResult>(
        `/providers/${encodeURIComponent(providerId)}/connection/test`,
        request,
    );

    return response.data;
}

export async function updateProviderConnection(
    providerId: string,
    request: UpdateProviderConnectionRequest,
): Promise<UpdateProviderConnectionResult> {
    const response = await atlas.put<UpdateProviderConnectionResult>(
        `/providers/${encodeURIComponent(providerId)}/connection`,
        request,
    );

    return response.data;
}
