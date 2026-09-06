import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerBindingActivationEvidences } from "../../api/workerBindingActivationEvidence";
import { workerBindingActivationPreflightFixture } from "../../test/workerBindingActivationPreflight";
import { workerBindingActivationEvidenceCollectionFixture } from "../../test/workerBindingActivationEvidence";
import type { WorkerBindingActivationEvidenceCollectionV1 } from "../../types/workerBindingActivationEvidence";
import { WorkerBindingActivationEvidences } from "./WorkerBindingActivationEvidences";

vi.mock("../../api/workerBindingActivationEvidence", () => ({ listWorkerBindingActivationEvidences: vi.fn() }));

const empty: WorkerBindingActivationEvidenceCollectionV1 = { ...workerBindingActivationEvidenceCollectionFixture, items: [], count: 0 };

describe("WorkerBindingActivationEvidences", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listWorkerBindingActivationEvidences).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: WorkerBindingActivationEvidenceCollectionV1) => void;
        vi.mocked(listWorkerBindingActivationEvidences).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerBindingActivationEvidences candidateId={workerBindingActivationPreflightFixture.candidate_record_id} preflightId={workerBindingActivationPreflightFixture.preflight_id} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading worker binding activation evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker binding activation evidence/i));
        unmount();

        vi.mocked(listWorkerBindingActivationEvidences).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<WorkerBindingActivationEvidences candidateId={workerBindingActivationPreflightFixture.candidate_record_id} preflightId={workerBindingActivationPreflightFixture.preflight_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders simple activation evidence state with technical evidence under Advanced details", async () => {
        vi.mocked(listWorkerBindingActivationEvidences).mockResolvedValue(workerBindingActivationEvidenceCollectionFixture);
        render(<WorkerBindingActivationEvidences candidateId={workerBindingActivationPreflightFixture.candidate_record_id} preflightId={workerBindingActivationPreflightFixture.preflight_id} />);
        expect(await screen.findByText(/recorded worker binding activation evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/state: evidence recorded for later activation consideration; activation runtime: not defined; worker-start admission: not defined; blocked: yes/i)).toHaveTextContent(/queue claimed: false; worker started: false; Agent invoked: false; execution started: false/i);
        const advanced = screen.getByText("Advanced details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/ordered worker binding activation evidence blockers/i)).toHaveTextContent(/worker_activation_runtime_not_defined.*store_contact_not_defined.*runtime_contact_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_admission_not_defined.*worker_start_not_defined.*agent_invocation_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/inherited sandbox, resource, network, and filesystem limits/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/worker binding activation evidence fixed-false authority fields/i)).toHaveTextContent(/binding activation allowedfalse.*worker activation runtime allowedfalse.*worker start admission allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
