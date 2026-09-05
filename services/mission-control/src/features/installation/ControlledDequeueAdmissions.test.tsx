import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createControlledDequeueAdmission, listControlledDequeueAdmissions } from "../../api/controlledDequeueAdmission";
import { getQueueObservation } from "../../api/queueObservation";
import { ambiguousControlledDequeueAdmissionResultFixture, controlledDequeueAdmissionCollectionFixture, controlledDequeueAdmissionResultFixture } from "../../test/controlledDequeueAdmission";
import { queueObservationReceiptFixture, queueObservationResultFixture } from "../../test/queueObservation";
import type { ControlledDequeueAdmissionCollectionV1 } from "../../types/controlledDequeueAdmission";
import { ControlledDequeueAdmissions } from "./ControlledDequeueAdmissions";

const session = vi.hoisted(() => ({ value: { authenticated: false, principal: null as { operator_id: string; permissions: string[] } | null, csrfToken: null as string | null } }));
vi.mock("../../hooks/operatorSessionContext", () => ({ useOperatorSession: () => session.value }));
vi.mock("../../api/queueObservation", async (original) => {
    const module = await original<typeof import("../../api/queueObservation")>();
    return { ...module, getQueueObservation: vi.fn() };
});
vi.mock("../../api/controlledDequeueAdmission", async (original) => {
    const module = await original<typeof import("../../api/controlledDequeueAdmission")>();
    return { ...module, listControlledDequeueAdmissions: vi.fn(), createControlledDequeueAdmission: vi.fn(), controlledDequeueAdmissionIdempotencyKey: () => "stable-controlled-dequeue-key" };
});

const empty: ControlledDequeueAdmissionCollectionV1 = { ...controlledDequeueAdmissionCollectionFixture, items: [], count: 0 };

describe("ControlledDequeueAdmissions", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        session.value = { authenticated: false, principal: null, csrfToken: null };
        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(empty);
        vi.mocked(getQueueObservation).mockResolvedValue(queueObservationResultFixture);
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue(controlledDequeueAdmissionResultFixture);
    });

    it("renders blocked, ready, stale, ambiguous, and redacted states", async () => {
        let resolve!: (value: ControlledDequeueAdmissionCollectionV1) => void;
        vi.mocked(listControlledDequeueAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading controlled dequeue admission evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByText(/readiness: blocked or not yet admitted/i)).toBeInTheDocument());
        expect(screen.getByRole("status")).toHaveTextContent(/no controlled dequeue admission evidence/i);
        unmount();

        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(controlledDequeueAdmissionCollectionFixture);
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        await waitFor(() => expect(screen.getAllByText(/ready for later dequeue consideration/i).length).toBeGreaterThan(0));
        expect(screen.getByText("Advanced controlled dequeue admission details")).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered controlled dequeue admission blockers/i)).toHaveTextContent(/dequeue_not_defined.*queue_polling_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByLabelText(/controlled dequeue admission fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*queue consumedfalse.*worker startedfalse.*process execution allowedfalse/i);
        expect(document.body.textContent).not.toMatch(/amqp|secret|internal\/path|10\.0\.0\.1|lease token|acknowledgement token/i);
        unmount();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(empty);
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue({ ...ambiguousControlledDequeueAdmissionResultFixture, error: { ...ambiguousControlledDequeueAdmissionResultFixture.error!, error_code: "evidence_stale" } });
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/readiness: blocked or not yet admitted/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review controlled dequeue admission statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Record admission evidence" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/evidence stale/i);
    });

    it("requires dedicated permissions and creates admission only from queue observation readback", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        const { rerender } = render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/recording remains blocked/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review controlled dequeue admission statement" })).not.toBeInTheDocument();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        rerender(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        fireEvent.click(await screen.findByRole("button", { name: "Review controlled dequeue admission statement" }));
        expect(screen.getByLabelText("Controlled dequeue admission confirmation")).toHaveTextContent("Record controlled dequeue admission evidence only. This does not dequeue, poll, claim, lease, acknowledge, consume, remove, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.");
        fireEvent.click(screen.getByRole("button", { name: "Record admission evidence" }));
        await waitFor(() => expect(createControlledDequeueAdmission).toHaveBeenCalled());
        expect(getQueueObservation).toHaveBeenCalledWith(queueObservationReceiptFixture.candidate_record_id, queueObservationReceiptFixture.receipt_id);
        expect(createControlledDequeueAdmission).toHaveBeenCalledWith(queueObservationReceiptFixture.candidate_record_id, expect.objectContaining({
            schema: "controlled-dequeue-admission-create-v1",
            queue_observation_receipt_id: queueObservationReceiptFixture.receipt_id,
            evidence_only: true,
            dequeue_allowed: false,
            queue_polling_allowed: false,
            queue_claim_allowed: false,
            queue_lease_allowed: false,
            queue_ack_allowed: false,
            worker_start_allowed: false,
            process_execution_allowed: false,
        }), "csrf", "stable-controlled-dequeue-key");
    });

    it("renders ambiguous create response as blocked with no prohibited control", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue(ambiguousControlledDequeueAdmissionResultFixture);
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/readiness: blocked or not yet admitted/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review controlled dequeue admission statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Record admission evidence" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/ambiguous state/i);
        expect(document.body.textContent).not.toMatch(/dequeue now|poll queue|claim item|lease item|ack now|consume item|remove item|retry now|resend now|start worker|execute now|install now|deploy now|roll back now/i);
    });
});
