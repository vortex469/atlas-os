import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { planCollection, planResult, admission } from "../../test/workerActivationRuntimePlan";
import { WorkerActivationRuntimePlan } from "./WorkerActivationRuntimePlan";
import { WorkerActivationRuntimeAdmission } from "./WorkerActivationRuntimeAdmission";
import { admissionCollection, admissionResult, prerequisite } from "../../test/workerActivationRuntimePlan";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(result: unknown = planResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: planCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.55 runtime plan presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimePlan admission={admission} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        expect(await screen.findByText(/Core recorded a reference-only runtime plan/)).toBeVisible();
        expect(screen.getByText(/runtime prerequisites remain incomplete/)).toBeVisible();
        const details = screen.getByText("Advanced v0.55 evidence").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(admissionResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...planResult, status: { ...planResult.status, lifecycle: "expired", evaluated_at: planResult.status.valid_until } });
        render(<WorkerActivationRuntimePlan admission={admission} />);
        expect(await screen.findByText(/plan evidence has expired/)).toBeVisible();
        expect(screen.getByText(/Worker start and execution remain blocked/)).toBeVisible();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s without retry controls", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimePlan admission={admission} />);
        expect(await screen.findByText(/Runtime plan evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...planCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimePlan admission={admission} />);
        expect(await screen.findByText(/Core has no recorded runtime plan evidence/)).toBeVisible();
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimePlan admission={admission} />);
        await screen.findByText(/Core recorded a reference-only runtime plan/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimePlan admission={{ ...admission, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/Core recorded a reference-only runtime plan/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimePlan admission={{ ...admission, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: planCollection }));
        expect(await screen.findByText(/Runtime plan evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded a reference-only runtime plan/)).not.toBeInTheDocument();
    });
    it.each([
        { operatorId: "other-owner" },
        { candidateId: "00000000-0000-4000-8000-000000000002" },
        { runtimeAdmissionId: "00000000-0000-5000-8000-000000000056" },
        { exactRecord: { changed: true } },
    ])("ignores a valid late item after scope changes: %j", async (change) => {
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: planCollection })
            .mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        const { rerender } = render(<WorkerActivationRuntimePlan admission={admission} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimePlan admission={{ ...admission, ...change }} />);
        await act(async () => resolve({ data: planResult }));
        expect(await screen.findByText(/Runtime plan evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded a reference-only runtime plan/)).not.toBeInTheDocument();
    });
    it("is nested beneath the exact v0.54 admission", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: admissionCollection }).mockResolvedValueOnce({ data: admissionResult });
        responses();
        render(<WorkerActivationRuntimeAdmission prerequisite={prerequisite} />);
        expect(await screen.findByText(/Core recorded a reference-only runtime plan/)).toBeVisible();
        expect(screen.getByRole("region", { name: "Worker runtime admission state" })).toContainElement(screen.getByRole("region", { name: "Worker runtime plan state" }));
    });
});
