import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAtlasAgent } from "../hooks/useAtlasAgent";
import { AtlasAgentPanel } from "./AtlasAgentPanel";

vi.mock("../hooks/useAtlasAgent", () => ({
    useAtlasAgent: vi.fn(),
}));

const mockedUseAtlasAgent = vi.mocked(useAtlasAgent);

describe("AtlasAgentPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("displays published repository and workflow status", () => {
        mockedUseAtlasAgent.mockReturnValue({
            repository: {
                root: "/opt/atlas",
                branch: "feature/atlas-agent",
                head_commit: "7661770",
                is_clean: true,
                modified_files: [],
                staged_files: [],
                untracked_files: [],
            },
            sprint: {
                checkpoint_id: "A7B",
                title: "Mission Control integration",
                goal: "Display Atlas Agent status.",
                phase: "implementation",
            },
            verification: {
                repository_root: "/opt/atlas",
                status: "passed",
                duration_seconds: 1.5,
                results: [],
            },
            review: {
                request_id: "review-1",
                checkpoint_id: "A7B",
                status: "approved",
                findings: [],
                recommendations: [],
            },
            approvals: [],
            isLoading: false,
            error: null,
        });

        render(<AtlasAgentPanel />);

        expect(
            screen.getByRole("heading", { name: "Atlas Agent" }),
        ).toBeInTheDocument();
        expect(screen.getByText("/opt/atlas")).toBeInTheDocument();
        expect(
            screen.getByText("feature/atlas-agent"),
        ).toBeInTheDocument();
        expect(
            screen.getByText(/A7B: Mission Control integration/),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Status: passed"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Status: approved"),
        ).toBeInTheDocument();
    });

    it("shows unpublished workflow resources without hiding the repository", () => {
        mockedUseAtlasAgent.mockReturnValue({
            repository: {
                root: "/opt/atlas",
                branch: null,
                head_commit: null,
                is_clean: false,
                modified_files: [],
                staged_files: [],
                untracked_files: ["logs/"],
            },
            sprint: null,
            verification: null,
            review: null,
            approvals: [],
            isLoading: false,
            error: null,
        });

        render(<AtlasAgentPanel />);

        expect(screen.getByText("/opt/atlas")).toBeInTheDocument();
        expect(screen.getByText("Detached")).toBeInTheDocument();
        expect(screen.getByText("Unknown")).toBeInTheDocument();
        expect(
            screen.getByText("Working tree has changes"),
        ).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(
            screen.getAllByText("Not published yet"),
        ).toHaveLength(3);
    });

    it("shows only the panel unavailable state after a request failure", () => {
        mockedUseAtlasAgent.mockReturnValue({
            repository: null,
            sprint: null,
            verification: null,
            review: null,
            approvals: [],
            isLoading: false,
            error: "Atlas Agent unavailable.",
        });

        render(<AtlasAgentPanel />);

        expect(screen.getByRole("alert")).toHaveTextContent(
            "Atlas Agent unavailable.",
        );
        expect(
            screen.queryByText("Repository"),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByText("Not published yet"),
        ).not.toBeInTheDocument();
    });
});
