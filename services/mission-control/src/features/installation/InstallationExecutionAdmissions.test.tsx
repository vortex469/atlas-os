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
        expect(screen.getByRole("status")).toHaveTextContent(/loading installation execution admission evidence/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no installation execution admission evidence/i));
        unmount();
        vi.mocked(listInstallationExecutionAdmissions).mockRejectedValue(new Error("secret token /internal/path 10.0.0.1"));
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[]} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/could not be recorded/i);
        expect(document.body).not.toHaveTextContent(/secret token|10\.0\.0\.1/i);
    });

    it("renders admission-gated lifecycle, blockers, full linkage, and false authority", async () => {
        vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue({ ...empty, admissions: [admissionResultFixture] });
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("heading", { name: "Active admission-gated evidence" })).toBeInTheDocument();
        expect(screen.getByText(/readiness: admission_gated; lifecycle: active/i)).toBeInTheDocument();
        const blockers = screen.getByRole("list", { name: "Ordered admission blockers" });
        expect(within(blockers).getAllByRole("listitem")[0]).toHaveTextContent("Runner binding is not defined");
        expect(within(blockers).getAllByRole("listitem")[1]).toHaveTextContent("Execution start boundary is not defined");
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
        await screen.findByText(/no installation execution admission evidence/i);
        fireEvent.click(screen.getByRole("button", { name: "Review admission evidence statement" }));
        expect(screen.getByLabelText("Admission evidence confirmation")).toHaveTextContent(/records admission evidence only.*does not select or invoke a runner.*does not install or execute anything/i);
        fireEvent.click(screen.getByRole("button", { name: "Record admission evidence" }));
        await waitFor(() => expect(createInstallationExecutionAdmission).toHaveBeenCalled());
        expect(createInstallationExecutionAdmission).toHaveBeenCalledWith(uuid4, expect.objectContaining({ permission_grant_id: uuid4, requested_scope: "future_installation_runner_consideration_only", execution_authorized: false, mutation_allowed: false, replay_allowed: false }), "csrf", "stable-admission-key");
    });

    it("keeps Home Assistant and expired grants blocked with no creation control", async () => {
        const expired = { ...grantResultFixture, status: { ...grantResultFixture.status!, lifecycle: "expired" as const } };
        const { rerender } = render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[expired]} homeAssistantBlocked={false} />);
        await screen.findByText(/creation remains blocked/i);
        expect(screen.queryByRole("button", { name: /admission evidence/i })).not.toBeInTheDocument();
        rerender(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={true} />);
        expect(screen.getByText(/Home Assistant remains blocked, non-installable, and non-executable/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /admission evidence/i })).not.toBeInTheDocument();
    });
});
