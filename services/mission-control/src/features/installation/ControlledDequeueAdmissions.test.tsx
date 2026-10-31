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
vi.mock("./OneShotControlledDequeues", () => ({ OneShotControlledDequeues: () => <section aria-label="One-shot controlled dequeue evidence">Nested one-shot controlled dequeue evidence</section> }));

const empty: ControlledDequeueAdmissionCollectionV1 = { ...controlledDequeueAdmissionCollectionFixture, items: [], count: 0 };

describe("ControlledDequeueAdmissions", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        session.value = { authenticated: false, principal: null, csrfToken: null };
        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(empty);
        vi.mocked(getQueueObservation).mockResolvedValue(queueObservationResultFixture);
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue(controlledDequeueAdmissionResultFixture);
    });

    it("renders review states and retries a failed read without resending a write", async () => {
        let resolve!: (value: ControlledDequeueAdmissionCollectionV1) => void;
        vi.mocked(listControlledDequeueAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved queue removal review/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue removal review has been saved/i));
        unmount();

        vi.mocked(listControlledDequeueAdmissions)
            .mockRejectedValueOnce(new Error("secret /internal/path 10.0.0.1"))
            .mockResolvedValueOnce(empty);
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/retry to check its current status/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue removal review has been saved/i));
        expect(createControlledDequeueAdmission).not.toHaveBeenCalled();
        unmount();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(controlledDequeueAdmissionCollectionFixture);
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText("A queue removal review record has been saved.")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument();
        expect(screen.getByText("Queue removal review is current")).toBeInTheDocument();
        expect(screen.getByText("Technical details")).toBeInTheDocument();
        expect(screen.getByLabelText("What needs attention")).toHaveTextContent(/Atlas has not set up a way to remove queued work.*Atlas has not set up a way to read work from a queue.*Atlas has not set up a way to claim queued work.*Atlas has not set up a way to reserve queued work.*Atlas has not set up a way to acknowledge queued work.*Atlas has not set up a way to start a worker.*Atlas has not set up a safe way to start this installation/i);
        expect(screen.getByText("dequeue_not_defined")).not.toBeVisible();
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByLabelText(/controlled dequeue admission fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*queue consumedfalse.*worker startedfalse.*process execution allowedfalse/i);
        expect(screen.getByLabelText(/one-shot controlled dequeue evidence/i)).toHaveTextContent(/nested one-shot controlled dequeue evidence/i);
        expect(document.body.textContent).not.toMatch(/amqp|secret|internal\/path|10\.0\.0\.1|lease token|acknowledgement token/i);
        unmount();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(empty);
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue({ ...ambiguousControlledDequeueAdmissionResultFixture, error: { ...ambiguousControlledDequeueAdmissionResultFixture.error!, error_code: "evidence_stale" } });
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/no queue removal review has been saved/i)).toBeInTheDocument();
        fireEvent.click(await screen.findByRole("button", { name: "Review queue removal statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Save review record" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/Some review information is out of date/i);
        expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument();
    });

    it("requires dedicated permissions and creates admission only from queue observation readback", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        const { rerender } = render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument();
        expect(await screen.findByText(/Saving this review needs a current queue receipt/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        rerender(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        fireEvent.click(await screen.findByRole("button", { name: "Review queue removal statement" }));
        expect(screen.getByLabelText("Controlled dequeue admission confirmation")).toHaveTextContent("Record controlled dequeue admission evidence only. This does not dequeue, poll, claim, lease, acknowledge, consume, remove, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.");
        fireEvent.click(screen.getByRole("button", { name: "Save review record" }));
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
        await waitFor(() => expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument());
    });

    it("withholds admission evidence controls when the signed-in session has no CSRF token", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: null };
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);

        expect(await screen.findByText(/Saving this review needs a current queue receipt/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Controlled dequeue admission confirmation")).not.toBeInTheDocument();
        expect(createControlledDequeueAdmission).not.toHaveBeenCalled();
    });

    it("renders ambiguous create response as blocked with no prohibited control", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue(ambiguousControlledDequeueAdmissionResultFixture);
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/no queue removal review has been saved/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review queue removal statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Save review record" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/Atlas cannot confirm the current status/i);
        expect(screen.queryByRole("button", { name: "Review queue removal statement" })).not.toBeInTheDocument();
        expect(document.body.textContent).not.toMatch(/dequeue now|poll queue|claim item|lease item|ack now|consume item|remove item|retry now|resend now|start worker|execute now|install now|deploy now|roll back now/i);
    });
});
