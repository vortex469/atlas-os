import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listRunnerBindingPlans } from "../../api/runnerBindingPlan";
import { admissionResultFixture } from "../../test/installationExecutionAdmission";
import { runnerBindingPlanResultFixture } from "../../test/runnerBindingPlan";
import { RunnerBindingPlans } from "./RunnerBindingPlans";

vi.mock("../../api/runnerBindingPlan", () => ({ listRunnerBindingPlans: vi.fn() }));
const empty = { schema: "runner-binding-plan-collection-v1" as const, plans: [], evidence_only: true as const, execution_authorized: false as const, mutation_allowed: false as const };

describe("RunnerBindingPlans", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(listRunnerBindingPlans).mockResolvedValue(empty); });
    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: typeof empty) => void;
        vi.mocked(listRunnerBindingPlans).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/loading runner binding plan evidence/i);
        resolve(empty); await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no runner binding plan evidence/i)); unmount();
        vi.mocked(listRunnerBindingPlans).mockRejectedValue(new Error("token secret /internal/path 10.0.0.1"));
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/error is redacted/i);
        expect(screen.queryByText(/10\.0\.0\.1|internal\/path|token secret/i)).not.toBeInTheDocument();
    });
    it("renders binding-planned lifecycle, linkage, ceilings, blockers, and fixed-false authority", async () => {
        vi.mocked(listRunnerBindingPlans).mockResolvedValue({ ...empty, plans: [runnerBindingPlanResultFixture] });
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByText(/active binding-planned evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/eligibility: binding_planned/i)).toBeInTheDocument();
        expect(screen.getByText(/runner is not bound/i)).toBeInTheDocument();
        expect(screen.getByText("isolated_installation_runner")).toBeInTheDocument();
        expect(screen.getByText("atlas-installation-confined-v1")).toBeInTheDocument();
        expect(screen.getByText("ephemeral_workspace_only")).toBeInTheDocument();
        expect(screen.getByText(/v0.36 execution admission fingerprint/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/runner binding fixed-false authority fields/i)).toHaveTextContent(/runner boundfalse/i);
        expect(screen.getByText(/permanent binding-subject reservation: true/i)).toBeInTheDocument();
    });
    it("renders expired and Home Assistant blocked posture without creation controls", async () => {
        const expired = { ...runnerBindingPlanResultFixture, status: { ...runnerBindingPlanResultFixture.status!, lifecycle: "expired" as const } };
        vi.mocked(listRunnerBindingPlans).mockResolvedValue({ ...empty, plans: [expired] });
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked />);
        expect(await screen.findByText(/expired binding-planned evidence/i)).toBeInTheDocument();
        expect(screen.getByText(/Home Assistant remains blocked, non-installable, non-executable/i)).toBeInTheDocument();
        expect(screen.getByText(/creation is unavailable in this context/i)).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
