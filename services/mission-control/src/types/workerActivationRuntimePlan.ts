import type { WorkerActivationRuntimeAdmission } from "./workerActivationRuntimeAdmission";

export interface WorkerActivationRuntimePlan extends WorkerActivationRuntimeAdmission {
    runtimePlanId: string;
    design: unknown;
}
