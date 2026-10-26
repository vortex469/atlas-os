import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { analyzeCompose } from "../../api/atlas";
import { Forge } from "./Forge";
import type { DeploymentAnalysisResponse } from "./types";

vi.mock("../../api/atlas", () => ({ analyzeCompose: vi.fn() }));
const analyze = vi.mocked(analyzeCompose);
function analysis(name: string): DeploymentAnalysisResponse {
    return { result: {
        analysis: { analyzer: "fixture", elapsed_ms: 1, diagnostics: [], plan: {
            id: "plan-1", name, source: "compose", components: [], risk: "low", requires_approval: true,
        } },
        planning: { planner: "fixture", elapsed_ms: 1, warnings: [], proposal: {
            id: "proposal-1", summary: `Review ${name}`, steps: [], risk: "low", approval_required: true,
            rollback_supported: false, estimated_duration_minutes: null,
        } },
    } };
}
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Analyze Deployment" }));

describe("Forge analysis freshness", () => {
    beforeEach(() => { analyze.mockReset().mockResolvedValue(analysis("Original result")); });

    it.each(["Deployment name", "Compose document"])("clears a displayed result when %s changes", async (label) => {
        render(<Forge />);
        submit();
        await screen.findAllByText("Original result");
        fireEvent.change(screen.getByLabelText(label), { target: { value: "new input" } });
        expect(screen.queryByRole("heading", { name: "Deployment Brief" })).not.toBeInTheDocument();
        expect(screen.queryByText("Original result")).not.toBeInTheDocument();
    });

    it("ignores an older success after analysis of the new input finishes", async () => {
        let resolveOld!: (value: DeploymentAnalysisResponse) => void;
        analyze.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
            .mockResolvedValueOnce(analysis("Current result"));
        render(<Forge />);
        submit();
        fireEvent.change(screen.getByLabelText("Deployment name"), { target: { value: " current-name " } });
        submit();
        await screen.findAllByText("Current result");
        await act(async () => resolveOld(analysis("Stale result")));
        expect(screen.queryByText("Stale result")).not.toBeInTheDocument();
        expect(screen.getAllByText("Current result")).toHaveLength(2);
        expect(analyze.mock.calls[1][1]).toBe("current-name");
    });

    it("ignores an old failure while the new analysis is pending", async () => {
        let rejectOld!: (error: Error) => void;
        let resolveCurrent!: (value: DeploymentAnalysisResponse) => void;
        analyze.mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; }))
            .mockImplementationOnce(() => new Promise((resolve) => { resolveCurrent = resolve; }));
        render(<Forge />);
        submit();
        fireEvent.change(screen.getByLabelText("Compose document"), { target: { value: "services: {}" } });
        submit();
        await act(async () => rejectOld(new Error("Old failure")));
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
        await act(async () => resolveCurrent(analysis("Current result")));
        expect(screen.getAllByText("Current result")).toHaveLength(2);
    });

    it("clears a failed result and allows the current input to be analyzed again", async () => {
        render(<Forge />);
        submit();
        await screen.findAllByText("Original result");
        analyze.mockRejectedValueOnce(new Error("Analysis unavailable"));
        submit();
        expect(await screen.findByRole("alert")).toHaveTextContent("Analysis unavailable");
        expect(screen.queryByRole("heading", { name: "Deployment Brief" })).not.toBeInTheDocument();
        submit();
        await screen.findAllByText("Original result");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("requires a document and name before analysis", () => {
        render(<Forge />);
        fireEvent.change(screen.getByLabelText("Compose document"), { target: { value: " " } });
        submit();
        expect(screen.getByRole("alert")).toHaveTextContent("Add a Compose document");
        fireEvent.change(screen.getByLabelText("Deployment name"), { target: { value: " " } });
        submit();
        expect(screen.getByRole("alert")).toHaveTextContent("Deployment name is required");
        expect(analyze).not.toHaveBeenCalled();
    });

    it.each(["high", "critical"] as const)("does not hide %s plan risk behind low analysis risk", async (risk) => {
        const result = analysis("Risk review");
        result.result.planning.proposal.risk = risk;
        analyze.mockResolvedValue(result);
        render(<Forge />);
        submit();
        expect(await screen.findByText(`Highest reported risk: ${risk}`)).toBeInTheDocument();
        expect(screen.queryByText("Ready for Review")).not.toBeInTheDocument();
        expect(screen.queryByText("Deployment Blocked")).not.toBeInTheDocument();
    });

    it("keeps higher analysis risk visible and distinguishes the planner flag from permission", async () => {
        const result = analysis("Risk review");
        result.result.analysis.plan.risk = "critical";
        result.result.planning.proposal.approval_required = false;
        analyze.mockResolvedValue(result);
        render(<Forge />);
        submit();
        await screen.findByText("Highest reported risk: critical");
        expect(screen.getByText("Planner does not request approval")).toBeInTheDocument();
        expect(screen.getByText("This is a proposed plan. Workflow permissions and exact approvals are checked separately.")).toBeInTheDocument();
        expect(screen.getAllByText("Not estimated").length).toBeGreaterThan(0);
        expect(screen.queryByText("0 minutes")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve|execute|deploy now/i })).not.toBeInTheDocument();
    });
});
