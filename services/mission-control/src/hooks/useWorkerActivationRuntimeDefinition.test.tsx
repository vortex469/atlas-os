import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getWorkerActivationRuntimeDefinition, listWorkerActivationRuntimeDefinitions } from "../api/workerActivationRuntimeDefinition";
import { useWorkerActivationRuntimeDefinition } from "./useWorkerActivationRuntimeDefinition";

vi.mock("../api/workerActivationRuntimeDefinition", () => ({
    getWorkerActivationRuntimeDefinition: vi.fn(),
    listWorkerActivationRuntimeDefinitions: vi.fn(),
}));

function Reader({ candidateId = "candidate", operatorId = "operator" }: { candidateId?: string; operatorId?: string }) {
    const state = useWorkerActivationRuntimeDefinition(candidateId, operatorId);
    return <output>{typeof state === "string" ? state : state.length}</output>;
}

describe("useWorkerActivationRuntimeDefinition", () => {
    beforeEach(() => vi.resetAllMocks());

    it("loads definitions and does not reread on an equivalent parent render", async () => {
        vi.mocked(listWorkerActivationRuntimeDefinitions).mockResolvedValue(["definition"]);
        vi.mocked(getWorkerActivationRuntimeDefinition).mockResolvedValue({} as never);
        const { rerender } = render(<Reader />);
        expect(screen.getByText("loading")).toBeVisible();
        await screen.findByText("1");
        rerender(<Reader />);
        await act(async () => { await Promise.resolve(); });
        expect(listWorkerActivationRuntimeDefinitions).toHaveBeenCalledTimes(1);
        expect(getWorkerActivationRuntimeDefinition).toHaveBeenCalledTimes(1);
    });

    it("shows loading for a new scope and ignores an obsolete failure", async () => {
        let rejectOld!: (reason: Error) => void;
        vi.mocked(listWorkerActivationRuntimeDefinitions)
            .mockReturnValueOnce(new Promise((_resolve, reject) => { rejectOld = reject; }))
            .mockResolvedValueOnce([]);
        const { rerender } = render(<Reader candidateId="old" />);
        rerender(<Reader candidateId="new" />);
        expect(screen.getByText("loading")).toBeVisible();
        await screen.findByText("missing");
        await act(async () => rejectOld(new Error("obsolete")));
        expect(screen.getByText("missing")).toBeVisible();
    });
});
