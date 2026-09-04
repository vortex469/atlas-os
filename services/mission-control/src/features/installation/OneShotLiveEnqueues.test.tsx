import { render, screen, waitFor } from "@testing-library/react";
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
        expect(screen.getByRole("status")).toHaveTextContent(/loading one-shot live enqueue evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no one-shot live enqueue evidence/i));
        unmount();

        vi.mocked(listOneShotLiveEnqueues).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<OneShotLiveEnqueues {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders only inert reference evidence with fixed-false authority", async () => {
        vi.mocked(listOneShotLiveEnqueues).mockResolvedValue(oneShotLiveEnqueueCollectionFixture);
        render(<OneShotLiveEnqueues {...props} homeAssistantBlocked />);
        expect(await screen.findByText(/recorded one-shot live enqueue evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/inert reference-only item: true; payload constructed: false; payload serialized: false; dequeue defined: false; queue polling allowed: false/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered one-shot live enqueue blockers/i)).toHaveTextContent(/dequeue_not_defined.*queue_polling_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText("Advanced one-shot enqueue evidence")).toBeInTheDocument();
        expect(screen.getByLabelText(/queue observation and enqueue receipt evidence/i)).toHaveTextContent(/nested queue observation evidence/i);
        expect(screen.getByText(/Permanent one-shot subject reservation: true/i)).toHaveTextContent(/replay bypass allowed: false/i);
        expect(screen.getByLabelText(/one-shot live enqueue fixed-false authority fields/i)).toHaveTextContent(/dequeue allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.getByText(/For Home Assistant, one-shot live enqueue remains blocked/i)).toHaveTextContent(/non-installable and non-executable/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
