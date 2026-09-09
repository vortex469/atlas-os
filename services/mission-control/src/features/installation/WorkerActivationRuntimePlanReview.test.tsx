import { WorkerActivationRuntimePlan } from "./WorkerActivationRuntimePlan";
import { planCollection, planResult, admission } from "../../test/workerActivationRuntimePlan";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "../../api/atlas";
import { reviewCollection, reviewResult, plan } from "../../test/workerActivationRuntimePlanReview";
import { WorkerActivationRuntimePlanReview } from "./WorkerActivationRuntimePlanReview";
vi.mock("../../api/atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(result: unknown = reviewResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: reviewCollection }).mockResolvedValueOnce({ data: result });
}
describe("v0.56 runtime plan presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows incomplete prerequisites first with inspectable collapsed details and no controls", async () => {
        responses();
        const { container } = render(<WorkerActivationRuntimePlanReview plan={plan} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        expect(await screen.findByText(/Core recorded a consistency review/)).toBeVisible();
        expect(screen.getByText(/runtime prerequisites remain incomplete/)).toBeVisible();
        const details = screen.getByText("Advanced v0.56 evidence").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(reviewResult.record.prerequisite_id)).not.toBeVisible();
        expect(details).toHaveTextContent("worker_start_allowedfalse");
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("shows expired evidence without suggesting runtime readiness", async () => {
        responses({ ...reviewResult, status: { ...reviewResult.status, lifecycle: "expired", evaluated_at: reviewResult.status.valid_until } });
        render(<WorkerActivationRuntimePlanReview plan={plan} />);
        expect(await screen.findByText(/plan review evidence has expired/)).toBeVisible();
        expect(screen.getByText(/Worker start and execution remain blocked/)).toBeVisible();
    });
    it("does not reread evidence on equivalent parent renders", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimePlanReview plan={plan} />);
        await screen.findByText(/Core recorded a consistency review/);
        rerender(<WorkerActivationRuntimePlanReview plan={structuredClone(plan)} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        expect(screen.getByText(/Core recorded a consistency review/)).toBeVisible();
    });
    it("ignores an old scope failure after the new scope has loaded", async () => {
        let reject!: (reason: Error) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
        const { rerender } = render(<WorkerActivationRuntimePlanReview plan={{ ...plan, operatorId: "previous-owner" }} />);
        responses();
        rerender(<WorkerActivationRuntimePlanReview plan={plan} />);
        expect(screen.getByRole("status")).toHaveTextContent("Loading");
        await screen.findByText(/Core recorded a consistency review/);
        await act(async () => reject(new Error("old private failure")));
        expect(screen.getByText(/Core recorded a consistency review/)).toBeVisible();
        expect(screen.queryByText(/unavailable|old private failure/)).not.toBeInTheDocument();
    });
    it.each([401, 403, 404, 409, 503])("redacts failure %s without retry controls", async (status) => {
        vi.mocked(atlas.get).mockRejectedValue({ response: { status, data: { message: "secret endpoint" } } });
        render(<WorkerActivationRuntimePlanReview plan={plan} />);
        expect(await screen.findByText(/Plan review evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/secret endpoint/)).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("distinguishes an empty owned collection", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...reviewCollection, count: 0, items: [] } });
        render(<WorkerActivationRuntimePlanReview plan={plan} />);
        expect(await screen.findByText(/Core has no recorded plan review evidence/)).toBeVisible();
    });
    it("clears evidence on scope change and ignores late responses", async () => {
        responses();
        const { rerender } = render(<WorkerActivationRuntimePlanReview plan={plan} />);
        await screen.findByText(/Core recorded a consistency review/);
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        rerender(<WorkerActivationRuntimePlanReview plan={{ ...plan, operatorId: "other-owner" }} />);
        expect(screen.queryByText(/Core recorded a consistency review/)).not.toBeInTheDocument();
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimePlanReview plan={{ ...plan, admissionId: "00000000-0000-5000-8000-000000000054" }} />);
        await act(async () => resolve({ data: reviewCollection }));
        expect(await screen.findByText(/Plan review evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded a consistency review/)).not.toBeInTheDocument();
    });
    it.each([
        { operatorId: "other-owner" },
        { candidateId: "00000000-0000-4000-8000-000000000002" },
        { runtimePlanId: "00000000-0000-5000-8000-000000000056" },
        { exactRecord: { changed: true } },
    ])("ignores a valid late item after scope changes: %j", async (change) => {
        let resolve!: (value: unknown) => void;
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: reviewCollection })
            .mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        const { rerender } = render(<WorkerActivationRuntimePlanReview plan={plan} />);
        await act(async () => { await Promise.resolve(); });
        expect(atlas.get).toHaveBeenCalledTimes(2);
        vi.mocked(atlas.get).mockRejectedValueOnce(new Error("forbidden"));
        rerender(<WorkerActivationRuntimePlanReview plan={{ ...plan, ...change }} />);
        await act(async () => resolve({ data: reviewResult }));
        expect(await screen.findByText(/Plan review evidence is unavailable/)).toBeVisible();
        expect(screen.queryByText(/Core recorded a consistency review/)).not.toBeInTheDocument();
    });
});

it("nests review under the exact Core plan", async () => {
    vi.resetAllMocks();
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: planCollection }).mockResolvedValueOnce({ data: planResult });
    responses();
    render(<WorkerActivationRuntimePlan admission={admission} />);
    await screen.findByText(/Core recorded a consistency review/);
    expect(screen.getByRole("region", { name: "Worker runtime plan state" })).toContainElement(
        screen.getByRole("region", { name: "Worker runtime plan review state" }));
    expect(atlas.get).toHaveBeenCalledTimes(4);
});
