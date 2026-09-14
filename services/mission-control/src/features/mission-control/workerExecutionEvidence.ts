import { listWorkflows } from "../../api/atlas-agent";
import type { WorkflowListResponse, WorkflowSummary } from "../../types/atlasAgent";

import { detailPath } from "./overviewEvidence";

const record = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value);

// Runtime checks are necessary: the existing workflow GET client returns raw JSON.
export function isWorkflowEvidencePage(value: unknown): value is WorkflowListResponse {
    return record(value) && Array.isArray(value.items)
        && Number.isSafeInteger(value.total) && Number(value.total) >= value.items.length
        && Number.isSafeInteger(value.offset) && Number(value.offset) >= 0
        && Number.isSafeInteger(value.limit) && Number(value.limit) > 0
        && value.items.every((item) => record(item)
            && typeof item.workflow_id === "string" && item.workflow_id.trim().length > 0 && !!detailPath("/workflows", item.workflow_id)
            && typeof item.workflow_state === "string"
            && typeof item.last_result_summary === "string"
            && Array.isArray(item.timeline) && item.timeline.every((stage) =>
                record(stage) && typeof stage.name === "string" && typeof stage.status === "string"));
}

export function isCompleteWorkflowEvidence(value: unknown): value is WorkflowListResponse {
    return isWorkflowEvidencePage(value) && value.offset === 0
        && value.total === value.items.length
        && new Set(value.items.map(item => item.workflow_id)).size === value.items.length;
}

export async function fetchAllWorkflowSummary(): Promise<WorkflowListResponse> {
    const pageSize = 200;
    let offset = 0;
    const collected: WorkflowSummary[] = [];
    let expectedTotal: number | null = null;
    const seen = new Set<string>();

    while (true) {
        const page = await listWorkflows({ limit: pageSize, offset });
        if (!isWorkflowEvidencePage(page) || page.offset !== offset) {
            throw new Error("Malformed workflow evidence.");
        }
        expectedTotal ??= page.total;
        if (page.total !== expectedTotal || offset + page.items.length > page.total
            || page.items.some((item) => {
                if (seen.has(item.workflow_id)) return true;
                seen.add(item.workflow_id);
                return false;
            })) {
            throw new Error("Inconsistent workflow evidence.");
        }
        collected.push(...page.items);
        const total = page.total;
        offset += page.items.length;
        if (total <= collected.length) {
            break;
        }
        if (page.items.length === 0 || offset >= 10_000) {
            throw new Error("Incomplete workflow evidence.");
        }
    }

    return {
        items: collected,
        total: collected.length,
        limit: pageSize,
        offset: 0,
    };
}
