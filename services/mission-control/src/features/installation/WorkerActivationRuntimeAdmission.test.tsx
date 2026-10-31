import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { admissionCollection, admissionResult, prerequisite } from "../../test/workerActivationRuntimeAdmission";
import { runtimeCollection, runtimeResult } from "../../test/workerActivationRuntimePrerequisite";
import { WorkerActivationRuntimePrerequisite } from "./WorkerActivationRuntimePrerequisite";
import { parseControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import receiptFixture from "../../test/controlledWorkerQueueReceipt";
import { WorkerActivationRuntimeAdmission } from "./WorkerActivationRuntimeAdmission";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
vi.mock("./WorkerActivationRuntimePlan", () => ({ WorkerActivationRuntimePlan: () => null }));
function responses(result: unknown = admissionResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: admissionCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.54 runtime admission presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(screen.getByRole("status")).toHaveTextContent(/Checking the runtime review/);
        expect(await screen.findByText(/Runtime admission review saved/)).toBeVisible();
        expect(screen.getByText(/Runtime requirements are not met/)).toBeVisible();
        const details = screen.getByText("Technical details").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(admissionResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...admissionResult, status: { ...admissionResult.status, lifecycle: "expired", evaluated_at: admissionResult.status.valid_until } });
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/This review has expired/i)).toBeVisible();
        expect(screen.getByText(/Runtime requirements are not met\. Worker start and execution are unavailable/)).toBeVisible();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s and offers a safe read retry", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/Atlas could not load the runtime admission review/i)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...admissionCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/No runtime admission review has been saved/)).toBeVisible();
    });
    it("retries the failed Core read and shows the saved review", async () => {
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("secret endpoint"));
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/retry to check its status/i);

        responses();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));

        expect(await screen.findByText(/Runtime admission review saved/)).toBeVisible();
        expect(atlas.get).toHaveBeenCalledTimes(3);
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        await screen.findByText(/Runtime admission review saved/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimeAdmission prerequisite={{ ...prerequisite, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/Runtime admission review saved/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimeAdmission prerequisite={{ ...prerequisite, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: admissionCollection }));
        expect(await screen.findByText(/Atlas could not load the runtime admission review/i)).toBeVisible();
        expect(screen.queryByText(/Runtime admission review saved/)).not.toBeInTheDocument();
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
        expect(await screen.findByText(/Atlas could not load the runtime admission review/i)).toBeVisible();
        expect(screen.queryByText(/Runtime admission review saved/)).not.toBeInTheDocument();
    });
    it("is nested beneath the exact v0.53 prerequisite", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: runtimeCollection }).mockResolvedValueOnce({ data: runtimeResult });
        responses();
        const receipt = parseControlledWorkerQueueReceipt(receiptFixture, prerequisite.candidateId, prerequisite.admissionId, prerequisite.operatorId);
        render(<WorkerActivationRuntimePrerequisite receipt={receipt} />);
        expect(await screen.findByText(/Runtime admission review saved/)).toBeVisible();
        expect(screen.getByRole("region", { name: "Worker runtime prerequisite state" })).toContainElement(screen.getByRole("region", { name: "Worker runtime admission state" }));
    });
});
