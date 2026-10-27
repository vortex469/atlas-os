import { beforeEach, describe, expect, it, vi } from "vitest";
import { changedDeploymentAnalysis, deploymentAnalysisFixture } from "../test/deploymentAnalysis";

const { mockPost } = vi.hoisted(() => ({ mockPost: vi.fn() }));
vi.mock("axios", () => ({ default: { create: () => ({ post: mockPost }), isAxiosError: () => false } }));
import { analyzeCompose } from "./atlas";

beforeEach(() => mockPost.mockReset());

describe("Forge analysis report readability", () => {
    it("preserves a readable report and the exact analysis request", async () => {
        const data = deploymentAnalysisFixture();
        mockPost.mockResolvedValue({ data });
        await expect(analyzeCompose("services: {}", "preview-name")).resolves.toBe(data);
        expect(mockPost).toHaveBeenCalledExactlyOnceWith("/analysis/deployments", { source: "compose", reference: "preview-name", document: { services: {} } });
    });

    it("accepts readable future labels and additive metadata without reclassifying reported risk", async () => {
        const data = changedDeploymentAnalysis("result.analysis.plan.risk", "future_risk") as ReturnType<typeof deploymentAnalysisFixture>;
        const body = { ...data, future_metadata: { extra: true } };
        mockPost.mockResolvedValue({ data: body });
        await expect(analyzeCompose("services: {}", "preview-name")).resolves.toBe(body);
    });

    it("preserves false flags, zero estimates and explicitly empty lists", async () => {
        const data = deploymentAnalysisFixture();
        data.result.analysis.plan.components = [];
        data.result.analysis.diagnostics = [];
        data.result.planning.proposal.steps = [];
        data.result.planning.proposal.approval_required = false;
        data.result.planning.proposal.estimated_duration_minutes = 0;
        mockPost.mockResolvedValue({ data });
        await expect(analyzeCompose("services: {}", "preview-name")).resolves.toBe(data);
    });

    it.each([null, [], {}])("rejects an unreadable report wrapper: %j", async data => {
        mockPost.mockResolvedValue({ data });
        await expect(analyzeCompose("services: {}", "preview-name")).rejects.toThrow("The analysis report is incomplete or unreadable.");
        expect(mockPost).toHaveBeenCalledTimes(1);
    });

    it.each([
        ["result", null], ["result.analysis", null], ["result.analysis.plan", null], ["result.planning.proposal", null],
        ["result.analysis.analyzer", {}], ["result.analysis.plan.name", {}], ["result.analysis.plan.risk", {}],
        ["result.analysis.plan.components", undefined], ["result.analysis.plan.components", {}],
        ["result.analysis.plan.components.0", null], ["result.analysis.plan.components.0.name", {}],
        ["result.analysis.plan.components.0.ports", null], ["result.analysis.plan.components.0.ports.0.protocol", {}],
        ["result.analysis.plan.components.0.ports.0.public", "false"], ["result.analysis.plan.components.0.ports.0.container_port", 0],
        ["result.analysis.plan.components.0.ports.0.host_port", undefined],
        ["result.analysis.diagnostics", null], ["result.analysis.diagnostics", {}], ["result.analysis.diagnostics.0.message", {}],
        ["result.analysis.diagnostics.0.code", {}], ["result.analysis.diagnostics.0.component_id", {}],
        ["result.planning.proposal.summary", {}], ["result.planning.proposal.risk", null],
        ["result.planning.proposal.steps", undefined], ["result.planning.proposal.steps", {}],
        ["result.planning.proposal.steps.0.order", 0], ["result.planning.proposal.steps.0.title", {}],
        ["result.planning.proposal.steps.0.description", {}], ["result.planning.proposal.approval_required", "false"],
        ["result.planning.proposal.estimated_duration_minutes", undefined], ["result.planning.proposal.estimated_duration_minutes", -1],
        ["result.analysis.plan.name", " \t"], ["result.planning.proposal.summary", " "],
        ["result.analysis.plan.components", Array(2).fill(deploymentAnalysisFixture().result.analysis.plan.components[0])],
        ["result.planning.proposal.steps", Array(2).fill(deploymentAnalysisFixture().result.planning.proposal.steps[0])],
        ["result.planning.proposal.steps", [deploymentAnalysisFixture().result.planning.proposal.steps[0], { ...deploymentAnalysisFixture().result.planning.proposal.steps[0], id: "different-step" }]],
    ] as const)("rejects unreadable %s (%j) with a controlled error", async (path, value) => {
        mockPost.mockResolvedValue({ data: changedDeploymentAnalysis(path, value) });
        await expect(analyzeCompose("services: {}", "preview-name")).rejects.toThrow("The analysis report is incomplete or unreadable. Analyze the document again.");
        expect(mockPost).toHaveBeenCalledTimes(1);
    });
});
