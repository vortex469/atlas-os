import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listLiveEnqueueAdmissions } from "../../api/liveEnqueueAdmission";
import { expiredLiveEnqueueAdmissionFixture, liveEnqueueAdmissionCollectionFixture } from "../../test/liveEnqueueAdmission";
import { workerIntakeAdmissionFixture } from "../../test/workerIntakeAdmission";
import type { LiveEnqueueAdmissionCollectionV1 } from "../../types/liveEnqueueAdmission";
import { LiveEnqueueAdmissions } from "./LiveEnqueueAdmissions";

vi.mock("../../api/liveEnqueueAdmission", () => ({ listLiveEnqueueAdmissions: vi.fn() }));
vi.mock("./OneShotLiveEnqueues", () => ({ OneShotLiveEnqueues: () => <section aria-label="One-shot live enqueue evidence">Nested one-shot live enqueue evidence</section> }));

const empty: LiveEnqueueAdmissionCollectionV1 = { ...liveEnqueueAdmissionCollectionFixture, items: [], count: 0 };
const props = { candidateId: workerIntakeAdmissionFixture.candidate_record_id, workerIntakeAdmissionId: workerIntakeAdmissionFixture.admission_id, homeAssistantBlocked: false };

describe("LiveEnqueueAdmissions", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue(empty); });

    it("renders checking, empty, and redacted error states with a safe retry", async () => {
        let resolve!: (value: LiveEnqueueAdmissionCollectionV1) => void;
        vi.mocked(listLiveEnqueueAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<LiveEnqueueAdmissions {...props} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved queue handoff review/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue handoff review has been saved/i));
        unmount();

        vi.mocked(listLiveEnqueueAdmissions)
            .mockRejectedValueOnce(new Error("secret /internal/path 10.0.0.1"))
            .mockResolvedValueOnce(empty);
        render(<LiveEnqueueAdmissions {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/private system details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue handoff review has been saved/i));
        expect(listLiveEnqueueAdmissions).toHaveBeenCalledTimes(3);
    });

    it("shows a plain-language review with technical evidence collapsed", async () => {
        vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue(liveEnqueueAdmissionCollectionFixture);
        render(<LiveEnqueueAdmissions {...props} />);
        expect(await screen.findByText("Queue handoff review is current")).toBeInTheDocument();
        expect(screen.getByText(/has not added work to a queue or contacted a worker/i)).toBeInTheDocument();
        expect(screen.getByLabelText("What needs attention")).toHaveTextContent(/Atlas has not set up a way to add work to the queue.*Atlas has not set up a way to remove queued work.*Atlas has not set up a way to start a worker.*Atlas has not set up a safe way to start this installation/i);
        expect(screen.getByText("Technical details")).toBeInTheDocument();
        expect(screen.getByText("enqueue_operation_not_defined")).not.toBeVisible();
        expect(screen.getByLabelText(/one-shot live enqueue evidence/i)).toHaveTextContent(/nested one-shot live enqueue evidence/i);
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText(/Permanent live-enqueue subject reservation: true/i)).toHaveTextContent(/replay bypass allowed: false/i);
        expect(screen.getByText(/Audit facts are server-owned/i)).toHaveTextContent(/correlation fingerprints returned by Core/i);
        expect(screen.getByLabelText(/live enqueue admission fixed-false authority fields/i)).toHaveTextContent(/live enqueue allowedfalse.*queue polling allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("renders expired and Home Assistant blocked states", async () => {
        vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue({ ...liveEnqueueAdmissionCollectionFixture, items: [expiredLiveEnqueueAdmissionFixture], count: 1 });
        render(<LiveEnqueueAdmissions {...props} homeAssistantBlocked />);
        expect(await screen.findByText("Queue handoff review has expired")).toBeInTheDocument();
        expect(screen.getByText(/Home Assistant installation is unsupported and remains blocked/i)).toBeInTheDocument();
    });
});
