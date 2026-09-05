import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listOneShotDequeueWorkerBindings } from "../../api/oneShotDequeueWorkerBinding";
import { oneShotControlledDequeueFixture } from "../../test/oneShotControlledDequeue";
import { oneShotDequeueWorkerBindingCollectionFixture } from "../../test/oneShotDequeueWorkerBinding";
import type { OneShotDequeueWorkerBindingCollectionV1 } from "../../types/oneShotDequeueWorkerBinding";
import { OneShotDequeueWorkerBindings } from "./OneShotDequeueWorkerBindings";

vi.mock("../../api/oneShotDequeueWorkerBinding", () => ({ listOneShotDequeueWorkerBindings: vi.fn() }));

const empty: OneShotDequeueWorkerBindingCollectionV1 = { ...oneShotDequeueWorkerBindingCollectionFixture, items: [], count: 0 };

describe("OneShotDequeueWorkerBindings", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listOneShotDequeueWorkerBindings).mockResolvedValue(empty); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: OneShotDequeueWorkerBindingCollectionV1) => void;
        vi.mocked(listOneShotDequeueWorkerBindings).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<OneShotDequeueWorkerBindings candidateId={oneShotControlledDequeueFixture.candidate_record_id} dequeueId={oneShotControlledDequeueFixture.dequeue_id} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading one-shot dequeue worker binding evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no one-shot dequeue worker binding evidence/i));
        unmount();

        vi.mocked(listOneShotDequeueWorkerBindings).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<OneShotDequeueWorkerBindings candidateId={oneShotControlledDequeueFixture.candidate_record_id} dequeueId={oneShotControlledDequeueFixture.dequeue_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("renders simple eligible, bound, and blocked state with technical evidence under Advanced details", async () => {
        vi.mocked(listOneShotDequeueWorkerBindings).mockResolvedValue(oneShotDequeueWorkerBindingCollectionFixture);
        render(<OneShotDequeueWorkerBindings candidateId={oneShotControlledDequeueFixture.candidate_record_id} dequeueId={oneShotControlledDequeueFixture.dequeue_id} />);
        expect(await screen.findByText(/recorded one-shot dequeue worker binding evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/state: eligible; bound: readiness gated; blocked: yes/i)).toHaveTextContent(/store contacted: false; runtime contacted: false; worker started: false; execution started: false/i);
        const advanced = screen.getByText("Advanced details").closest("details");
        expect(advanced).toBeInTheDocument();
        expect(advanced).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/ordered one-shot dequeue worker binding blockers/i)).toHaveTextContent(/store_contact_not_defined.*runtime_contact_not_defined.*worker_start_not_defined.*execution_start_boundary_not_defined/i);
        expect(screen.getByText(/inherited sandbox, resource, network, and filesystem limits/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/one-shot dequeue worker binding fixed-false authority fields/i)).toHaveTextContent(/worker start allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
