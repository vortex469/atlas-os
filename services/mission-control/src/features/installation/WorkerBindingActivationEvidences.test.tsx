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
        expect(screen.getByRole("status")).toHaveTextContent(/loading activation records/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no activation evidence is recorded/i));
        unmount();

        vi.mocked(listWorkerBindingActivationEvidences).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<WorkerBindingActivationEvidences candidateId={workerBindingActivationPreflightFixture.candidate_record_id} preflightId={workerBindingActivationPreflightFixture.preflight_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("explains the blocked activation evidence in plain language and keeps technical evidence under Advanced details", async () => {
        vi.mocked(listWorkerBindingActivationEvidences).mockResolvedValue(workerBindingActivationEvidenceCollectionFixture);
        render(<WorkerBindingActivationEvidences candidateId={workerBindingActivationPreflightFixture.candidate_record_id} preflightId={workerBindingActivationPreflightFixture.preflight_id} />);
        expect(await screen.findByText("Activation evidence recorded")).toBeInTheDocument();
        expect(screen.getByText("Runtime activation is blocked")).toBeInTheDocument();
        expect(screen.getByText("10 requirements remain unavailable.")).toBeInTheDocument();
        expect(screen.getByText(/This record does not activate a worker or start execution/i)).toBeInTheDocument();
        const blockers = screen.getByText("Show what needs to be in place").closest("details");
        expect(blockers).toBeInTheDocument();
        expect(blockers).not.toHaveAttribute("open");
        expect(screen.getByLabelText("Runtime activation blockers")).toHaveTextContent(/The worker activation runtime is not available.*Contact with the worker store is not available.*Contact with the worker runtime is not available/i);
        const advanced = screen.getByText("Advanced details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/ordered worker binding activation evidence blockers/i)).toHaveTextContent(/worker_activation_runtime_not_defined.*store_contact_not_defined.*runtime_contact_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_admission_not_defined.*worker_start_not_defined.*agent_invocation_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/inherited sandbox, resource, network, and filesystem limits/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/worker binding activation evidence fixed-false authority fields/i)).toHaveTextContent(/binding activation allowedfalse.*worker activation runtime allowedfalse.*worker start admission allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("does not call an empty blocker list blocked", async () => {
        const noBlockers: WorkerBindingActivationEvidenceCollectionV1 = {
            ...workerBindingActivationEvidenceCollectionFixture,
            items: [{ ...workerBindingActivationEvidenceCollectionFixture.items[0], blockers: [] }],
        };
        vi.mocked(listWorkerBindingActivationEvidences).mockResolvedValue(noBlockers);
        render(<WorkerBindingActivationEvidences candidateId={workerBindingActivationPreflightFixture.candidate_record_id} preflightId={workerBindingActivationPreflightFixture.preflight_id} />);
        expect(await screen.findByText("No blockers are listed. This record still does not activate the worker.")).toBeInTheDocument();
        expect(screen.queryByText("Runtime activation is blocked")).not.toBeInTheDocument();
    });
});
