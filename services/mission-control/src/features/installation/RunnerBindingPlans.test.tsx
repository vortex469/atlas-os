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
        expect(screen.getByRole("status")).toHaveTextContent(/checking for a saved machine setup plan/i);
        resolve(empty); await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no machine setup plan has been saved/i)); unmount();
        vi.mocked(listRunnerBindingPlans).mockRejectedValue(new Error("token secret /internal/path 10.0.0.1"));
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/could not load the machine setup plan.*retry to check its current status/i);
        expect(screen.queryByText(/10\.0\.0\.1|internal\/path|token secret/i)).not.toBeInTheDocument();
        vi.mocked(listRunnerBindingPlans).mockResolvedValueOnce(empty);
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(await screen.findByText("No machine setup plan has been saved. Atlas cannot start an installation.")).toBeInTheDocument();
        expect(listRunnerBindingPlans).toHaveBeenCalledTimes(3);
    });
    it("renders binding-planned lifecycle, linkage, ceilings, blockers, and fixed-false authority", async () => {
        vi.mocked(listRunnerBindingPlans).mockResolvedValue({ ...empty, plans: [runnerBindingPlanResultFixture] });
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked={false} />);
        expect(await screen.findByText("Machine setup plan is current")).toBeInTheDocument();
        expect(screen.getByText("No machine is connected to this plan.")).toBeInTheDocument();
        const technical = screen.getByText("Technical details").closest("details");
        expect(technical).not.toHaveAttribute("open");
        expect(screen.getByText("isolated_installation_runner")).not.toBeVisible();
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText(/plan status: binding_planned/i)).toBeVisible();
        expect(screen.getByText("isolated_installation_runner")).toBeInTheDocument();
        expect(screen.getByText("atlas-installation-confined-v1")).toBeInTheDocument();
        expect(screen.getByText("ephemeral_workspace_only")).not.toBeVisible();
        fireEvent.click(screen.getByText("Sandbox and resource limits"));
        expect(screen.getByText("ephemeral_workspace_only")).toBeVisible();
        fireEvent.click(screen.getByText("Related review records"));
        expect(screen.getByText(/v0.36 execution admission fingerprint/i)).toBeVisible();
        fireEvent.click(screen.getByText("Authority flags"));
        expect(screen.getByLabelText(/runner binding fixed-false authority fields/i)).toHaveTextContent(/runner boundfalse/i);
        expect(screen.getByText(/this record cannot be retried or replayed/i)).toBeInTheDocument();
    });
    it("renders expired and Home Assistant blocked posture without creation controls", async () => {
        const expired = { ...runnerBindingPlanResultFixture, status: { ...runnerBindingPlanResultFixture.status!, lifecycle: "expired" as const } };
        vi.mocked(listRunnerBindingPlans).mockResolvedValue({ ...empty, plans: [expired] });
        render(<RunnerBindingPlans candidateId="candidate" admission={admissionResultFixture} homeAssistantBlocked />);
        expect(await screen.findByText("Machine setup plan has expired")).toBeInTheDocument();
        expect(screen.getByText("Atlas cannot install or run Home Assistant yet.")).toBeInTheDocument();
        expect(screen.getByText(/Atlas has no eligible machine to reference here/i)).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});
