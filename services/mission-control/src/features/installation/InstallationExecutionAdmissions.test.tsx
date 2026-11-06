import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createInstallationExecutionAdmission, listInstallationExecutionAdmissions } from "../../api/installationExecutionAdmission";
import { listRunnerBindingPlans } from "../../api/runnerBindingPlan";
import { grantResultFixture } from "../../test/executionPermissionGrant";
import { admissionResultFixture } from "../../test/installationExecutionAdmission";
import { uuid4 } from "../../test/installationReadinessReview";
import type { InstallationExecutionAdmissionCollectionV1 } from "../../types/installationExecutionAdmission";
import { InstallationExecutionAdmissions } from "./InstallationExecutionAdmissions";

const session = vi.hoisted(() => ({ value: { authenticated: false, principal: null as { operator_id: string; permissions: string[] } | null, csrfToken: null as string | null } }));
vi.mock("../../hooks/operatorSessionContext", () => ({ useOperatorSession: () => session.value }));
vi.mock("../../api/installationExecutionAdmission", async (original) => {
    const module = await original<typeof import("../../api/installationExecutionAdmission")>();
    return { ...module, listInstallationExecutionAdmissions: vi.fn(), createInstallationExecutionAdmission: vi.fn(), installationExecutionAdmissionIdempotencyKey: () => "stable-admission-key" };
});
vi.mock("../../api/runnerBindingPlan", () => ({ listRunnerBindingPlans: vi.fn() }));

const empty: InstallationExecutionAdmissionCollectionV1 = { admissions: [], evidence_only: true, execution_start_allowed: false, runner_binding_allowed: false, execution_authorized: false, installation_allowed: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false };

