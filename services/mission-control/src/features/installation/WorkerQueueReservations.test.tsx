import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkerQueueReservations } from "../../api/workerQueueReservation";
import { workerQueueReservationResultFixture } from "../../test/workerQueueReservation";
import type { WorkerQueueReservationCollectionV1 } from "../../types/workerQueueReservation";
import { WorkerQueueReservations } from "./WorkerQueueReservations";

vi.mock("../../api/workerQueueReservation", () => ({ listWorkerQueueReservations: vi.fn() }));
vi.mock("./WorkerIntakeAdmissions", () => ({ WorkerIntakeAdmissions: () => <section aria-label="Worker intake review">Nested worker intake review</section> }));

const empty: WorkerQueueReservationCollectionV1 = {
    schema: "worker-queue-reservation-collection-v1",
    items: [], count: 0, evidence_only: true,
};
const record = workerQueueReservationResultFixture.reservation!;

describe("WorkerQueueReservations", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(listWorkerQueueReservations).mockResolvedValue(empty);
    });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: WorkerQueueReservationCollectionV1) => void;
        vi.mocked(listWorkerQueueReservations).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<WorkerQueueReservations candidateId={record.candidate_record_id} stubId={record.linkage.worker_admission_stub_id} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved queue records/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue record is saved/i));
        unmount();

        vi.mocked(listWorkerQueueReservations).mockRejectedValue(new Error("credential secret /internal/path 10.0.0.1"));
        render(<WorkerQueueReservations candidateId={record.candidate_record_id} stubId={record.linkage.worker_admission_stub_id} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(document.body).not.toHaveTextContent(/credential secret|internal\/path|10\.0\.0\.1/i);
    });

    it("shows the saved queue outcome and safety summary before technical details", async () => {
        const unrelated = structuredClone(workerQueueReservationResultFixture);
        unrelated.reservation!.linkage.worker_admission_stub_id = "00000000-0000-4000-8000-000000000099";
        vi.mocked(listWorkerQueueReservations).mockResolvedValue({ ...empty, items: [unrelated, workerQueueReservationResultFixture], count: 2 });
        render(<WorkerQueueReservations candidateId={record.candidate_record_id} stubId={record.linkage.worker_admission_stub_id} homeAssistantBlocked={false} />);

        expect(await screen.findByRole("heading", { name: "Saved for later queue review" })).toBeInTheDocument();
        expect(screen.getByText("This record does not create a queue, add work, or start a worker.")).toBeInTheDocument();
        const savedAt = document.querySelector(`time[datetime="${record.recorded_at}"]`);
        const expiresAt = document.querySelector(`time[datetime="${record.valid_until}"]`);
        expect(savedAt).toHaveTextContent(new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(record.recorded_at)));
        expect(expiresAt).toHaveTextContent(new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(record.valid_until)));
        expect(savedAt).not.toHaveTextContent(record.recorded_at);
        expect(screen.getByLabelText("Planned queue safety limits")).toHaveTextContent(/no network access or live queue contact.*no access to host, repository, or guest files/i);
        expect(screen.getByLabelText("Planned queue safety limits")).toHaveTextContent(/1 CPU core, 512 MiB memory, 64 processes, 15 minutes, 1 MiB output, and 256 MiB temporary workspace/i);
        expect(screen.getByRole("list", { name: "Saved queue review records" }).children).toHaveLength(1);
        const blockers = screen.getByRole("list", { name: "What still needs to be in place" });
        expect(blockers).toHaveTextContent(/A safe way to add work to a live queue is not defined.*A safe way to take work from a queue is not defined.*A safe way to start a worker is not defined.*A safe way to start installation is not defined/i);
        expect(screen.getByText("Queue intake reference ID")).not.toBeVisible();
        expect(screen.getByText("Sandbox profile")).not.toBeVisible();
        expect(screen.getByLabelText("Queue reservation fixed-false authority fields")).not.toBeVisible();

        fireEvent.click(screen.getByText("Queue and item details"));
        expect(screen.getByText("Queue intake reference ID")).toBeVisible();
        expect(screen.getByText("Queue kind code")).toBeVisible();
        fireEvent.click(screen.getByText("Exact safety limits and earlier evidence"));
        expect(screen.getByText("Sandbox profile")).toBeVisible();
        expect(screen.getByText("Earlier evidence chain fingerprint")).toBeVisible();
        fireEvent.click(screen.getByText("Audit and authority details"));
        expect(screen.getByText(/This review record is reserved permanently/i)).toBeVisible();
        expect(screen.getByLabelText("Queue reservation fixed-false authority fields")).toHaveTextContent(/Live enqueue allowedfalse.*Worker start allowedfalse.*Replay bypass allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("keeps Home Assistant blocked", async () => {
        render(<WorkerQueueReservations candidateId={record.candidate_record_id} stubId={record.linkage.worker_admission_stub_id} homeAssistantBlocked />);
        expect(await screen.findByText(/Atlas cannot install Home Assistant, so it cannot be queued for installation/i)).toBeInTheDocument();
    });
});
