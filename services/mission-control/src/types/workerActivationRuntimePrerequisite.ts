import { CLOSED_QUEUE_AUTHORITY } from "./controlledWorkerQueueReceipt";
import type { FingerprintV1 } from "./installationReadinessReview";

export const CLOSED_RUNTIME_AUTHORITY = [...CLOSED_QUEUE_AUTHORITY,
    "queue_adapter_defined", "queue_contact_allowed", "queue_claim_allowed", "queue_lease_allowed", "queue_ack_allowed",
    "worker_discovery_allowed", "worker_registration_allowed", "worker_start_admission_build_allowed",
    "execution_start_admission_build_allowed", "runtime_effect_allowed",
] as const;

export interface WorkerActivationRuntimePrerequisite {
    prerequisiteId: string;
    admissionId: string;
    candidateId: string;
    operatorId: string;
    recordedAt: string;
    validUntil: string;
    evaluatedAt: string;
    lifecycle: "active" | "expired";
    exactDuplicate: boolean;
    blockers: string[];
    fingerprints: Record<string, FingerprintV1>;
    authority: Record<typeof CLOSED_RUNTIME_AUTHORITY[number], false>;
}
