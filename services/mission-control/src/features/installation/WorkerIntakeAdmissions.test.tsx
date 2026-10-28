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

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: WorkerIntakeAdmissionCollectionV1) => void;
        vi.mocked(listWorkerIntakeAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved worker intake reviews/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker intake review is saved/i));
        unmount();

        vi.mocked(listWorkerIntakeAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("summarizes the saved review and keeps technical evidence in closed details", async () => {
        vi.mocked(listWorkerIntakeAdmissions).mockResolvedValue(workerIntakeAdmissionCollectionFixture);
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("heading", { name: "Saved worker intake review" })).toBeInTheDocument();
        expect(screen.getByText(/does not mean a worker is available or that work can start/i)).toBeInTheDocument();
        expect(screen.getByLabelText("Why work cannot start")).toHaveTextContent(/safe way to add work to a queue.*safe way to take work from a queue.*safe way to start a worker.*safe way to start installation/i);
        expect(screen.getByLabelText("Safety limits recorded for a future worker")).toHaveTextContent(/No network access.*No access to host, repository, or guest files.*No elevated privileges.*1 CPU core.*512 MiB memory.*64 processes.*15 minutes.*1 MiB output.*256 MiB temporary workspace/i);
        const workerDetails = screen.getByText("Worker and intake details").closest("details");
        expect(workerDetails).not.toHaveAttribute("open");
        expect(screen.getByText(workerIntakeAdmissionCollectionFixture.items[0].admission_id)).not.toBeVisible();
        expect(screen.getByLabelText(/worker intake admission fixed-false authority fields/i)).toHaveTextContent(/live enqueue allowedfalse.*worker start allowedfalse.*process execution allowedfalse/i);
        expect(screen.getByText("Exact safety limits and earlier evidence").closest("details")).not.toHaveAttribute("open");
        fireEvent.click(screen.getByText("Worker and intake details"));
        expect(workerDetails).toHaveAttribute("open");
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("preserves Home Assistant blocked copy", async () => {
        render(<WorkerIntakeAdmissions candidateId={reservation.candidate_record_id} reservationId={reservation.reservation_id} homeAssistantBlocked />);
        expect(await screen.findByText(/Atlas cannot install Home Assistant/i)).toHaveTextContent(/cannot be prepared for a worker/i);
    });
});
