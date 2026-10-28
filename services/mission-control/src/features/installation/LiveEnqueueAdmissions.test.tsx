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

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: LiveEnqueueAdmissionCollectionV1) => void;
        vi.mocked(listLiveEnqueueAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<LiveEnqueueAdmissions {...props} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved queue handoff reviews/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no queue handoff review is saved/i));
        unmount();

        vi.mocked(listLiveEnqueueAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<LiveEnqueueAdmissions {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("summarizes the saved review and keeps technical evidence in closed details", async () => {
        vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue(liveEnqueueAdmissionCollectionFixture);
        render(<LiveEnqueueAdmissions {...props} />);
        expect(await screen.findByRole("heading", { name: "Saved queue handoff review" })).toBeInTheDocument();
        expect(screen.getByText(/does not mean work can be added to a queue/i)).toBeInTheDocument();
        expect(screen.getByLabelText("Why work cannot be added")).toHaveTextContent(/safe way to add work to a queue.*safe way to take work from a queue.*safe way to start a worker.*safe way to start installation/i);
        expect(screen.getByLabelText("Safety limits recorded for a future worker")).toHaveTextContent(/No network access.*No access to host, repository, or guest files.*No elevated privileges.*1 CPU core.*512 MiB memory.*64 processes.*15 minutes.*1 MiB output.*256 MiB temporary workspace/i);
        const details = screen.getByText("Queue and worker details").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(liveEnqueueAdmissionCollectionFixture.items[0].admission_id)).not.toBeVisible();
        expect(screen.getByLabelText(/one-shot live enqueue evidence/i)).toHaveTextContent(/nested one-shot live enqueue evidence/i);
        expect(screen.getByLabelText(/live enqueue admission fixed-false authority fields/i)).toHaveTextContent(/live enqueue allowedfalse.*queue polling allowedfalse.*process execution allowedfalse/i);
        expect(screen.getByText("Exact safety limits and saved evidence").closest("details")).not.toHaveAttribute("open");
        fireEvent.click(screen.getByText("Queue and worker details"));
        expect(details).toHaveAttribute("open");
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("renders expired and Home Assistant blocked states", async () => {
        vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue({ ...liveEnqueueAdmissionCollectionFixture, items: [expiredLiveEnqueueAdmissionFixture], count: 1 });
        render(<LiveEnqueueAdmissions {...props} homeAssistantBlocked />);
        expect(await screen.findByRole("heading", { name: "Expired queue handoff review" })).toBeInTheDocument();
        expect(screen.getByText(/Atlas cannot install Home Assistant/i)).toHaveTextContent(/cannot be prepared for a worker/i);
    });
});
