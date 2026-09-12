import type { WorkerActivationRuntimePlanReview } from "./workerActivationRuntimePlanReview";

export interface WorkerActivationRuntimeInterfacePrerequisite extends Omit<WorkerActivationRuntimePlanReview, "findings"> {
    runtimeInterfacePrerequisiteId: string;
    inventory: { blocker: string; owner: string; required_proof: string }[];
}
