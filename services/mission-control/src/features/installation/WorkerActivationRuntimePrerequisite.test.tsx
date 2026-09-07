import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { parseControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import receiptFixture from "../../test/controlledWorkerQueueReceipt";
import { runtimeCollection, runtimeResult } from "../../test/workerActivationRuntimePrerequisite";
import { WorkerActivationRuntimePrerequisite } from "./WorkerActivationRuntimePrerequisite";
import { ControlledWorkerQueueReceipt } from "./ControlledWorkerQueueReceipt";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
const receipt = parseControlledWorkerQueueReceipt(receiptFixture, runtimeResult.record.candidate_record_id, runtimeResult.record.admission_id, runtimeResult.record.operator_id);
function responses(result: unknown = runtimeResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: runtimeCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.53 runtime prerequisite presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        expect(await screen.findByText(/Core recorded prerequisite evidence/)).toBeVisible();
        expect(screen.getAllByText(/Runtime prerequisites remain incomplete/).every((node) => node.textContent?.includes("Worker start and execution remain blocked"))).toBe(true);
        const details = screen.getByText("Advanced v0.53 evidence").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(runtimeResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...runtimeResult, status: { ...runtimeResult.status, lifecycle: "expired", evaluated_at: runtimeResult.status.valid_until } });
        render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        expect(await screen.findByText(/prerequisite evidence has expired/)).toBeVisible();
        expect(screen.getAllByText(/Worker start and execution remain blocked/)[0]).toBeVisible();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s without retry controls", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        expect(await screen.findByText(/Runtime prerequisite evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...runtimeCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        expect(await screen.findByText(/Core has no recorded runtime prerequisite evidence/)).toBeVisible();
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        await screen.findByText(/Core recorded prerequisite evidence/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimePrerequisite receipt={{ ...receipt, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/Core recorded prerequisite evidence/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimePrerequisite receipt={{ ...receipt, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: runtimeCollection }));
        expect(await screen.findByText(/Runtime prerequisite evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded prerequisite evidence/)).not.toBeInTheDocument();
    });
    it("ignores a valid item response that arrives after its owner changes", async () => {
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: runtimeCollection })
            .mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        const { rerender } = render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimePrerequisite receipt={{ ...receipt, operatorId: "other-owner" }} />);
        await act(async () => resolve({ data: runtimeResult }));
        expect(await screen.findByText(/Runtime prerequisite evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded prerequisite evidence/)).not.toBeInTheDocument();
    });
    it("is nested under the exact v0.52 receipt in the existing workflow", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: receiptFixture });
        responses();
        render(<ControlledWorkerQueueReceipt candidateId={receipt.candidateId} admissionId={receipt.admissionId} operatorId={receipt.operatorId} />);
        expect(await screen.findByText(/Core recorded prerequisite evidence/)).toBeVisible();
        expect(screen.getByRole("region", { name: "Controlled queue receipt state" })).toContainElement(screen.getByRole("region", { name: "Worker runtime prerequisite state" }));
    });
});
