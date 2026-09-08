import type { WorkerActivationRuntimePrerequisite } from "./workerActivationRuntimePrerequisite";

export interface WorkerActivationRuntimeAdmission extends WorkerActivationRuntimePrerequisite {
    exactRecord: unknown;
    runtimeAdmissionId: string;
    lineage: { record: unknown; status: unknown };
}
