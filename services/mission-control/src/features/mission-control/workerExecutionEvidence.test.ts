import { beforeEach, describe, expect, it, vi } from "vitest";
import { listWorkflows } from "../../api/atlas-agent";
import type { WorkflowSummary } from "../../types/atlasAgent";
import { fetchAllWorkflowSummary } from "./workerExecutionEvidence";

vi.mock("../../api/atlas-agent", () => ({ listWorkflows: vi.fn() }));
const item = (id: string) => ({ workflow_id: id, workflow_state: "executing", last_result_summary: "No result yet", timeline: [] }) as unknown as WorkflowSummary;
const page = (ids: string[], total: number, offset = 0) => ({ items: ids.map(item), total, offset, limit: 200 });

describe("dashboard workflow evidence loading", () => {
    beforeEach(() => vi.resetAllMocks());
    it("continues short pages until the authoritative total is reached using only the existing list read", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(page(["a"], 2)).mockResolvedValueOnce(page(["b"], 2, 1));
        expect((await fetchAllWorkflowSummary()).items.map((row) => row.workflow_id)).toEqual(["a", "b"]);
        expect(listWorkflows).toHaveBeenNthCalledWith(2, { limit: 200, offset: 1 });
    });
    it.each([
        [page([], 2, 1)],
        [page(["a"], 2, 1)],
        [page(["b"], 3, 1)],
        [page(["b"], 2, 0)],
    ])("rejects incomplete or inconsistent pagination", async (second) => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(page(["a"], 2)).mockResolvedValueOnce(second);
        await expect(fetchAllWorkflowSummary()).rejects.toThrow(/workflow evidence/);
    });
    it("rejects malformed responses and propagates unavailable reads", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(null as never).mockRejectedValueOnce(new Error("unavailable"));
        await expect(fetchAllWorkflowSummary()).rejects.toThrow("Malformed");
        await expect(fetchAllWorkflowSummary()).rejects.toThrow("unavailable");
    });
    it("accepts an authoritative empty collection", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(page([], 0));
        expect((await fetchAllWorkflowSummary()).total).toBe(0);
    });
});

it('bounds collection reads without publishing truncated totals', async () => {
    vi.mocked(listWorkflows).mockImplementation(async ({ offset = 0 } = {}) =>
        page(Array.from({ length: 200 }, (_, i) => String(offset + i)), 10_001, offset));
    await expect(fetchAllWorkflowSummary()).rejects.toThrow('Incomplete workflow evidence');
    expect(listWorkflows).toHaveBeenLastCalledWith({ limit: 200, offset: 9800 });
});
