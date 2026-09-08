import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { admissionCollection, admissionResult, prerequisite } from "../../test/workerActivationRuntimeAdmission";
import { runtimeCollection, runtimeResult } from "../../test/workerActivationRuntimePrerequisite";
import { WorkerActivationRuntimePrerequisite } from "./WorkerActivationRuntimePrerequisite";
import { parseControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import receiptFixture from "../../test/controlledWorkerQueueReceipt";
import { WorkerActivationRuntimeAdmission } from "./WorkerActivationRuntimeAdmission";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(result: unknown = admissionResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: admissionCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.54 runtime admission presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        expect(await screen.findByText(/Core recorded admission evidence/)).toBeVisible();
        expect(screen.getByText(/Runtime prerequisites remain incomplete/)).toBeVisible();
        const details = screen.getByText("Advanced v0.54 evidence").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(admissionResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...admissionResult, status: { ...admissionResult.status, lifecycle: "expired", evaluated_at: admissionResult.status.valid_until } });
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/admission evidence has expired/)).toBeVisible();
        expect(screen.getByText(/Runtime prerequisites remain incomplete. Worker start and execution remain blocked/)).toBeVisible();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s without retry controls", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/Runtime admission evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...admissionCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/Core has no recorded runtime admission evidence/)).toBeVisible();
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        await screen.findByText(/Core recorded admission evidence/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimeAdmission prerequisite={{ ...prerequisite, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/Core recorded admission evidence/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimeAdmission prerequisite={{ ...prerequisite, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: admissionCollection }));
        expect(await screen.findByText(/Runtime admission evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded admission evidence/)).not.toBeInTheDocument();
    });
    it("ignores a valid item response that arrives after its owner changes", async () => {
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: admissionCollection })
            .mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        const { rerender } = render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimeAdmission prerequisite={{ ...prerequisite, operatorId: "other-owner" }} />);
        await act(async () => resolve({ data: admissionResult }));
        expect(await screen.findByText(/Runtime admission evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded admission evidence/)).not.toBeInTheDocument();
    });
    it("is nested beneath the exact v0.53 prerequisite", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: runtimeCollection }).mockResolvedValueOnce({ data: runtimeResult });
        responses();
        const receipt = parseControlledWorkerQueueReceipt(receiptFixture, prerequisite.candidateId, prerequisite.admissionId, prerequisite.operatorId);
        render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        expect(await screen.findByText(/Core recorded admission evidence/)).toBeVisible();
        expect(screen.getByRole("region", { name: "Worker runtime prerequisite state" })).toContainElement(screen.getByRole("region", { name: "Worker runtime admission state" }));
    });
});
