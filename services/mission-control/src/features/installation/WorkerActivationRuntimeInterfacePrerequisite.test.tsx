import { WorkerActivationRuntimePlanReview } from "./WorkerActivationRuntimePlanReview";
import { reviewCollection, reviewResult, plan } from "../../test/workerActivationRuntimePlanReview";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { inventoryCollection, inventoryResult, review } from "../../test/workerActivationRuntimeInterfacePrerequisite";
import { WorkerActivationRuntimeInterfacePrerequisite } from "./WorkerActivationRuntimeInterfacePrerequisite";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(result: unknown = inventoryResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: inventoryCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.57 runtime plan presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        expect(await screen.findByText(/Core recorded an interface prerequisite inventory/)).toBeVisible();
        expect(screen.getByText(/runtime prerequisites remain incomplete/)).toBeVisible();
        const details = screen.getByText("Advanced v0.57 evidence").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(inventoryResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...inventoryResult, status: { ...inventoryResult.status, lifecycle: "expired", evaluated_at: inventoryResult.status.valid_until } });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/interface prerequisite evidence has expired/)).toBeVisible();
        expect(screen.getByText(/Worker start and execution remain blocked/)).toBeVisible();
    });
    it("does not reread evidence on equivalent parent renders", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        await screen.findByText(/Core recorded an interface prerequisite inventory/);
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={structuredClone(review)} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/Core recorded an interface prerequisite inventory/)).toBeVisible();
    });
    it("ignores an old scope failure after the new scope has loaded", async () => {
        let reject!: (reason: Error) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, operatorId: "previous-owner" }} />);
        responses();
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        await screen.findByText(/Core recorded an interface prerequisite inventory/);
        await act(async () => reject(new Error("old private failure")));
        expect(screen.getByText(/Core recorded an interface prerequisite inventory/)).toBeVisible();
        expect(screen.queryByText(/unavailable|old private failure/)).not.toBeInTheDocument();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s without retry controls", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/Interface prerequisite inventory evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...inventoryCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        expect(await screen.findByText(/Core has no recorded interface prerequisite evidence/)).toBeVisible();
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimeInterfacePrerequisite review={review} />);
        await screen.findByText(/Core recorded an interface prerequisite inventory/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/Core recorded an interface prerequisite inventory/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimeInterfacePrerequisite review={{ ...review, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: inventoryCollection }));
        expect(await screen.findByText(/Interface prerequisite inventory evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded an interface prerequisite inventory/)).not.toBeInTheDocument();
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
        expect(await screen.findByText(/Interface prerequisite inventory evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded an interface prerequisite inventory/)).not.toBeInTheDocument();
    });
});

it("nests inventory under the exact Core review", async () => {
    vi.resetAllMocks();
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: reviewCollection }).mockResolvedValueOnce({ data: reviewResult });
    responses();
    render(<WorkerActivationRuntimePlanReview plan={plan} />);
    await screen.findByText(/Core recorded an interface prerequisite inventory/);
    expect(screen.getByRole("region", { name: "Worker runtime plan review state" })).toContainElement(
        screen.getByRole("region", { name: "Worker runtime interface prerequisite state" }));
    expect(atlas.get).toHaveBeenCalledTimes(4);
});
