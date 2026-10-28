import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved runner plans/i);
        resolve(empty); await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no runner plan is saved/i)); unmount();
        vi.mocked(listRunnerBindingPlans).mockRejectedValue(new Error("token secret /internal/path 10.0.0.1"));
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/technical error details are hidden/i);
        expect(screen.queryByText(/10\.0\.0\.1|internal\/path|token secret/i)).not.toBeInTheDocument();
    });
    it("leads with the saved plan and safety limits, with exact technical values in disclosures", async () => {
        vi.mocked(listRunnerBindingPlans).mockResolvedValue({ ...empty, plans: [runnerBindingPlanResultFixture] });
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("heading", { name: "Saved runner plan" })).toBeInTheDocument();
        expect(screen.getByText(/This plan does not register, contact, reserve, or bind a runner/i)).toBeInTheDocument();
        expect(screen.getByText(/No runner is bound to this plan/i)).toBeInTheDocument();
        expect(screen.getByText(/A safe way to start installation is not defined/i)).toBeInTheDocument();
        expect(screen.getByLabelText("Planned safety limits")).toHaveTextContent(/no network access.*no access to host, repository, or guest files/i);
        expect(screen.getByLabelText("Planned safety limits")).toHaveTextContent(/1 CPU core, 512 MiB memory, 64 processes, 15 minutes, 1 MiB output, and 256 MiB temporary workspace/i);
        expect(screen.getByText("Sandbox profile")).not.toBeVisible();
        expect(screen.getByText("Runner kind code")).not.toBeVisible();
        fireEvent.click(screen.getByText("Exact sandbox and resource limits"));
        expect(screen.getByText("isolated_installation_runner")).toBeInTheDocument();
        expect(screen.getByText("atlas-installation-confined-v1")).toBeInTheDocument();
        expect(screen.getByText("ephemeral_workspace_only")).toBeInTheDocument();
        fireEvent.click(screen.getByText("Plan identity and linked evidence"));
        expect(screen.getByText(/Execution admission fingerprint/i)).toBeInTheDocument();
        expect(screen.getByLabelText("Runner binding fixed-false authority fields")).not.toBeVisible();
        fireEvent.click(screen.getByText("Audit and authority details"));
        expect(screen.getByLabelText(/runner binding fixed-false authority fields/i)).toHaveTextContent(/runner boundfalse/i);
        expect(screen.getByText(/Binding and idempotency use are reserved permanently/i)).toBeInTheDocument();
    });
    it("renders expired and Home Assistant blocked posture without creation controls", async () => {
        const expired = { ...runnerBindingPlanResultFixture, status: { ...runnerBindingPlanResultFixture.status!, lifecycle: "expired" as const } };
        vi.mocked(listRunnerBindingPlans).mockResolvedValue({ ...empty, plans: [expired] });
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked />);
        expect(await screen.findByRole("heading", { name: "Expired runner plan" })).toBeInTheDocument();
        expect(screen.getByText(/Atlas cannot install Home Assistant/i)).toBeInTheDocument();
        expect(screen.getByText(/No runner is available to bind from this review/i)).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
