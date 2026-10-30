import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { analyzeCompose } from "../../api/atlas";
import { Forge } from "./Forge";
import type { DeploymentAnalysisResponse } from "./types";

vi.mock("../../api/atlas", () => ({
    analyzeCompose: vi.fn(),
    getAtlasErrorMessage: (_error: unknown, fallback: string) => fallback,
}));
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

    it.each(["Deployment name", "Docker Compose file"])("clears a displayed result when %s changes", async (label) => {
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
        fireEvent.change(screen.getByLabelText("Docker Compose file"), { target: { value: "services: {}" } });
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
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control couldn't complete the analysis. Check the Compose file and Atlas connection, then try again.");
        const technicalDetails = alert.querySelector("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(screen.getByText("Analysis unavailable")).not.toBeVisible();
        fireEvent.click(screen.getByText("Technical details"));
        expect(technicalDetails).toHaveAttribute("open");
        expect(screen.getByText("Analysis unavailable")).toBeVisible();
        expect(screen.queryByRole("heading", { name: "Deployment Brief" })).not.toBeInTheDocument();
        submit();
        await screen.findAllByText("Original result");
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("requires a document and name before analysis", () => {
        render(<Forge />);
        fireEvent.change(screen.getByLabelText("Docker Compose file"), { target: { value: " " } });
        submit();
        expect(screen.getByRole("alert")).toHaveTextContent("Add a Docker Compose file");
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

    it("limits the empty findings message to what the analysis reported", async () => {
        render(<Forge />);
        submit();
        await screen.findByRole("heading", { name: "Deployment Brief" });
        expect(screen.getByRole("heading", { name: "Findings" })).toBeInTheDocument();
        expect(screen.getByText("No findings were reported for this Compose file.")).toBeInTheDocument();
        expect(screen.queryByText(/security or operational concerns/)).not.toBeInTheDocument();
    });

    it("explains port bindings without claiming internet access", async () => {
        const result = analysis("Home services");
        result.result.analysis.plan.components = [{
            id: "web",
            name: "web",
            kind: "service",
            image: "nginx:latest",
            ports: [
                { host_port: 8080, container_port: 80, protocol: "tcp", public: true },
                { host_port: null, container_port: 443, protocol: "tcp", public: false },
            ],
        }];
        analyze.mockResolvedValue(result);
        render(<Forge />);
        submit();

        await screen.findByRole("heading", { name: "Network ports" });
        expect(screen.getByText("Host ports are on the computer where Docker runs; service ports are inside the container. This review does not check whether a firewall, router, or internet connection allows other computers to reach the service.")).toBeInTheDocument();
        expect(screen.getByText("Host port 8080 → service port 80/TCP")).toBeInTheDocument();
        expect(screen.getByText("The binding may accept connections from other computers.")).toBeInTheDocument();
        expect(screen.getByText("No fixed host port was specified in this file → service port 443/TCP")).toBeInTheDocument();
        expect(screen.getByText("Access from other computers was not reported.")).toBeInTheDocument();
        expect(screen.queryByText("Public", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Analyzer" })).not.toBeInTheDocument();
    });

    it("states what deployment analysis does and does not do", () => {
        render(<Forge />);
        expect(screen.getByRole("heading", { name: "Deployment analysis" })).toBeInTheDocument();
        expect(screen.getByText("Review a Docker Compose file, findings, and suggested steps. This page does not deploy anything.")).toBeInTheDocument();
        expect(screen.queryByText("Atlas Forge")).not.toBeInTheDocument();
    });
});
