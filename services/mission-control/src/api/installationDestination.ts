import { atlas } from "./atlas";
import type {
    InstallationAdmissionAssessmentV1,
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationCollectionV1,
    ProspectiveInstallationDestinationV1,
} from "../types/installationDestination";

const mutationConfig = (csrfToken: string, idempotencyKey: string) => ({
    withCredentials: true,
    headers: {
        "X-Atlas-CSRF-Token": csrfToken,
        "Idempotency-Key": idempotencyKey,
    },
});

export async function listProspectiveInstallationDestinations(): Promise<ProspectiveInstallationDestinationV1[]> {
    const response = await atlas.get<ProspectiveInstallationDestinationCollectionV1>(
        "/installation/destinations",
        { withCredentials: true },
    );
    return response.data.destinations;
}

export async function selectProspectiveInstallationDestination(
    destination: Pick<ProspectiveInstallationDestinationV1, "resource_id" | "enumeration_token">,
    csrfToken: string,
    idempotencyKey: string,
): Promise<InstallationDestinationSelectionV1> {
    const response = await atlas.post<InstallationDestinationSelectionV1>(
        "/installation/destination-selections",
        destination,
        mutationConfig(csrfToken, idempotencyKey),
    );
    return response.data;
}

export async function assessInstallationAdmission(
    request: { item_id: string; catalog_entry_id: string; plan_fingerprint: string; selection_id: string },
    csrfToken: string,
    idempotencyKey: string,
): Promise<InstallationAdmissionAssessmentV1> {
    const response = await atlas.post<InstallationAdmissionAssessmentV1>(
        "/installation/admission-assessments",
        request,
        mutationConfig(csrfToken, idempotencyKey),
    );
    return response.data;
}

export function installationIdempotencyKey(): string {
    return `mission-control-${crypto.randomUUID()}`;
}
