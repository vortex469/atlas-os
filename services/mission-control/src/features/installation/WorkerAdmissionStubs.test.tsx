import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerAdmissionStubs } from "../../api/workerAdmissionStub";
import { listWorkerQueueReservations } from "../../api/workerQueueReservation";
import { runnerBindingPlanResultFixture } from "../../test/runnerBindingPlan";
import { workerAdmissionStubResultFixture } from "../../test/workerAdmissionStub";
import type { WorkerAdmissionStubCollectionV1 } from "../../types/workerAdmissionStub";
import { WorkerAdmissionStubs } from "./WorkerAdmissionStubs";

vi.mock("../../api/workerAdmissionStub", () => ({ listWorkerAdmissionStubs: vi.fn() }));
vi.mock("../../api/workerQueueReservation", () => ({ listWorkerQueueReservations: vi.fn().mockResolvedValue({ schema: "worker-queue-reservation-collection-v1", items: [], count: 0, evidence_only: true }) }));
const empty: WorkerAdmissionStubCollectionV1 = { schema: "worker-admission-stub-collection-v1", stubs: [], evidence_only: true, worker_start_allowed: false, enqueue_allowed: false, execution_authorized: false, mutation_allowed: false };

describe("WorkerAdmissionStubs", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listWorkerAdmissionStubs).mockResolvedValue(empty); vi.mocked(listWorkerQueueReservations).mockResolvedValue({ schema: "worker-queue-reservation-collection-v1", items: [], count: 0, evidence_only: true }); });
    it("renders loading, empty, and redacted error states without leaking details", async () => {
        let resolve!: (value: typeof empty) => void;
        vi.mocked(listWorkerAdmissionStubs).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved worker setup record/i);
        resolve(empty); await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker setup record has been saved/i)); unmount();
        vi.mocked(listWorkerAdmissionStubs).mockRejectedValue(new Error("credential /internal/path 10.0.0.1"));
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/could not load the worker setup record.*retry to check its current status/i));
        expect(screen.queryByText(/10\.0\.0\.1|credential \/internal/i)).not.toBeInTheDocument();
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValueOnce(empty);
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(await screen.findByText("No worker setup record has been saved. Atlas cannot start a worker or queue work.")).toBeInTheDocument();
        expect(listWorkerAdmissionStubs).toHaveBeenCalledTimes(3);
    });
    it("renders a short worker status while keeping technical evidence collapsed", async () => {
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValue({ ...empty, stubs: [workerAdmissionStubResultFixture] });
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByText("Worker setup record is current")).toBeInTheDocument();
        expect(screen.getByText(/no worker has been contacted or started, and no work has been put on a queue/i)).toBeInTheDocument();
        const advanced = screen.getByText("Technical details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/ordered worker admission blockers/i)).toHaveTextContent(/worker_not_started.*queue_boundary_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/sandbox and resource limits/i)).toBeInTheDocument();
        expect(screen.getByText(/related review records/i)).toBeInTheDocument();
        expect(screen.getByText(/permanent worker-admission-subject reservation/i)).toHaveTextContent(/replay allowed: false/i);
        expect(screen.getByLabelText(/worker admission fixed-false authority fields/i)).toHaveTextContent(/worker startedfalse.*work enqueuedfalse.*execution authorizedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("renders expiry without repeating the parent Home Assistant notice", async () => {
        const expired = { ...workerAdmissionStubResultFixture, status: { ...workerAdmissionStubResultFixture.status!, lifecycle: "expired" as const } };
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValue({ ...empty, stubs: [expired] });
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked />);
        expect(await screen.findByText("Worker setup record has expired")).toBeInTheDocument();
        expect(screen.queryByText("Atlas cannot install or run Home Assistant yet.")).not.toBeInTheDocument();
    });
});
