import { isAxiosError } from "axios";
import { useEffect, useState } from "react";

import {
    getAgentInfo,
    getAtlasAgentErrorMessage,
    getRepositoryStatus,
    getReviewReport,
    getSprintStatus,
    getVerificationReport,
} from "../api/atlas-agent";
import { getPendingApprovals } from "../api/approval";

import type {
    AgentInfo,
    RepositoryStatus,
    ReviewReport,
    SprintStatus,
    VerificationReport,
} from "../types/atlasAgent";
import type { ApprovalResult } from "../types/approval";

interface AtlasAgentState {
    info: AgentInfo | null;
    repository: RepositoryStatus | null;
    sprint: SprintStatus | null;
    verification: VerificationReport | null;
    review: ReviewReport | null;
    approvals: ApprovalResult[];
    isLoading: boolean;
    error: string | null;
}

interface AtlasAgentResult extends AtlasAgentState {
    retry: () => void;
}

const initialState: AtlasAgentState = {
    info: null,
    repository: null,
    sprint: null,
    verification: null,
    review: null,
    approvals: [],
    isLoading: true,
    error: null,
};

async function loadOptionalSummary<T>(
    loader: () => Promise<T>,
): Promise<T | null> {
    try {
        return await loader();
    } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
            return null;
        }

        throw error;
    }
}

function getAtlasUnavailableMessage(error: unknown): string {
    if (
        isAxiosError(error) &&
        (error.response?.status === 500 || error.response?.status === 503)
    ) {
        return "Atlas Agent unavailable";
    }

    if (isAxiosError(error) && !error.response) {
        return "Atlas Agent unavailable";
    }

    if (error instanceof Error) {
        return "Atlas Agent unavailable";
    }

    return getAtlasAgentErrorMessage(error, "Atlas Agent unavailable");
}

export function useAtlasAgent(): AtlasAgentResult {
    const [state, setState] =
        useState<AtlasAgentState>(initialState);
    const [loadAttempt, setLoadAttempt] = useState(0);
    const retry = () => {
        setState(initialState);
        setLoadAttempt((attempt) => attempt + 1);
    };

    useEffect(() => {
        let isCancelled = false;

        async function loadAtlasAgent() {
            try {
                const [
                    info,
                    repository,
                    sprint,
                    verification,
                    review,
                    approvals,
                ] = await Promise.all([
                    getAgentInfo(),
                    getRepositoryStatus(),
                    loadOptionalSummary(() => getSprintStatus()),
                    loadOptionalSummary(() => getVerificationReport()),
                    loadOptionalSummary(() => getReviewReport()),
                    getPendingApprovals(),
                ]);

                if (!isCancelled) {
                    setState({
                        info,
                        repository,
                        sprint,
                        verification,
                        review,
                        approvals,
                        isLoading: false,
                        error: null,
                    });
                }
            } catch (requestError) {
                if (!isCancelled) {
                    setState({
                        ...initialState,
                        isLoading: false,
                        error: getAtlasUnavailableMessage(requestError),
                    });
                }
            }
        }

        void loadAtlasAgent();

        return () => {
            isCancelled = true;
        };
    }, [loadAttempt]);

    return { ...state, retry };
}
