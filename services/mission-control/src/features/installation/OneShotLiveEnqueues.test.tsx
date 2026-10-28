import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listOneShotLiveEnqueues } from "../../api/oneShotLiveEnqueue";
import { oneShotLiveEnqueueCollectionFixture } from "../../test/oneShotLiveEnqueue";
import type { OneShotLiveEnqueueCollectionV1 } from "../../types/oneShotLiveEnqueue";
import { OneShotLiveEnqueues } from "./OneShotLiveEnqueues";

vi.mock("../../api/oneShotLiveEnqueue", () => ({ listOneShotLiveEnqueues: vi.fn() }));
vi.mock("./QueueObservationEvidence", () => ({ QueueObservationEvidence: () => <section aria-label="Queue observation and enqueue receipt evidence">Nested queue observation evidence</section> }));

const empty: OneShotLiveEnqueueCollectionV1 = { ...oneShotLiveEnqueueCollectionFixture, items: [], count: 0 };
const props = {
    candidateId: oneShotLiveEnqueueCollectionFixture.candidate_record_id,
    liveEnqueueAdmissionId: oneShotLiveEnqueueCollectionFixture.items[0].lineage.live_enqueue_admission_id,
    homeAssistantBlocked: false,
};

describe("OneShotLiveEnqueues", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listOneShotLiveEnqueues).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: OneShotLiveEnqueueCollectionV1) => void;
        vi.mocked(listOneShotLiveEnqueues).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<OneShotLiveEnqueues {...props} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved queue references/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue reference is saved/i));
        unmount();

        vi.mocked(listOneShotLiveEnqueues).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<OneShotLiveEnqueues {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("summarizes the inert queue reference and keeps technical evidence in closed details", async () => {
        vi.mocked(listOneShotLiveEnqueues).mockResolvedValue(oneShotLiveEnqueueCollectionFixture);
        render(<OneShotLiveEnqueues {...props} homeAssistantBlocked />);
        expect(await screen.findByRole("heading", { name: "Saved queue reference" })).toBeInTheDocument();
        expect(screen.getByText(/Core saved a reference for a possible queue item/i)).toBeInTheDocument();
        expect(screen.getByText(/only a reference for a possible queue item/i)).toBeInTheDocument();
        expect(screen.getByLabelText("Why this queue reference cannot run")).toHaveTextContent(/safe way to take work from a queue.*safe way to check a queue.*safe way to start a worker.*safe way to start installation/i);
        expect(screen.getByLabelText("Safety limits recorded for a future worker")).toHaveTextContent(/No network access.*No access to host, repository, or guest files.*No elevated privileges.*1 CPU core.*512 MiB memory.*64 processes.*15 minutes.*1 MiB output.*256 MiB temporary workspace/i);
        const details = screen.getByText("Queue item and earlier reviews").closest("details");
        expect(details).not.toHaveAttribute("open");
        for (const element of screen.getAllByText(oneShotLiveEnqueueCollectionFixture.items[0].enqueue_id)) expect(element).not.toBeVisible();
        expect(screen.queryByText("dequeue_not_defined")).not.toBeInTheDocument();
        expect(screen.getByLabelText(/queue observation and enqueue receipt evidence/i)).toHaveTextContent(/nested queue observation evidence/i);
        expect(screen.getByLabelText(/one-shot live enqueue fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.getByText("Exact safety limits and record details").closest("details")).not.toHaveAttribute("open");
        fireEvent.click(screen.getByText("Queue item and earlier reviews"));
        expect(details).toHaveAttribute("open");
        expect(screen.getByText(/Atlas cannot install Home Assistant/i)).toHaveTextContent(/cannot be prepared for a worker/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
