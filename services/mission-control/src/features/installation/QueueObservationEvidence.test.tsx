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

    it("renders receipt states and retries a failed read without resending a write", async () => {
        let resolve!: (value: QueueObservationReceiptCollectionV1) => void;
        vi.mocked(listQueueObservations).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved queue receipt/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue receipt record has been saved/i));
        unmount();

        vi.mocked(listQueueObservations)
            .mockRejectedValueOnce(new Error("secret /internal/path 10.0.0.1"))
            .mockResolvedValueOnce(empty);
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/retry to check its current status/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue receipt record has been saved/i));
        expect(createQueueObservation).not.toHaveBeenCalled();
        unmount();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.queue_observation.record", "installation.execution.one_shot_live_enqueue.read"] }, csrfToken: "csrf" };
        vi.mocked(listQueueObservations).mockResolvedValue(queueObservationCollectionFixture);
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(await screen.findByText("A queue receipt record has been saved.")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review receipt record statement" })).not.toBeInTheDocument();
        expect(screen.getByText("Queue receipt record is current")).toBeInTheDocument();
        expect(screen.getByText("Technical details")).toBeInTheDocument();
        expect(screen.getByLabelText("What needs attention")).toHaveTextContent(/Atlas has not set up a way to remove queued work.*Atlas has not set up a way to read work from a queue.*Atlas has not set up a way to start a worker.*Atlas has not set up a safe way to start this installation/i);
        expect(screen.getByText("dequeue_not_defined")).not.toBeVisible();
        fireEvent.click(screen.getAllByText("Technical details")[0]);
        expect(screen.getByLabelText(/queue observation fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(document.body.textContent).not.toMatch(/amqp|secret|internal\/path|10\.0\.0\.1/i);
    });

    it("uses the exact two-step confirmation and dedicated permission before creating evidence", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.queue_observation.record", "installation.execution.one_shot_live_enqueue.read"] }, csrfToken: "csrf" };
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(screen.queryByRole("button", { name: "Review receipt record statement" })).not.toBeInTheDocument();
        expect(await screen.findByText(/no queue receipt record has been saved/i)).toBeInTheDocument();
        fireEvent.click(await screen.findByRole("button", { name: "Review receipt record statement" }));
        expect(screen.getByLabelText("Queue observation evidence confirmation")).toHaveTextContent("Record bounded queue observation evidence only. This does not dequeue, poll as a consumer, claim, lease, acknowledge, contact or start a worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy, roll back, mutate, or execute anything.");
        fireEvent.click(screen.getByRole("button", { name: "Save receipt record" }));
        await waitFor(() => expect(createQueueObservation).toHaveBeenCalled());
        await waitFor(() => expect(screen.queryByRole("button", { name: "Review receipt record statement" })).not.toBeInTheDocument());
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

    it("withholds observation evidence controls when the signed-in session has no CSRF token", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.queue_observation.record", "installation.execution.one_shot_live_enqueue.read"] }, csrfToken: null };
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);

        expect(await screen.findByText(/Saving this receipt needs a current queue item/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review receipt record statement" })).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Queue observation evidence confirmation")).not.toBeInTheDocument();
        expect(createQueueObservation).not.toHaveBeenCalled();
    });

    it("renders ambiguous create response as pending or blocked with no prohibited control", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.queue_observation.record", "installation.execution.one_shot_live_enqueue.read"] }, csrfToken: "csrf" };
        vi.mocked(createQueueObservation).mockResolvedValue(ambiguousQueueObservationResultFixture);
        render(<QueueObservationEvidence candidateId={oneShotLiveEnqueueFixture.candidate_record_id} oneShot={oneShotLiveEnqueueFixture} />);
        expect(await screen.findByText(/no queue receipt record has been saved/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review receipt record statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Save receipt record" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/Atlas cannot confirm the observation status/i);
        expect(screen.queryByRole("button", { name: "Review receipt record statement" })).not.toBeInTheDocument();
        expect(document.body.textContent).not.toMatch(/dequeue now|retry now|resend now|start worker|execute now|install now|deploy now|roll back now/i);
    });
});
