import { useEffect, useState } from "react";

import {
    getAtlasAgentErrorMessage,
    getRepositoryStatus,
    getReviewReport,
    getSprintStatus,
    getVerificationReport,
} from "../api/atlas-agent";
import type {
    RepositoryStatus,
    ReviewReport,
    SprintStatus,
    VerificationReport,
} from "../types/atlasAgent";

interface AtlasAgentState {
    repository: RepositoryStatus | null;
    sprint: SprintStatus | null;
    verification: VerificationReport | null;
    review: ReviewReport | null;
    isLoading: boolean;
    error: string | null;
}

const initialState: AtlasAgentState = {
    repository: null,
    sprint: null,
    verification: null,
    review: null,
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
                ] = await Promise.all([
                    getRepositoryStatus(),
                    getSprintStatus(),
                    getVerificationReport(),
                    getReviewReport(),
                ]);

                if (!isCancelled) {
                    setState({
                        repository,
                        sprint,
                        verification,
                        review,
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
