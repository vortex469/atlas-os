import { atlas } from "./atlas";
import type {
    ProviderIntentMutationRequest,
    ProviderIntentMutationResult,
    ProviderManagementV3,
} from "../types/providerManagement";

export async function getAuthenticatedProviderManagement(
    providerId: string,
): Promise<ProviderManagementV3> {
    const response = await atlas.get<ProviderManagementV3>(
        `/providers/${encodeURIComponent(providerId)}/management/operator`,
        { withCredentials: true },
    );
    return response.data;
}

export async function putProviderMonitoringIntent(
    providerId: string,
    resourceType: string,
    resourceId: string,
    request: ProviderIntentMutationRequest,
    csrfToken: string,
): Promise<ProviderIntentMutationResult> {
    const response = await atlas.put<ProviderIntentMutationResult>(
        `/providers/${encodeURIComponent(providerId)}/management/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}/monitoring-intent`,
        request,
        {
            withCredentials: true,
            headers: { "X-Atlas-CSRF-Token": csrfToken },
        },
    );
    return response.data;
}
