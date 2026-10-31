import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getControlledDequeueAdmission } from "../../api/controlledDequeueAdmission";
import { createOneShotControlledDequeue, listOneShotControlledDequeues } from "../../api/oneShotControlledDequeue";
import { controlledDequeueAdmissionFixture, controlledDequeueAdmissionResultFixture } from "../../test/controlledDequeueAdmission";
import { blockedOneShotControlledDequeueResultFixture, oneShotControlledDequeueCollectionFixture, oneShotControlledDequeueResultFixture } from "../../test/oneShotControlledDequeue";
import type { OneShotControlledDequeueCollectionV1 } from "../../types/oneShotControlledDequeue";
import { OneShotControlledDequeues } from "./OneShotControlledDequeues";

const session = vi.hoisted(() => ({ value: { authenticated: false, principal: null as { operator_id: string; permissions: string[] } | null, csrfToken: null as string | null } }));
vi.mock("../../hooks/operatorSessionContext", () => ({ useOperatorSession: () => session.value }));
vi.mock("../../api/controlledDequeueAdmission", async (original) => {
    const module = await original<typeof import("../../api/controlledDequeueAdmission")>();
    return { ...module, getControlledDequeueAdmission: vi.fn() };
});
vi.mock("../../api/oneShotControlledDequeue", async (original) => {
    const module = await original<typeof import("../../api/oneShotControlledDequeue")>();
    return { ...module, listOneShotControlledDequeues: vi.fn(), createOneShotControlledDequeue: vi.fn(), oneShotControlledDequeueIdempotencyKey: () => "stable-one-shot-controlled-key" };
});
vi.mock("./OneShotDequeueWorkerBindings", () => ({ OneShotDequeueWorkerBindings: () => <section aria-label="One-shot dequeue worker binding evidence">Nested v0.46 binding evidence</section> }));

const empty: OneShotControlledDequeueCollectionV1 = { ...oneShotControlledDequeueCollectionFixture, items: [], count: 0 };
const props = {
    candidateId: controlledDequeueAdmissionFixture.candidate_record_id,
    admission: controlledDequeueAdmissionFixture,
};

