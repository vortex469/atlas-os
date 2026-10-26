import { atlas } from "./atlas";
import { parseConnectionSave, parseConnectionSchema, parseConnectionTest } from "./connectionResponse";
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
    const response = await atlas.get<unknown>(
        `/providers/${encodeURIComponent(providerId)}/connection`,
    );

    return parseConnectionSchema(response.data, providerId);
}

export async function testProviderConnection(
    providerId: string,
    request: TestProviderConnectionRequest,
): Promise<TestProviderConnectionResult> {
    const response = await atlas.post<unknown>(
        `/providers/${encodeURIComponent(providerId)}/connection/test`,
        request,
    );

    return parseConnectionTest(response.data, providerId);
}

export async function updateProviderConnection(
    providerId: string,
    request: UpdateProviderConnectionRequest,
): Promise<UpdateProviderConnectionResult> {
    const response = await atlas.put<unknown>(
        `/providers/${encodeURIComponent(providerId)}/connection`,
        request,
    );

    return parseConnectionSave(response.data, providerId);
}
