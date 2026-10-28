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

    it("renders blocked, ready, stale, ambiguous, and redacted states", async () => {
        let resolve!: (value: ControlledDequeueAdmissionCollectionV1) => void;
        vi.mocked(listControlledDequeueAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading dequeue readiness reviews/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByText(/status: not yet recorded/i)).toBeInTheDocument());
        expect(screen.getByRole("status")).toHaveTextContent(/no readiness review is saved/i);
        unmount();

        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(controlledDequeueAdmissionCollectionFixture);
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        await waitFor(() => expect(screen.getAllByText(/status: admission recorded/i).length).toBeGreaterThan(0));
        expect(screen.getByText("Queue and review details")).toBeInTheDocument();
        expect(screen.getByLabelText("Why work cannot be taken")).toHaveTextContent(/safe way to take work from a queue.*safe way to check a queue.*safe way to reserve work from a queue.*safe way to hold work from a queue.*safe way to confirm queue work.*safe way to start a worker.*safe way to start installation/i);
        expect(screen.getByLabelText("Limits recorded for a future worker")).toHaveTextContent(/No network access.*No access to host, repository, or guest files.*No elevated privileges.*1 CPU core.*512 MiB memory.*64 processes.*15 minutes.*1 MiB output.*256 MiB temporary workspace/i);
        expect(screen.getByText("Queue and review details").closest("details")).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/controlled dequeue admission fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*queue consumedfalse.*worker startedfalse.*process execution allowedfalse/i);
        expect(screen.getByLabelText(/one-shot controlled dequeue evidence/i)).toHaveTextContent(/nested one-shot controlled dequeue evidence/i);
        expect(document.body.textContent).not.toMatch(/amqp|secret|internal\/path|10\.0\.0\.1|lease token|acknowledgement token/i);
        unmount();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        vi.mocked(listControlledDequeueAdmissions).mockResolvedValue(empty);
        vi.mocked(createControlledDequeueAdmission).mockResolvedValue({ ...ambiguousControlledDequeueAdmissionResultFixture, error: { ...ambiguousControlledDequeueAdmissionResultFixture.error!, error_code: "evidence_stale" } });
        render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/status: not yet recorded/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review what will be recorded" }));
        fireEvent.click(screen.getByRole("button", { name: "Save readiness review" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/an earlier review is out of date/i);
    });

    it("requires dedicated permissions and creates admission only from queue observation readback", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        const { rerender } = render(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        expect(await screen.findByText(/signed-in account with review permission/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review what will be recorded" })).not.toBeInTheDocument();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.controlled_dequeue_admission.record", "installation.execution.controlled_dequeue_admission.read", "installation.execution.queue_observation.read"] }, csrfToken: "csrf" };
        rerender(<ControlledDequeueAdmissions candidateId={queueObservationReceiptFixture.candidate_record_id} observation={queueObservationReceiptFixture} />);
        fireEvent.click(await screen.findByRole("button", { name: "Review what will be recorded" }));
        expect(screen.getByLabelText("Controlled dequeue admission confirmation")).toHaveTextContent("Save evidence that a later queue handoff review may be considered. This does not take work from the queue, contact or start a worker, or run installation.");
        fireEvent.click(screen.getByRole("button", { name: "Save readiness review" }));
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
        expect(await screen.findByText(/status: not yet recorded/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review what will be recorded" }));
        fireEvent.click(screen.getByRole("button", { name: "Save readiness review" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/atlas could not confirm the result/i);
        expect(document.body.textContent).not.toMatch(/dequeue now|poll queue|claim item|lease item|ack now|consume item|remove item|retry now|resend now|start worker|execute now|install now|deploy now|roll back now/i);
    });
});