describe("InstallationExecutionAdmissions", () => {
    beforeEach(() => { vi.resetAllMocks(); session.value = { authenticated: false, principal: null, csrfToken: null }; vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue(empty); vi.mocked(listRunnerBindingPlans).mockResolvedValue({ schema: "runner-binding-plan-collection-v1", plans: [], evidence_only: true, execution_authorized: false, mutation_allowed: false }); });

    it("renders loading, empty, and redacted error states", async () => {
        let resolve!: (value: typeof empty) => void;
        vi.mocked(listInstallationExecutionAdmissions).mockReturnValue(new Promise((done) => { resolve = done; }));
        const { unmount } = render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[]} homeAssistantBlocked={false} />);
        expect(screen.getByRole("status")).toHaveTextContent(/checking for saved run review records/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no run review record has been saved/i));
        unmount();
        vi.mocked(listInstallationExecutionAdmissions).mockRejectedValue(new Error("secret token /internal/path 10.0.0.1"));
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[]} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas could not load the run review record. Retry to check its current status.");
        expect(document.body).not.toHaveTextContent(/secret token|10\.0\.0\.1/i);
        vi.mocked(listInstallationExecutionAdmissions).mockResolvedValueOnce(empty);
        fireEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(await screen.findByText("No run review record has been saved.")).toBeInTheDocument();
        expect(listInstallationExecutionAdmissions).toHaveBeenCalledTimes(3);
        expect(createInstallationExecutionAdmission).not.toHaveBeenCalled();
    });

    it("renders admission-gated lifecycle, blockers, full linkage, and false authority", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.admission.record"] }, csrfToken: "csrf" };
        vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue({ ...empty, admissions: [admissionResultFixture] });
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("heading", { name: "Run review record is current" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review run statement" })).not.toBeInTheDocument();
        const explanation = screen.getByText("How this record works").closest("details");
        expect(explanation).not.toHaveAttribute("open");
        fireEvent.click(screen.getByText("How this record works"));
        expect(explanation).toHaveTextContent("This record is evidence only. It does not connect a machine, start work, or allow system changes.");
        expect(explanation).toHaveTextContent("It is tied to this operator and the exact earlier reviews and confirmation. If it expires, it cannot be renewed or reused.");
        expect(screen.getByText("Technical details").closest("details")).not.toHaveAttribute("open");
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText(/readiness: admission_gated; lifecycle: active/i)).toBeVisible();
        const blockers = screen.getByRole("list", { name: "What needs attention" });
        expect(within(blockers).getAllByRole("listitem")[0]).toHaveTextContent("No machine is set up to run this installation yet.");
        expect(within(blockers).getAllByRole("listitem")[1]).toHaveTextContent("Atlas has not set up a safe way to start this installation yet.");
        expect(screen.getByText("v0.35 permission grant ID").nextSibling).toHaveTextContent(uuid4);
        expect(screen.getByText("v0.20–v0.35 chain fingerprint").nextSibling).toHaveTextContent("a".repeat(64));
        expect(screen.getByText(/permanent idempotency reservation: true/i)).toHaveTextContent(/raw idempotency key persisted: false.*replay allowed: false/i);
        const flags = screen.getByLabelText("Admission fixed-false authority fields");
        expect(within(flags).getByText("Runner binding allowed").nextSibling).toHaveTextContent("false");
        expect(within(flags).getByText("Execution start allowed").nextSibling).toHaveTextContent("false");
    });

    it("uses two-step evidence-only creation through the exact API", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.admission.record"] }, csrfToken: "csrf" };
        vi.mocked(createInstallationExecutionAdmission).mockResolvedValue(admissionResultFixture);
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);
        expect(screen.queryByRole("button", { name: "Review run statement" })).not.toBeInTheDocument();
        await screen.findByText(/no run review record has been saved/i);
        expect(await screen.findByRole("button", { name: "Review run statement" })).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Review run statement" }));
        expect(screen.getByLabelText("Run review confirmation")).toHaveTextContent(/saves the review only.*does not choose a machine or allow an installation to start/i);
        fireEvent.click(screen.getByRole("button", { name: "Save review record" }));
        await waitFor(() => expect(createInstallationExecutionAdmission).toHaveBeenCalled());
        await waitFor(() => expect(screen.queryByRole("button", { name: "Review run statement" })).not.toBeInTheDocument());
        expect(createInstallationExecutionAdmission).toHaveBeenCalledWith(uuid4, expect.objectContaining({ permission_grant_id: uuid4, requested_scope: "future_installation_runner_consideration_only", execution_authorized: false, mutation_allowed: false, replay_allowed: false }), "csrf", "stable-admission-key");
    });

    it("withholds run review controls when the signed-in session has no CSRF token", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.admission.record"] }, csrfToken: null };
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);

        expect(await screen.findByText(/current confirmation and an operator account with permission are needed/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review run statement" })).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Run review confirmation")).not.toBeInTheDocument();
        expect(createInstallationExecutionAdmission).not.toHaveBeenCalled();
    });

    it("reports a failed record without retaining the empty state", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.admission.record"] }, csrfToken: "csrf" };
        vi.mocked(createInstallationExecutionAdmission).mockRejectedValue(new Error("private response"));
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);
        await screen.findByText(/no run review record has been saved/i);
        fireEvent.click(screen.getByRole("button", { name: "Review run statement" }));
        fireEvent.click(screen.getByRole("button", { name: "Save review record" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas could not save the run review record.");
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Review run statement" })).not.toBeInTheDocument();
    });

    it("keeps Home Assistant and expired grants blocked with no creation control", async () => {
        const expired = { ...grantResultFixture, status: { ...grantResultFixture.status!, lifecycle: "expired" as const } };
        const { rerender } = render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[expired]} homeAssistantBlocked={false} />);
        await screen.findByText(/current confirmation and an operator account with permission are needed/i);
        expect(screen.queryByRole("button", { name: /run statement/i })).not.toBeInTheDocument();
        rerender(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={true} />);
        expect(screen.getByText("Atlas cannot install or run Home Assistant yet.")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /run statement/i })).not.toBeInTheDocument();
    });
});
