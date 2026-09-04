import { render, screen, waitFor } from "@testing-library/react";
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
        expect(screen.getByRole("status")).toHaveTextContent(/loading live enqueue admission evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no live enqueue admission evidence/i));
        unmount();

        vi.mocked(listLiveEnqueueAdmissions).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<LiveEnqueueAdmissions {...props} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders recorded evidence, blockers, linkage, inherited ceilings, audit posture, and fixed-false authority", async () => {
        vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue(liveEnqueueAdmissionCollectionFixture);
        render(<LiveEnqueueAdmissions {...props} />);
        expect(await screen.findByText(/recorded live enqueue admission evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/queue item constructed: false; payload constructed: false; payload serialized: false; request sent: false; queue enqueued: false/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/ordered live enqueue admission blockers/i)).toHaveTextContent(/enqueue_operation_not_defined.*dequeue_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText("Advanced live enqueue evidence")).toBeInTheDocument();
        expect(screen.getByLabelText(/one-shot live enqueue evidence/i)).toHaveTextContent(/nested one-shot live enqueue evidence/i);
        expect(screen.getByText(/Permanent live-enqueue subject reservation: true/i)).toHaveTextContent(/replay bypass allowed: false/i);
        expect(screen.getByText(/Audit facts are server-owned/i)).toHaveTextContent(/correlation fingerprints returned by Core/i);
        expect(screen.getByLabelText(/live enqueue admission fixed-false authority fields/i)).toHaveTextContent(/live enqueue allowedfalse.*queue polling allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("renders expired and Home Assistant blocked states", async () => {
        vi.mocked(listLiveEnqueueAdmissions).mockResolvedValue({ ...liveEnqueueAdmissionCollectionFixture, items: [expiredLiveEnqueueAdmissionFixture], count: 1 });
        render(<LiveEnqueueAdmissions {...props} homeAssistantBlocked />);
        expect(await screen.findByText(/expired live enqueue admission evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/For Home Assistant, live enqueue admission remains blocked/i)).toHaveTextContent(/non-installable and non-executable/i);
    });
});
