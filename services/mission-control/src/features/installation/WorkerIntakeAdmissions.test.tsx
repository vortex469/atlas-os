import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerIntakeAdmissions } from "../../api/workerIntakeAdmission";
import { workerIntakeAdmissionCollectionFixture } from "../../test/workerIntakeAdmission";
import { workerQueueReservationResultFixture } from "../../test/workerQueueReservation";
import type { WorkerIntakeAdmissionCollectionV1 } from "../../types/workerIntakeAdmission";
import { WorkerIntakeAdmissions } from "./WorkerIntakeAdmissions";

vi.mock("../../api/workerIntakeAdmission", () => ({ listWorkerIntakeAdmissions: vi.fn() }));
vi.mock("./LiveEnqueueAdmissions", () => ({ LiveEnqueueAdmissions: () => <section aria-label="Live enqueue admission evidence">Nested live enqueue evidence</section> }));

const reservation = workerQueueReservationResultFixture.reservation!;
const empty: WorkerIntakeAdmissionCollectionV1 = { ...workerIntakeAdmissionCollectionFixture, items: [], count: 0 };

describe("WorkerIntakeAdmissions", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listWorkerIntakeAdmissions).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: WorkerIntakeAdmissionCollectionV1) => void;
        vi.mocked(listWorkerIntakeAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading worker intake admission status/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker intake admission evidence/i));
        unmount();

        vi.mocked(listWorkerIntakeAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders operator status while keeping technical evidence under Advanced details", async () => {
        vi.mocked(listWorkerIntakeAdmissions).mockResolvedValue(workerIntakeAdmissionCollectionFixture);
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(await screen.findByText(/recorded worker intake admission evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/worker contacted: false; worker started: false; work enqueued: false/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered worker intake admission blockers/i)).toHaveTextContent(/live_enqueue_not_defined.*dequeue_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText("Advanced details")).toBeInTheDocument();
        expect(screen.getByLabelText(/worker intake admission fixed-false authority fields/i)).toHaveTextContent(/live enqueue allowedfalse.*worker start allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("preserves Home Assistant blocked copy", async () => {
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked />);
        expect(await screen.findByText(/For Home Assistant, worker intake admission remains blocked/i)).toHaveTextContent(/non-installable and non-executable/i);
    });
});
