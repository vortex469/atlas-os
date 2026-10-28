import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listControlledWorkerQueueClaimAdmissions } from "../../api/controlledWorkerQueueClaimAdmission";
import { controlledWorkerQueueClaimAdmissionCollectionFixture } from "../../test/controlledWorkerQueueClaimAdmission";
import { workerBindingActivationEvidenceFixture } from "../../test/workerBindingActivationEvidence";
import type { ControlledWorkerQueueClaimAdmissionCollectionV1 } from "../../types/controlledWorkerQueueClaimAdmission";
import { ControlledWorkerQueueClaimAdmissions } from "./ControlledWorkerQueueClaimAdmissions";

vi.mock("../../api/controlledWorkerQueueClaimAdmission", () => ({ listControlledWorkerQueueClaimAdmissions: vi.fn() }));
vi.mock("./ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions", () => ({ ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions: () => <section aria-label="Controlled worker queue claim lease acknowledgement admission evidence">Nested v0.51 claim lease acknowledgement evidence</section> }));

const empty: ControlledWorkerQueueClaimAdmissionCollectionV1 = { ...controlledWorkerQueueClaimAdmissionCollectionFixture, items: [], count: 0 };

describe("ControlledWorkerQueueClaimAdmissions", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listControlledWorkerQueueClaimAdmissions).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: ControlledWorkerQueueClaimAdmissionCollectionV1) => void;
        vi.mocked(listControlledWorkerQueueClaimAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<ControlledWorkerQueueClaimAdmissions candidateId={workerBindingActivationEvidenceFixture.candidate_record_id} activationEvidenceId={workerBindingActivationEvidenceFixture.activation_evidence_id} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading queue claim readiness/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue claim readiness record is available/i));
        unmount();

        vi.mocked(listControlledWorkerQueueClaimAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<ControlledWorkerQueueClaimAdmissions candidateId={workerBindingActivationEvidenceFixture.candidate_record_id} activationEvidenceId={workerBindingActivationEvidenceFixture.activation_evidence_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("explains blocked queue readiness and keeps technical evidence under Advanced details", async () => {
        vi.mocked(listControlledWorkerQueueClaimAdmissions).mockResolvedValue(controlledWorkerQueueClaimAdmissionCollectionFixture);
        render(<ControlledWorkerQueueClaimAdmissions candidateId={workerBindingActivationEvidenceFixture.candidate_record_id} activationEvidenceId={workerBindingActivationEvidenceFixture.activation_evidence_id} />);
        expect(await screen.findByText("Queue claim admission recorded")).toBeInTheDocument();
        expect(screen.getByText("Queue claim is blocked")).toBeInTheDocument();
        expect(screen.getByText("10 requirements remain unavailable.")).toBeInTheDocument();
        expect(screen.getByText(/Queue claiming is not available yet. This record only captures readiness/i)).toBeInTheDocument();
        expect(screen.getByText(/A separate lease and acknowledgement readiness record may appear below. It is also read-only/i)).toBeInTheDocument();
        const blockers = screen.getByText("Show what needs to be in place").closest("details");
        expect(blockers).toBeInTheDocument();
        expect(blockers).not.toHaveAttribute("open");
        expect(screen.getByLabelText("Queue claim blockers")).toHaveTextContent(/Taking work from the queue is not available.*Holding work from the queue is not available.*Acknowledging queue work is not available/i);
        expect(screen.getByLabelText(/controlled worker queue claim lease acknowledgement admission evidence/i)).toHaveTextContent(/nested v0\.51/i);
        const advanced = screen.getByText("Advanced details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(advanced).toHaveTextContent(/v0\.50 prerequisite details/i);
        expect(screen.getByLabelText(/v0\.50 controlled worker queue prerequisites/i)).toHaveTextContent(/one active same-owner v0\.49 controlled worker queue claim admission.*Agent and execution-worker zero-consumer behavior/i);
        expect(screen.getByLabelText(/v0\.50 fixed-false prerequisite equations/i)).toHaveTextContent(/v0\.50 prerequisite frozen equals queue claimedfalse.*v0\.50 prerequisite frozen equals execution startedfalse.*Claim admission recorded equals queue claimedfalse/i);
        expect(screen.getByLabelText(/ordered controlled worker queue claim admission blockers/i)).toHaveTextContent(/queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_activation_runtime_not_defined.*store_contact_not_defined.*runtime_contact_not_defined.*worker_start_admission_not_defined.*worker_start_not_defined.*agent_invocation_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/inherited sandbox, resource, network, and filesystem limits/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/controlled worker queue claim admission fixed-false authority fields/i)).toHaveTextContent(/queue claim allowedfalse.*queue claimedfalse.*worker start admission allowedfalse.*worker start admittedfalse.*execution startedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("does not call an empty blocker list blocked", async () => {
        const noBlockers: ControlledWorkerQueueClaimAdmissionCollectionV1 = {
            ...controlledWorkerQueueClaimAdmissionCollectionFixture,
            items: [{ ...controlledWorkerQueueClaimAdmissionCollectionFixture.items[0], blockers: [] }],
        };
        vi.mocked(listControlledWorkerQueueClaimAdmissions).mockResolvedValue(noBlockers);
        render(<ControlledWorkerQueueClaimAdmissions candidateId={workerBindingActivationEvidenceFixture.candidate_record_id} activationEvidenceId={workerBindingActivationEvidenceFixture.activation_evidence_id} />);
        expect(await screen.findByText("No blockers are listed. This record still cannot take queue work.")).toBeInTheDocument();
        expect(screen.queryByText("Queue claim is blocked")).not.toBeInTheDocument();
    });
});
