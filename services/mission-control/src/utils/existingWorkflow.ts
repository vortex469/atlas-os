import type { CandidatePlanningResponse } from "../types/atlasAgent";

function workflowId(session: CandidatePlanningResponse): string | null {
    const id = session.workflow_session_id;
    return typeof id === "string" && id.length > 0 && id !== "." && id !== ".." && id.trim() === id && !Array.from(id).some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127) ? id : null;
}

export function hasExistingWorkflow(session: CandidatePlanningResponse): boolean {
    return typeof session.session_id === "string" && session.session_id.length > 0 && session.planning_failure === null
        && (session.status === "workflow_created" || (session.status === "plan_ready" && workflowId(session) !== null));
}

export function existingWorkflowPath(session: CandidatePlanningResponse): string | null {
    const id = workflowId(session);
    return hasExistingWorkflow(session) && id !== null ? `/workflows/${encodeURIComponent(id)}` : null;
}
