import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerBindingActivationPreflights } from "../../api/workerBindingActivationPreflight";
import { oneShotDequeueWorkerBindingFixture } from "../../test/oneShotDequeueWorkerBinding";
import { workerBindingActivationPreflightCollectionFixture } from "../../test/workerBindingActivationPreflight";
import type { WorkerBindingActivationPreflightCollectionV1 } from "../../types/workerBindingActivationPreflight";
import { WorkerBindingActivationPreflights } from "./WorkerBindingActivationPreflights";

vi.mock("../../api/workerBindingActivationPreflight", () => ({ listWorkerBindingActivationPreflights: vi.fn() }));

const empty: WorkerBindingActivationPreflightCollectionV1 = { ...workerBindingActivationPreflightCollectionFixture, items: [], count: 0 };

describe("WorkerBindingActivationPreflights", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listWorkerBindingActivationPreflights).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: WorkerBindingActivationPreflightCollectionV1) => void;
        vi.mocked(listWorkerBindingActivationPreflights).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerBindingActivationPreflights candidateId={oneShotDequeueWorkerBindingFixture.candidate_record_id} bindingId={oneShotDequeueWorkerBindingFixture.binding_id} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading worker binding activation preflight evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker binding activation preflight evidence/i));
        unmount();

        vi.mocked(listWorkerBindingActivationPreflights).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<WorkerBindingActivationPreflights candidateId={oneShotDequeueWorkerBindingFixture.candidate_record_id} bindingId={oneShotDequeueWorkerBindingFixture.binding_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders simple preflight state with technical evidence under Advanced details", async () => {
        vi.mocked(listWorkerBindingActivationPreflights).mockResolvedValue(workerBindingActivationPreflightCollectionFixture);
        render(<WorkerBindingActivationPreflights candidateId={oneShotDequeueWorkerBindingFixture.candidate_record_id} bindingId={oneShotDequeueWorkerBindingFixture.binding_id} />);
        expect(await screen.findByText(/recorded worker binding activation preflight evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/state: eligible for later activation consideration; activation: not defined; blocked: yes/i)).toHaveTextContent(/store contacted: false; runtime contacted: false; queue claimed: false; worker started: false; Agent invoked: false; execution started: false/i);
        const advanced = screen.getByText("Advanced details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/ordered worker binding activation preflight blockers/i)).toHaveTextContent(/worker_binding_activation_not_defined.*store_contact_not_defined.*runtime_contact_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_not_defined.*agent_invocation_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/inherited sandbox, resource, network, and filesystem limits/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/worker binding activation preflight fixed-false authority fields/i)).toHaveTextContent(/binding activation allowedfalse.*worker start allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
