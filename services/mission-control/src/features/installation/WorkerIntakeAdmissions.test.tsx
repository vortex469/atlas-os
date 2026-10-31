import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

    it("renders checking, empty, and redacted error states with a safe retry", async () => {
        let resolve!: (value: WorkerIntakeAdmissionCollectionV1) => void;
        vi.mocked(listWorkerIntakeAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved worker intake record/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker intake review record has been saved/i));
        unmount();

        vi.mocked(listWorkerIntakeAdmissions)
            .mockRejectedValueOnce(new Error("secret /internal/path 10.0.0.1"))
            .mockResolvedValueOnce(empty);
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/private system details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker intake review record has been saved/i));
        expect(listWorkerIntakeAdmissions).toHaveBeenCalledTimes(3);
    });

    it("shows plain-language status while keeping technical evidence collapsed", async () => {
        vi.mocked(listWorkerIntakeAdmissions).mockResolvedValue(workerIntakeAdmissionCollectionFixture);
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(await screen.findByText("Worker intake record is current")).toBeInTheDocument();
        expect(screen.getByText(/has not contacted a worker or put work on a queue/i)).toBeInTheDocument();
        expect(screen.getByLabelText("What needs attention")).toHaveTextContent(/Atlas has not set up a live queue.*Atlas has not set up a way to remove queued work.*Atlas has not set up a way to start a worker.*Atlas has not set up a safe way to start this installation/i);
        expect(screen.getByText("Technical details")).toBeInTheDocument();
        expect(screen.getByText("live_enqueue_not_defined")).not.toBeVisible();
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByLabelText(/worker intake admission fixed-false authority fields/i)).toHaveTextContent(/live enqueue allowedfalse.*worker start allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("leaves Home Assistant guidance to the parent review", async () => {
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked />);
        expect(screen.queryByText(/For Home Assistant, worker intake admission remains blocked/i)).not.toBeInTheDocument();
    });
});
