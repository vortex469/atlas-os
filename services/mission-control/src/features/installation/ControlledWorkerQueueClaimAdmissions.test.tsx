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
        expect(screen.getByRole("status")).toHaveTextContent(/loading controlled worker queue claim admission evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no controlled worker queue claim admission evidence/i));
        expect(screen.getByRole("status")).toHaveTextContent(/v0\.50 remains documentation-only prerequisite closure/i);
        unmount();

        vi.mocked(listControlledWorkerQueueClaimAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<ControlledWorkerQueueClaimAdmissions candidateId={workerBindingActivationEvidenceFixture.candidate_record_id} activationEvidenceId={workerBindingActivationEvidenceFixture.activation_evidence_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders simple readiness and start-admission state with technical evidence under Advanced details", async () => {
        vi.mocked(listControlledWorkerQueueClaimAdmissions).mockResolvedValue(controlledWorkerQueueClaimAdmissionCollectionFixture);
        render(<ControlledWorkerQueueClaimAdmissions candidateId={workerBindingActivationEvidenceFixture.candidate_record_id} activationEvidenceId={workerBindingActivationEvidenceFixture.activation_evidence_id} />);
        expect(await screen.findByText(/recorded controlled worker queue claim admission evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/readiness\/start-admission state: queue-claim admission evidence recorded/i)).toHaveTextContent(/worker-start admission: not defined; blocked: yes/i);
        expect(screen.getByText(/readiness\/start-admission state: queue-claim admission evidence recorded/i)).toHaveTextContent(/queue claimed: false; queue leased: false; queue acknowledged: false; worker started: false; Agent invoked: false; execution started: false/i);
        expect(screen.getByText(/v0\.50 progress: prerequisite frozen, documentation-only/i)).toHaveTextContent(/queue claim, lease, acknowledgement, worker-start admission, worker start, Agent invocation, and execution are still unavailable/i);
        expect(screen.getByText(/v0\.51 state is shown below when Core has recorded it/i)).toHaveTextContent(/read-only evidence/i);
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
});
