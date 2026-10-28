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
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved worker review records/i);
        resolve(empty); await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker review record is saved/i)); unmount();
        vi.mocked(listWorkerAdmissionStubs).mockRejectedValue(new Error("credential /internal/path 10.0.0.1"));
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/technical error details are hidden/i));
        expect(screen.queryByText(/10\.0\.0\.1|credential \/internal/i)).not.toBeInTheDocument();
    });
    it("leads with the worker outcome and blockers, with exact evidence in disclosures", async () => {
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValue({ ...empty, stubs: [workerAdmissionStubResultFixture] });
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("heading", { name: "Saved worker review record" })).toBeInTheDocument();
        expect(screen.getByText("This record has not started a worker or queued work. It does not authorize installation or execution.")).toBeInTheDocument();
        const blockers = screen.getByRole("list", { name: "What still needs to be in place" });
        expect(blockers).toHaveTextContent(/A worker has not been started.*A safe way to create or use a work queue is not defined.*A safe way to start installation is not defined/i);
        expect(screen.getByLabelText("Planned worker safety limits")).toHaveTextContent(/no network access.*no access to host, repository, or guest files/i);
        expect(screen.getByLabelText("Planned worker safety limits")).toHaveTextContent(/1 CPU core, 512 MiB memory, 64 processes, 15 minutes, 1 MiB output, and 256 MiB temporary workspace/i);
        expect(screen.getByText("Worker reference ID")).not.toBeVisible();
        expect(screen.getByText("Inherited limits fingerprint")).not.toBeVisible();
        const details = screen.getByText("Worker and record details").closest("details");
        expect(details).toBeInTheDocument();
        expect(details).not.toHaveAttribute("open");
        fireEvent.click(screen.getByText("Worker and record details"));
        expect(screen.getByText("Worker capability fingerprint")).toBeVisible();
        fireEvent.click(screen.getByText("Exact safety limits and earlier evidence"));
        expect(screen.getByText("Inherited limits fingerprint")).toBeVisible();
        expect(screen.getByText(/Prior evidence chain fingerprint/i)).toBeInTheDocument();
        fireEvent.click(screen.getByText("Audit and authority details"));
        expect(screen.getByText(/Worker and idempotency use are reserved permanently/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/worker admission fixed-false authority fields/i)).toHaveTextContent(/worker startedfalse.*work enqueuedfalse.*execution authorizedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
    it("renders expiry and Home Assistant blocked golden copy", async () => {
        const expired = { ...workerAdmissionStubResultFixture, status: { ...workerAdmissionStubResultFixture.status!, lifecycle: "expired" as const } };
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValue({ ...empty, stubs: [expired] });
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked />);
        expect(await screen.findByRole("heading", { name: "Expired worker review record" })).toBeInTheDocument();
        expect(screen.getByText(/Atlas cannot install Home Assistant, so it cannot be prepared for a worker/i)).toBeInTheDocument();
    });
});