describe("OneShotControlledDequeues", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        session.value = { authenticated: false, principal: null, csrfToken: null };
        vi.mocked(listOneShotControlledDequeues).mockResolvedValue(empty);
        vi.mocked(getControlledDequeueAdmission).mockResolvedValue(controlledDequeueAdmissionResultFixture);
        vi.mocked(createOneShotControlledDequeue).mockResolvedValue(oneShotControlledDequeueResultFixture);
    });

    it("renders loading, empty, recorded, and redacted states", async () => {
        let resolve!: (value: OneShotControlledDequeueCollectionV1) => void;
        vi.mocked(listOneShotControlledDequeues).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<OneShotControlledDequeues {...props} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking the removal record/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no removal result has been recorded/i));
        unmount();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.record", "installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: "csrf" };
        vi.mocked(listOneShotControlledDequeues).mockResolvedValue(oneShotControlledDequeueCollectionFixture);
        render(<OneShotControlledDequeues {...props} />);
        expect(await screen.findByText(/status: removed/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review removal" })).not.toBeInTheDocument();
        expect(screen.getByText("Technical details")).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered one-shot controlled dequeue blockers/i)).toHaveTextContent(/queue_polling_not_defined.*queue_claim_not_defined.*queue_lease_not_defined.*queue_ack_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByLabelText(/one-shot controlled dequeue fixed-false authority fields/i)).toHaveTextContent(/queue polling allowedfalse.*worker startedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(document.body.textContent).not.toMatch(/amqp|secret|internal\/path|10\.0\.0\.1|lease token|acknowledgement token/i);
        unmount();

        vi.mocked(listOneShotControlledDequeues).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<OneShotControlledDequeues {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/private system details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("retries only the receipt-list read after a load failure", async () => {
        vi.mocked(listOneShotControlledDequeues).mockRejectedValueOnce(new Error("secret /internal/path"));
        const { getByRole, findByText } = render(<OneShotControlledDequeues {...props} />);

        expect(await screen.findByRole("alert")).toHaveTextContent(/retry to check its status/i);
        expect(screen.getByText(/status: unavailable/i)).toBeInTheDocument();
        fireEvent.click(getByRole("button", { name: "Retry" }));

        expect(await findByText(/no removal result has been recorded/i)).toBeInTheDocument();
        expect(listOneShotControlledDequeues).toHaveBeenCalledTimes(2);
        expect(createOneShotControlledDequeue).not.toHaveBeenCalled();
    });

    it("requires dedicated permissions and creates only from controlled dequeue admission readback", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: "csrf" };
        const { rerender } = render(<OneShotControlledDequeues {...props} />);
        expect(screen.queryByRole("button", { name: "Review removal" })).not.toBeInTheDocument();
        expect(await screen.findByText(/this action is unavailable/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review removal" })).not.toBeInTheDocument();

        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.record", "installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: "csrf" };
        rerender(<OneShotControlledDequeues {...props} />);
        fireEvent.click(await screen.findByRole("button", { name: "Review removal" }));
        expect(screen.getByLabelText("One-shot controlled dequeue confirmation")).toHaveTextContent(/exact admitted inert item only/i);
        fireEvent.click(screen.getByRole("button", { name: "Record result" }));
        await waitFor(() => expect(createOneShotControlledDequeue).toHaveBeenCalled());
        expect(getControlledDequeueAdmission).toHaveBeenCalledWith(controlledDequeueAdmissionFixture.candidate_record_id, controlledDequeueAdmissionFixture.admission_id);
        expect(createOneShotControlledDequeue).toHaveBeenCalledWith(controlledDequeueAdmissionFixture.candidate_record_id, expect.objectContaining({
            schema: "one-shot-controlled-dequeue-create-v1",
            controlled_dequeue_admission_id: controlledDequeueAdmissionFixture.admission_id,
            queue_observation_receipt_id: controlledDequeueAdmissionFixture.queue_observation_receipt.receipt_id,
            requested_scope: "installation_one_shot_controlled_dequeue_only",
            evidence_only: true,
            dequeue_allowed: false,
            queue_polling_allowed: false,
            queue_claim_allowed: false,
            queue_lease_allowed: false,
            queue_ack_allowed: false,
            worker_start_allowed: false,
            process_execution_allowed: false,
        }), "csrf", "stable-one-shot-controlled-key");
        await waitFor(() => expect(screen.queryByRole("button", { name: "Review removal" })).not.toBeInTheDocument());
    });

    it("withholds one-shot dequeue controls when the signed-in session has no CSRF token", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.record", "installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: null };
        render(<OneShotControlledDequeues {...props} />);

        expect(await screen.findByText(/this action is unavailable/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review removal" })).not.toBeInTheDocument();
        expect(screen.queryByLabelText("One-shot controlled dequeue confirmation")).not.toBeInTheDocument();
        expect(createOneShotControlledDequeue).not.toHaveBeenCalled();
        expect(getControlledDequeueAdmission).not.toHaveBeenCalled();
    });

    it("renders blocked create response without prohibited downstream controls", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.record", "installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: "csrf" };
        vi.mocked(createOneShotControlledDequeue).mockResolvedValue(blockedOneShotControlledDequeueResultFixture);
        render(<OneShotControlledDequeues {...props} />);
        expect(await screen.findByText(/status: not recorded/i)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review removal" }));
        fireEvent.click(screen.getByRole("button", { name: "Record result" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/the removal result was not recorded/i);
        expect(screen.getByRole("alert")).toHaveTextContent(/ambiguous state/i);
        expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review removal" })).not.toBeInTheDocument();
        expect(document.body.textContent).not.toMatch(/poll queue|claim item|lease item|ack now|consume item|remove item|retry now|resend now|start worker|execute now|install now|deploy now|roll back now/i);
    });

    it("does not resend an uncertain removal request", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.record", "installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: "csrf" };
        vi.mocked(createOneShotControlledDequeue).mockRejectedValueOnce(new Error("secret /internal/path"));
        render(<OneShotControlledDequeues {...props} />);

        fireEvent.click(await screen.findByRole("button", { name: "Review removal" }));
        fireEvent.click(screen.getByRole("button", { name: "Record result" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/Atlas could not confirm whether it saved the result/i);
        expect(screen.getByText(/status: unconfirmed/i)).toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent(/will not resend/i);
        expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
        expect(createOneShotControlledDequeue).toHaveBeenCalledTimes(1);
    });

    it("allows the operator to review again when the admission preflight read fails before any write", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.one_shot_controlled_dequeue.record", "installation.execution.one_shot_controlled_dequeue.read", "installation.execution.controlled_dequeue_admission.read"] }, csrfToken: "csrf" };
        vi.mocked(getControlledDequeueAdmission).mockRejectedValueOnce(new Error("secret /internal/path"));
        render(<OneShotControlledDequeues {...props} />);

        fireEvent.click(await screen.findByRole("button", { name: "Review removal" }));
        fireEvent.click(screen.getByRole("button", { name: "Record result" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(/no removal was requested/i);
        expect(screen.getByText(/status: not requested/i)).toBeInTheDocument();
        expect(createOneShotControlledDequeue).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "Review again" }));
        expect(screen.getByRole("button", { name: "Review removal" })).toBeInTheDocument();
    });
});
