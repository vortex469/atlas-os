import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture } from "../../test/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { controlledWorkerQueueClaimAdmissionFixture } from "../../test/controlledWorkerQueueClaimAdmission";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 } from "../../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "./ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions";

vi.mock("../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission", () => ({ listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions: vi.fn() }));

const empty: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 = { ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture, items: [], count: 0 };

describe("ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1) => void;
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking the saved review/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no review has been saved/i));
        unmount();

        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/private system details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("retries only the saved review read", async () => {
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockRejectedValueOnce(new Error("secret /internal/path"));
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);

        expect(await screen.findByRole("alert")).toHaveTextContent(/retry to check its status/i);
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));

        expect(await screen.findByText(/no review has been saved/i)).toBeInTheDocument();
        expect(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).toHaveBeenCalledTimes(2);
    });

    it("renders simple v0.51 state with technical evidence under Advanced details", async () => {
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockResolvedValue(controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture);
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(await screen.findByText(/queue and worker review saved/i)).toBeInTheDocument();
        expect(screen.getByText(/queue access and worker start are not available/i)).toHaveTextContent(/this record only saves review evidence/i);
        const advanced = screen.getByText("Technical details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(advanced).toHaveTextContent(/v0\.50 prerequisite state/i);
        expect(screen.getByLabelText(/ordered controlled queue claim lease acknowledgement admission blockers/i)).toHaveTextContent(/queue_adapter_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_admission_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByLabelText(/controlled queue claim lease acknowledgement fixed-false authority fields/i)).toHaveTextContent(/queue adapter definedfalse.*queue claim allowedfalse.*queue claimedfalse.*queue leasedfalse.*queue acknowledgedfalse.*agent invokedfalse.*execution startedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
