import type { WorkerActivationRuntimePrerequisite } from "./workerActivationRuntimePrerequisite";

export interface WorkerActivationRuntimeAdmission extends WorkerActivationRuntimePrerequisite {
    runtimeAdmissionId: string;
    lineage: { record: unknown; status: unknown };
}
