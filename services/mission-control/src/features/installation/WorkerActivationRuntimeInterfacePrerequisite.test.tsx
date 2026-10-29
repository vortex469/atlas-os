import { WorkerActivationRuntimePlanReview } from "./WorkerActivationRuntimePlanReview";
import { reviewCollection, reviewResult, plan } from "../../test/workerActivationRuntimePlanReview";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { inventoryCollection, inventoryResult, review } from "../../test/workerActivationRuntimeInterfacePrerequisite";
import { WorkerActivationRuntimeInterfacePrerequisite } from "./WorkerActivationRuntimeInterfacePrerequisite";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(result: unknown = inventoryResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: inventoryCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.63 retained interface prerequisite presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(screen.getByRole("status")).toHaveTextContent(/Checking the interface inventory/);
        expect(await screen.findByText(/An interface inventory is saved/)).toBeVisible();
        expect(screen.getByText(/does not make a runtime ready, define its interface, contact a worker, or allow start/i)).toBeVisible();
        expect(screen.getByText(/status reflects the last Core check/)).toBeVisible();
        const details = screen.getByText("Technical details").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(inventoryResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(details).toHaveTextContent("Runtime identity, capability, and lifecycle definition and review remain deferred");
        expect(details).toHaveTextContent("this inventory grants no runtime authority");
        for (const label of ["Core interface prerequisite inventory", "Exact review lineage", "v0.57 fixed-false authority"]) {
            expect(details).toContainElement(screen.getByLabelText(label));
            expect(screen.getByLabelText(label)).not.toBeVisible();
        }
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it.each([
        { worker_activation_runtime_defined: true },
        { worker_activation_runtime_defined: false },
        { schema: "worker-activation-runtime-definition-result-v1" },
        { worker_activation_runtime_interface_admitted: true },
        { worker_activation_runtime_interface_admitted: false },
        { worker_activation_runtime_interface_definition_review_recorded: true },
        { worker_activation_runtime_interface_definition_review_recorded: false },
        { schema: "worker-activation-runtime-interface-definition-review-result-v1" },
        { worker_activation_runtime_inventory_admitted: true },
        { worker_activation_runtime_inventory_admitted: false },
        { worker_activation_runtime_definition_recorded: true },
        { worker_activation_runtime_definition_recorded: false },
        { worker_activation_runtime_definition_review_recorded: true },
        { worker_activation_runtime_definition_review_recorded: false },
        { schema: "worker-activation-runtime-interface-prerequisite-v061" },
        { schema: "worker-activation-runtime-interface-prerequisite-status-v061" },
        { worker_activation_runtime_identity_defined: true },
        { worker_activation_runtime_identity_defined: false },
        { worker_activation_runtime_capability_composition_recorded: true },
        { worker_activation_runtime_capability_composition_recorded: false },
        { worker_activation_runtime_lifecycle_defined: true },
        { worker_activation_runtime_lifecycle_defined: false },
        { worker_activation_runtime_definition_review_recorded: true },
        { worker_activation_runtime_definition_review_recorded: false },
        { schema: "worker-activation-runtime-interface-prerequisite-v062" },
        { schema: "worker-activation-runtime-interface-prerequisite-status-v062" },
        { schema: "worker-activation-runtime-interface-prerequisite-v063" },
        { schema: "worker-activation-runtime-interface-prerequisite-status-v063" },
    ])("fails closed for an invented successor: %j", async (change) => {
        responses({ ...inventoryResult, ...change });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/Atlas could not load the interface inventory/i)).toBeVisible();
        expect(screen.getByText(/does not make a runtime ready, define its interface/i)).toBeVisible();
        expect(screen.queryByText(/An interface inventory is saved/)).not.toBeInTheDocument();
        expect(screen.queryByText("Technical details")).not.toBeInTheDocument();
        expect(atlas.get).toHaveBeenCalledTimes(2);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...inventoryResult, status: { ...inventoryResult.status, lifecycle: "expired", evaluated_at: inventoryResult.status.valid_until } });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/This inventory has expired/)).toBeVisible();
        expect(screen.getByText(/does not make a runtime ready/i)).toBeVisible();
    });
    it.each(["2000-01-01T00:00:00Z", "2199-01-01T00:00:00Z"])("preserves Core lifecycle despite browser clock %s", async (clock) => {
        vi.useFakeTimers({ toFake: ["Date"] });
        vi.setSystemTime(new Date(clock));
        try {
            responses();
            render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
            expect(await screen.findByText(/This inventory is current/)).toBeVisible();
            expect(screen.getByText(/status reflects the last Core check/)).toBeVisible();
            expect(screen.getByText(/does not make a runtime ready/i)).toBeVisible();
            expect(atlas.get).toHaveBeenCalledTimes(2);
        } finally {
            vi.useRealTimers();
        }
    });
    it("discards listed evidence when the authoritative item read fails", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: inventoryCollection })
            .mockRejectedValueOnce({ response: { status: 503, data: { detail: "private dependency failure" }, headers: { "retry-after": "0" } } });
        const { container, rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/Atlas could not load the interface inventory/i)).toBeVisible();
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={structuredClone(review)} />);
        await act(async () => { await Promise.resolve(); });
        expect(screen.queryByText(/An interface inventory is saved|private dependency failure|Technical details/)).not.toBeInTheDocument();
        expect(screen.getByText(/does not make a runtime ready/i)).toBeVisible();
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(1);
        expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
        expect(atlas.get).toHaveBeenCalledTimes(2);
    });
    it("does not reread evidence on equivalent parent renders", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        await screen.findByText(/An interface inventory is saved/);
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={structuredClone(review)} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/An interface inventory is saved/)).toBeVisible();
    });
    it("ignores an old scope failure after the new scope has loaded", async () => {
        let reject!: (reason: Error) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, operatorId: "previous-owner" }} />);
        responses();
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(screen.getByRole("status")).toHaveTextContent(/Checking the interface inventory/);
        await screen.findByText(/An interface inventory is saved/);
        await act(async () => reject(new Error("old private failure")));
        expect(screen.getByText(/An interface inventory is saved/)).toBeVisible();
        expect(screen.queryByText(/unavailable|old private failure/)).not.toBeInTheDocument();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s and offers a safe read retry", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/Atlas could not load the interface inventory/i)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...inventoryCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/No interface inventory has been saved/)).toBeVisible();
    });
    it("retries the failed Core read and shows the saved inventory", async () => {
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("secret endpoint"));
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/retry to check its status/i);

        responses();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));

        expect(await screen.findByText(/An interface inventory is saved/)).toBeVisible();
        expect(atlas.get).toHaveBeenCalledTimes(3);
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        await screen.findByText(/An interface inventory is saved/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/An interface inventory is saved/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: inventoryCollection }));
        expect(await screen.findByText(/Atlas could not load the interface inventory/i)).toBeVisible();
        expect(screen.queryByText(/An interface inventory is saved/)).not.toBeInTheDocument();
    });
    it.each([
        { operatorId: "other-owner" },
        { candidateId: "00000000-0000-4000-8000-000000000002" },
        { runtimePlanReviewId: "00000000-0000-5000-8000-000000000058" },
        { exactRecord: { changed: true } },
    ])("ignores a valid late item after scope changes: %j", async (change) => {
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: inventoryCollection })
            .mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, ...change }} />);
        await act(async () => resolve({ data: inventoryResult }));
        expect(await screen.findByText(/Atlas could not load the interface inventory/i)).toBeVisible();
        expect(screen.queryByText(/An interface inventory is saved/)).not.toBeInTheDocument();
    });
});

it("nests inventory under the exact Core review", async () => {
    vi.resetAllMocks();
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: reviewCollection }).mockResolvedValueOnce({ data: reviewResult });
    responses();
    render(<WorkerActivationRuntimePlanReview plan={plan} />);
    await screen.findByText(/An interface inventory is saved/);
    expect(screen.getByRole("region", { name: "Worker runtime plan review state" })).toContainElement(
        screen.getByRole("region", { name: "Worker runtime interface prerequisite state" }));
    expect(atlas.get).toHaveBeenCalledTimes(4);
});
