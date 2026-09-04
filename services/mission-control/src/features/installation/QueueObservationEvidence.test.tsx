import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getOneShotLiveEnqueue } from "../../api/oneShotLiveEnqueue";
import { createQueueObservation, listQueueObservations } from "../../api/queueObservation";
import { oneShotLiveEnqueueFixture, oneShotLiveEnqueueResultFixture } from "../../test/oneShotLiveEnqueue";
import { ambiguousQueueObservationResultFixture, queueObservationCollectionFixture, queueObservationResultFixture } from "../../test/queueObservation";
import type { QueueObservationReceiptCollectionV1 } from "../../types/queueObservation";
import { QueueObservationEvidence } from "./QueueObservationEvidence";

const session = vi.hoisted(() => ({ value: { authenticated: false, principal: null as { operator_id: string; permissions: string[] } | null, csrfToken: null as string | null } }));
vi.mock("../../hooks/operatorSessionContext", () => ({ useOperatorSession: () => session.value }));
vi.mock("../../api/oneShotLiveEnqueue", () => ({ getOneShotLiveEnqueue: vi.fn() }));
vi.mock("../../api/queueObservation", async (original) => {
    const module = await original<typeof import("../../api/queueObservation")>();
    return { ...module, listQueueObservations: vi.fn(), createQueueObservation: vi.fn(), queueObservationIdempotencyKey: () => "stable-observation-key" };
});

const empty: QueueObservationReceiptCollectionV1 = { ...queueObservationCollectionFixture, items: [], count: 0 };

describe("QueueObservationEvidence", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        session.value = { authenticated: false, principal: null, csrfToken: null };
        vi.mocked(listQueueObservations).mockResolvedValue(empty);
        vi.mocked(getOneShotLiveEnqueue).mockResolvedValue(oneShotLiveEnqueueResultFixture);
        vi.mocked(createQueueObservation).mockResolvedValue(queueObservationResultFixture);
    });

    it("renders pending, observed, and redacted blocked states", async () => {
        let resolve!: (value: QueueObservationReceiptCollectionV1) => void;
        vi.mocked(listQueueObservations).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading queue observation evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByText(/state: pending or blocked/i)).toBeInTheDocument());
        expect(screen.getByRole("status")).toHaveTextContent(/no observation receipt evidence/i);
        unmount();

        vi.mocked(listQueueObservations).mockResolvedValue(queueObservationCollectionFixture);
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        await waitFor(() => expect(screen.getAllByText(/state: observed/i).length).toBeGreaterThan(0));
        expect(screen.getByText(/observed queued item/i)).toBeInTheDocument();
        expect(screen.getByText("Advanced queue observation details")).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered queue observation blockers/i)).toHaveTextContent(/dequeue_not_defined.*queue_polling_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByLabelText(/queue observation fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(document.body.textContent).not.toMatch(/amqp|secret|internal\/path|10\.0\.0\.1/i);
    });

    it("uses the exact two-step confirmation and dedicated permission before creating evidence", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.queue_observation.record", "installation.execution.one_shot_live_enqueue.read"] }, csrfToken: "csrf" };
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(await screen.findByText(/state: pending or blocked/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review queue observation evidence statement" }));
        expect(screen.getByLabelText("Queue observation evidence confirmation")).toHaveTextContent("Record bounded queue observation evidence only. This does not dequeue, poll as a consumer, claim, lease, acknowledge, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.");
        fireEvent.click(screen.getByRole("button", { name: "Record observation evidence" }));
        await waitFor(() => expect(createQueueObservation).toHaveBeenCalled());
        expect(getOneShotLiveEnqueue).toHaveBeenCalledWith(oneShotLiveEnqueueFixture.candidate_record_id, oneShotLiveEnqueueFixture.enqueue_id);
        expect(createQueueObservation).toHaveBeenCalledWith(oneShotLiveEnqueueFixture.candidate_record_id, expect.objectContaining({
            schema: "queue-observation-receipt-create-v1",
            enqueue_id: oneShotLiveEnqueueFixture.enqueue_id,
            observation_only: true,
            dequeue_allowed: false,
            worker_start_allowed: false,
            execution_authorized: false,
        }), "csrf", "stable-observation-key");
    });

    it("renders ambiguous create response as pending or blocked with no prohibited control", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.queue_observation.record", "installation.execution.one_shot_live_enqueue.read"] }, csrfToken: "csrf" };
        vi.mocked(createQueueObservation).mockResolvedValue(ambiguousQueueObservationResultFixture);
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(await screen.findByText(/state: pending or blocked/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review queue observation evidence statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Record observation evidence" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/ambiguous state/i);
        expect(document.body.textContent).not.toMatch(/dequeue now|retry now|resend now|start worker|execute now|install now|deploy now|roll back now/i);
    });
});
