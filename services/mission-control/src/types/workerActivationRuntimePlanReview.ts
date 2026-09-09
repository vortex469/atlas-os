import type { WorkerActivationRuntimePlan } from "./workerActivationRuntimePlan";

export interface WorkerActivationRuntimePlanReview extends Omit<WorkerActivationRuntimePlan, "design"> {
    runtimePlanReviewId: string;
    profile: string;
    findings: string[];
}
