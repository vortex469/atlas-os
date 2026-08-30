import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerAdmissionStubs } from "../../api/workerAdmissionStub";
import { runnerBindingPlanResultFixture } from "../../test/runnerBindingPlan";
import { workerAdmissionStubResultFixture } from "../../test/workerAdmissionStub";
import type { WorkerAdmissionStubCollectionV1 } from "../../types/workerAdmissionStub";
import { WorkerAdmissionStubs } from "./WorkerAdmissionStubs";

vi.mock("../../api/workerAdmissionStub", () => ({ listWorkerAdmissionStubs: vi.fn() }));
const empty: WorkerAdmissionStubCollectionV1 = { schema: "worker-admission-stub-collection-v1", stubs: [], evidence_only: true, worker_start_allowed: false, enqueue_allowed: false, execution_authorized: false, mutation_allowed: false };

describe("WorkerAdmissionStubs", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listWorkerAdmissionStubs).mockResolvedValue(empty); });
    it("renders loading, empty, and redacted error states without leaking details", async () => {
        let resolve!: (value: typeof empty) => void;
        vi.mocked(listWorkerAdmissionStubs).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading worker admission stub evidence/i);
        resolve(empty); await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker admission stub evidence/i)); unmount();
        vi.mocked(listWorkerAdmissionStubs).mockRejectedValue(new Error("credential /internal/path 10.0.0.1"));
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/error is redacted/i));
        expect(screen.queryByText(/10\.0\.0\.1|credential \/internal/i)).not.toBeInTheDocument();
    });
    it("renders lifecycle, blockers, intent, limits, linkage, audit, and false authority", async () => {
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValue({ ...empty, stubs: [workerAdmissionStubResultFixture] });
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByText(/active worker-admission-stubbed evidence/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered worker admission blockers/i)).toHaveTextContent(/worker_not_started.*queue_boundary_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/inherited byte-exact sandbox/i)).toBeInTheDocument();
        expect(screen.getByText(/required v0.20–v0.37 linkage/i)).toBeInTheDocument();
        expect(screen.getByText(/permanent worker-admission-subject reservation/i)).toHaveTextContent(/replay allowed: false/i);
        expect(screen.getByLabelText(/worker admission fixed-false authority fields/i)).toHaveTextContent(/worker startedfalse.*work enqueuedfalse.*execution authorizedfalse/i);
        expect(screen.getByText(/not worker start, queue or enqueue/i)).toHaveTextContent(/not.*dispatch.*retry or resend.*Agent invocation.*deployment.*rollback.*permission to mutate/i);
    });
    it("renders expiry and Home Assistant blocked golden copy", async () => {
        const expired = { ...workerAdmissionStubResultFixture, status: { ...workerAdmissionStubResultFixture.status!, lifecycle: "expired" as const } };
        vi.mocked(listWorkerAdmissionStubs).mockResolvedValue({ ...empty, stubs: [expired] });
        render(<WorkerAdmissionStubs candidateId="candidate" bindingPlan={runnerBindingPlanResultFixture} homeAssistantBlocked />);
        expect(await screen.findByText(/expired worker-admission-stubbed evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/For Home Assistant, worker admission remains blocked/i)).toHaveTextContent(/non-installable and non-executable/i);
    });
});
