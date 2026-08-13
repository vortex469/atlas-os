import { atlas } from "./atlas";
import type {
    ExecutionCandidate,
    ExecutionCandidateListQuery,
    ExecutionCandidatePage,
} from "../types/executionCandidates";

const DEFAULT_LIMIT = 25;

export async function listExecutionCandidates(
    query: ExecutionCandidateListQuery = {},
): Promise<ExecutionCandidatePage> {
    const response = await atlas.get<ExecutionCandidatePage>("/execution-candidates", {
        params: executionCandidateParams(query),
    });

    return response.data;
}

export async function getExecutionCandidate(
    candidateId: string,
): Promise<ExecutionCandidate> {
    const response = await atlas.get<ExecutionCandidate>(
        `/execution-candidates/${encodeURIComponent(candidateId)}`,
    );

    return response.data;
}

function executionCandidateParams(query: ExecutionCandidateListQuery) {
    return {
        status: query.status || undefined,
        category: query.category || undefined,
        intent: query.intent || undefined,
        source_subsystem: query.sourceSubsystem || undefined,
        target_id: query.targetId || undefined,
        limit: query.limit ?? DEFAULT_LIMIT,
        offset: query.offset ?? 0,
    };
}
