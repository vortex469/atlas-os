import { useEffect, useState } from "react";

import {
    getAtlasAgentErrorMessage,
    getRepositoryStatus,
    getReviewReport,
    getSprintStatus,
    getVerificationReport,
} from "../api/atlas-agent";
import { getPendingApprovals } from "../api/approval";

import type {
    RepositoryStatus,
    ReviewReport,
    SprintStatus,
    VerificationReport,
} from "../types/atlasAgent";
import type { ApprovalResult } from "../types/approval";

interface AtlasAgentState {
    repository: RepositoryStatus | null;
    sprint: SprintStatus | null;
    verification: VerificationReport | null;
    review: ReviewReport | null;
    approvals: ApprovalResult[];
    isLoading: boolean;
    error: string | null;
}

const initialState: AtlasAgentState = {
    repository: null,
    sprint: null,
    verification: null,
    review: null,
    approvals: [],
    isLoading: true,
    error: null,
};

export function useAtlasAgent(): AtlasAgentState {
    const [state, setState] =
        useState<AtlasAgentState>(initialState);

    useEffect(() => {
        let isCancelled = false;

        async function loadAtlasAgent() {
            try {
                const [
                    repository,
                    sprint,
                    verification,
                    review,
                    approvals,
                ] = await Promise.all([
                    getRepositoryStatus(),
                    getSprintStatus(),
                    getVerificationReport(),
                    getReviewReport(),
                    getPendingApprovals(),
                ]);

                if (!isCancelled) {
                    setState({
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
                        error: getAtlasAgentErrorMessage(
                            requestError,
                            "Mission Control could not load Atlas Agent status.",
                        ),
                    });
                }
            }
        }

        void loadAtlasAgent();

        return () => {
            isCancelled = true;
        };
    }, []);

    return state;
}