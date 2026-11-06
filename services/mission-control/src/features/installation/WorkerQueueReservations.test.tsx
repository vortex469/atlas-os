import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerQueueReservations } from "../../api/workerQueueReservation";
import { workerQueueReservationResultFixture } from "../../test/workerQueueReservation";
import type { WorkerQueueReservationCollectionV1 } from "../../types/workerQueueReservation";
import { WorkerQueueReservations } from "./WorkerQueueReservations";

vi.mock("../../api/workerQueueReservation", () => ({ listWorkerQueueReservations: vi.fn() }));
vi.mock("./WorkerIntakeAdmissions", () => ({ WorkerIntakeAdmissions: () => null }));

const reservation = workerQueueReservationResultFixture.reservation!;
const empty: WorkerQueueReservationCollectionV1 = { schema: "worker-queue-reservation-collection-v1", items: [], count: 0, evidence_only: true };

describe("WorkerQueueReservations", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listWorkerQueueReservations).mockResolvedValue(empty); });

    it("shows a plain loading state, empty state, and safe retry after a failed read", async () => {
        let resolve!: (value: WorkerQueueReservationCollectionV1) => void;
        vi.mocked(listWorkerQueueReservations).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
        const view = render(<WorkerQueueReservations candidateId={reservation.candidate_record_id} stubId={reservation.linkage.worker_admission_stub_id} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved queue review record/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue review record has been saved/i));
        view.unmount();

        vi.mocked(listWorkerQueueReservations).mockRejectedValueOnce(new Error("secret /internal/path 10.0.0.1"));
        render(<WorkerQueueReservations candidateId={reservation.candidate_record_id} stubId={reservation.linkage.worker_admission_stub_id} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/could not load the queue review record/i);
        expect(document.body).not.toHaveTextContent(/secret|internal\/path|10\.0\.0\.1/i);
        vi.mocked(listWorkerQueueReservations).mockResolvedValueOnce(empty);
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(await screen.findByText("No queue review record has been saved. Atlas cannot enqueue or start work.")).toBeInTheDocument();
        expect(listWorkerQueueReservations).toHaveBeenCalledTimes(3);
    });

    it("keeps queue IDs, limits, and fingerprints collapsed by default", async () => {
        vi.mocked(listWorkerQueueReservations).mockResolvedValueOnce({ ...empty, items: [workerQueueReservationResultFixture], count: 1 });
        render(<WorkerQueueReservations candidateId={reservation.candidate_record_id} stubId={reservation.linkage.worker_admission_stub_id} homeAssistantBlocked={false} />);
        expect(await screen.findByText("Queue review record is current")).toBeInTheDocument();
        expect(screen.getByText(/this record has not put work in a queue or started a worker/i)).toBeInTheDocument();
        expect(screen.getByText("Atlas has not set up a live queue.")).toBeInTheDocument();
        const details = screen.getByText("Technical details").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(reservation.reservation_id)).not.toBeVisible();
        expect(screen.getByText(/sandbox and resource limits/i)).not.toBeVisible();
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText(reservation.reservation_id)).toBeVisible();
        expect(screen.getByText(/sandbox and resource limits/i)).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
