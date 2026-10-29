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
};

describe("OneShotLiveEnqueues", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listOneShotLiveEnqueues).mockResolvedValue(empty); });

    it("renders checking, empty, and redacted error states with a safe retry", async () => {
        let resolve!: (value: OneShotLiveEnqueueCollectionV1) => void;
        vi.mocked(listOneShotLiveEnqueues).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<OneShotLiveEnqueues {...props} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved queue item record/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue item record has been saved/i));
        unmount();

        vi.mocked(listOneShotLiveEnqueues)
            .mockRejectedValueOnce(new Error("secret /internal/path 10.0.0.1"))
            .mockResolvedValueOnce(empty);
        render(<OneShotLiveEnqueues {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/private system details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue item record has been saved/i));
        expect(listOneShotLiveEnqueues).toHaveBeenCalledTimes(3);
    });

    it("shows a plain queue item summary and keeps technical evidence collapsed", async () => {
        vi.mocked(listOneShotLiveEnqueues).mockResolvedValue(oneShotLiveEnqueueCollectionFixture);
        render(<OneShotLiveEnqueues {...props} />);
        expect(await screen.findByText("Queue item record is current")).toBeInTheDocument();
        expect(screen.getByText(/This reference has no payload and has not contacted a worker/i)).toBeInTheDocument();
        expect(screen.getByLabelText("What needs attention")).toHaveTextContent(/Atlas has not set up a way to remove queued work.*Atlas has not set up a way to read work from a queue.*Atlas has not set up a way to start a worker.*Atlas has not set up a safe way to start this installation/i);
        expect(screen.getByText("Technical details")).toBeInTheDocument();
        expect(screen.getByText("dequeue_not_defined")).not.toBeVisible();
        expect(screen.getByLabelText(/queue observation and enqueue receipt evidence/i)).toHaveTextContent(/nested queue observation evidence/i);
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText(/Permanent one-shot subject reservation: true/i)).toHaveTextContent(/replay bypass allowed: false/i);
        expect(screen.getByLabelText(/one-shot live enqueue fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByText(/Home Assistant installation/i)).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
