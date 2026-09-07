import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getControlledWorkerQueueReceipt, parseControlledWorkerQueueReceipt } from "../../api/controlledWorkerQueueReceipt";
import fixture from "../../test/controlledWorkerQueueReceipt";
import { ControlledWorkerQueueReceipt } from "./ControlledWorkerQueueReceipt";
import { ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "./ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions";
import { listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions } from "../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";

vi.mock("../../api/controlledWorkerQueueReceipt", async (original) => ({ ...await original<object>(), getControlledWorkerQueueReceipt: vi.fn() }));
vi.mock("../../api/controlledWorkerQueueClaimLeaseAcknowledgementAdmission", async (original) => ({ ...await original<object>(), listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions: vi.fn() }));
const props = { candidateId: fixture.record.candidate_record_id, admissionId: fixture.record.admission_id, operatorId: fixture.record.operator_id };
const receipt = parseControlledWorkerQueueReceipt(fixture, props.candidateId, props.admissionId, props.operatorId);

describe("v0.52 installation receipt presentation", () => {
    beforeEach(() => vi.resetAllMocks());
    it("shows simple recorded state and collapsed evidence without controls", async () => {
        vi.mocked(getControlledWorkerQueueReceipt).mockResolvedValue(receipt);
        const { container } = render(<ControlledWorkerQueueReceipt {...props} />);
        expect(screen.getByRole("status")).toHaveTextContent(/Loading/);
        expect(await screen.findByText(/Core recorded the queue claim/)).toBeVisible();
        expect(screen.getByText(/Worker start and execution remain blocked/)).toBeVisible();
        const details = screen.getByText("Advanced v0.52 evidence").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(props.admissionId)).not.toBeVisible();
        expect(details).toHaveTextContent(/Reservation before effecttrue/);
        expect(container.querySelectorAll("button,input,form,select,textarea")).toHaveLength(0);
    });
    it("presents Core expiry and redacts unavailable, unauthorized and missing evidence", async () => {
        vi.mocked(getControlledWorkerQueueReceipt).mockResolvedValue({ ...receipt, lifecycle: "expired" });
        const { unmount } = render(<ControlledWorkerQueueReceipt {...props} />);
        expect(await screen.findByText(/Core reports this evidence has expired/)).toBeVisible();
        unmount();
        vi.mocked(getControlledWorkerQueueReceipt).mockRejectedValue(new Error("secret internal endpoint 403"));
        render(<ControlledWorkerQueueReceipt {...props} />);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/unavailable or has not been recorded/));
        expect(screen.queryByText(/secret internal/)).not.toBeInTheDocument();
    });
    it("clears prior evidence on scope change and ignores late responses", async () => {
        let resolve!: (value: typeof receipt) => void;
        vi.mocked(getControlledWorkerQueueReceipt).mockResolvedValueOnce(receipt).mockReturnValueOnce(new Promise((done) => { resolve = done; })).mockRejectedValueOnce(new Error("forbidden"));
        const { rerender } = render(<ControlledWorkerQueueReceipt {...props} />);
        await screen.findByText(/Core recorded/);
        rerender(<ControlledWorkerQueueReceipt {...props} operatorId="second-owner" />);
        expect(screen.queryByText(/Core recorded/)).not.toBeInTheDocument();
        rerender(<ControlledWorkerQueueReceipt {...props} candidateId="another-candidate" />);
        await act(async () => resolve(receipt));
        expect(screen.queryByText(/Core recorded/)).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(/unavailable/);
    });
    it("is reachable beneath v0.51 admission evidence in the existing workflow", async () => {
        const admission = fixture.record.controlled_worker_queue_claim_lease_acknowledgement_admission;
        vi.mocked(listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions).mockResolvedValue({ items: [admission] } as never);
        vi.mocked(getControlledWorkerQueueReceipt).mockResolvedValue(receipt);
        render(<ControlledWorkerQueueClaimLeaseAcknowledgementAdmissions candidateId={props.candidateId} v049AdmissionId={admission.controlled_worker_queue_claim_lease_acknowledgement_prerequisite.admission_id} />);
        expect(await screen.findByText(/Core recorded the queue claim/)).toBeVisible();
        expect(getControlledWorkerQueueReceipt).toHaveBeenCalledWith(props.candidateId, props.admissionId, props.operatorId);
    });
});
