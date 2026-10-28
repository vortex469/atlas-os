import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture } from "../../test/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { controlledWorkerQueueClaimAdmissionFixture } from "../../test/controlledWorkerQueueClaimAdmission";
import type { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 } from "../../types/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "./ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions";

vi.mock("../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission", () => ({ listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions: vi.fn() }));
vi.mock("./ControlledWorkerQueueReceipt", () => ({ ControlledWorkerQueueReceipt: () => <section aria-label="Queue receipt evidence">Queue receipt evidence</section> }));

const empty: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 = { ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture, items: [], count: 0 };

describe("ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1) => void;
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading queue readiness/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue readiness record is available/i));
        unmount();

        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("explains blocked queue readiness and keeps technical evidence under Advanced details", async () => {
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockResolvedValue(controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture);
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(await screen.findByText("Queue readiness recorded")).toBeInTheDocument();
        expect(screen.getByText("Queue operations are blocked")).toBeInTheDocument();
        expect(screen.getByText("11 requirements remain unavailable.")).toBeInTheDocument();
        expect(screen.getByText(/This record only lists requirements. It cannot operate the queue or start a worker/i)).toBeInTheDocument();
        expect(screen.getByText(/Core may also show the queue receipt below. It reports recorded queue state and does not add actions here/i)).toBeInTheDocument();
        expect(screen.getByLabelText("Queue receipt evidence")).toBeInTheDocument();
        const blockers = screen.getByText("Show what needs to be in place").closest("details");
        expect(blockers).toBeInTheDocument();
        expect(blockers).not.toHaveAttribute("open");
        expect(screen.getByLabelText("Queue operation blockers")).toHaveTextContent(/The queue connection is not available.*Taking work from the queue is not available.*Holding work from the queue is not available/i);
        const advanced = screen.getByText("Advanced details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(advanced).toHaveTextContent(/v0\.50 prerequisite state/i);
        expect(screen.getByLabelText(/ordered controlled queue claim lease acknowledgement admission blockers/i)).toHaveTextContent(/queue_adapter_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_admission_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByLabelText(/controlled queue claim lease acknowledgement fixed-false authority fields/i)).toHaveTextContent(/queue adapter definedfalse.*queue claim allowedfalse.*queue claimedfalse.*queue leasedfalse.*queue acknowledgedfalse.*agent invokedfalse.*execution startedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("does not call an empty blocker list blocked", async () => {
        const noBlockers: ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionV1 = {
            ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture,
            items: [{ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture.items[0], blockers: [] }],
        };
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockResolvedValue(noBlockers);
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={controlledWorkerQueueClaimAdmissionFixture.candidate_record_id} v049AdmissionId={controlledWorkerQueueClaimAdmissionFixture.admission_id} />);
        expect(await screen.findByText("No blockers are listed. This record still does not operate the queue.")).toBeInTheDocument();
        expect(screen.queryByText("Queue operations are blocked")).not.toBeInTheDocument();
    });
});
