import { atlas } from "./atlas";
import type {
    OperatorIntentCreationResponse,
    OperatorIntentResourceCollection,
} from "../types/operatorIntent";

const INTENT_LIFETIME_MS = 15 * 60 * 1000;

export async function getOperatorIntentResources(): Promise<OperatorIntentResourceCollection> {
    const response = await atlas.get<OperatorIntentResourceCollection>(
        "/execution-candidates/operator-intents/resources",
        { withCredentials: true },
    );
    return response.data;
}

export async function requestRestartServiceIntent(
    resourceId: string,
    expectedTargetFingerprint: string,
    csrfToken: string,
    now: Date = new Date(),
): Promise<OperatorIntentCreationResponse> {
    const response = await atlas.post<OperatorIntentCreationResponse>(
        "/execution-candidates/operator-intents",
        {
            execution_intent: "restart-service",
            provider_id: "proxmox",
            resource_id: resourceId,
            resource_type: "qemu",
            expected_target_fingerprint: expectedTargetFingerprint,
            expires_at: new Date(now.getTime() + INTENT_LIFETIME_MS).toISOString(),
        },
        {
            withCredentials: true,
            headers: { "X-Atlas-CSRF-Token": csrfToken },
        },
    );
    return response.data;
}
