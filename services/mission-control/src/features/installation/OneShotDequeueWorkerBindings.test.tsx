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
        expect(screen.getByRole("status")).toHaveTextContent(/loading worker readiness reviews/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no worker readiness review is saved/i));
        unmount();

        vi.mocked(listOneShotDequeueWorkerBindings).mockRejectedValue(new Error("secret /internal/path 10.0.0.1"));
        render(<OneShotDequeueWorkerBindings candidateId={oneShotControlledDequeueFixture.candidate_record_id} dequeueId={oneShotControlledDequeueFixture.dequeue_id} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|secret \/internal/i)).not.toBeInTheDocument();
    });

    it("summarizes why a worker cannot start and keeps technical evidence in closed details", async () => {
        vi.mocked(listOneShotDequeueWorkerBindings).mockResolvedValue(oneShotDequeueWorkerBindingCollectionFixture);
        render(<OneShotDequeueWorkerBindings candidateId={oneShotControlledDequeueFixture.candidate_record_id} dequeueId={oneShotControlledDequeueFixture.dequeue_id} />);
        expect(await screen.findByRole("heading", { name: "Worker readiness review saved" })).toBeInTheDocument();
        expect(screen.getAllByText(/does not contact a store or runtime or start a worker/i)).toHaveLength(2);
        expect(screen.getByLabelText("Why a worker cannot start")).toHaveTextContent(/safe way to contact the store.*safe way to contact the runtime.*safe way to start a worker.*safe way to start installation/i);
        expect(screen.getByLabelText("Limits recorded for a future worker")).toHaveTextContent(/No network access.*No access to host, repository, or guest files.*No elevated privileges.*1 CPU core.*512 MiB memory.*64 processes.*15 minutes.*1 MiB output.*256 MiB temporary workspace/i);
        const details = screen.getByText("Worker and queue details").closest("details");
        expect(details).toBeInTheDocument();
        expect(details).not.toHaveAttribute("open");
        for (const element of screen.getAllByText(oneShotDequeueWorkerBindingCollectionFixture.items[0].binding_id)) expect(element).not.toBeVisible();
        expect(screen.getByText("Exact safety and authority details").closest("details")).not.toHaveAttribute("open");
        expect(screen.getByLabelText(/one-shot dequeue worker binding fixed-false authority fields/i)).toHaveTextContent(/worker start allowedfalse.*agent invocation allowedfalse.*process execution allowedfalse/i);
        expect(screen.queryByText("store_contact_not_defined")).not.toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
