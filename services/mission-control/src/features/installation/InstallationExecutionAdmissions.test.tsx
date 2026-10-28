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
        expect(screen.getByRole("status")).toHaveTextContent(/loading saved runner review records/i);
        resolve(empty);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no runner review records saved yet/i));
        unmount();
        vi.mocked(listInstallationExecutionAdmissions).mockRejectedValue(new Error("secret token /internal/path 10.0.0.1"));
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[]} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable or could not be saved/i);
        expect(document.body).not.toHaveTextContent(/secret token|10\.0\.0\.1/i);
    });

    it("leads with a plain outcome and blockers, with technical identity and authority in disclosures", async () => {
        vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue({ ...empty, admissions: [admissionResultFixture] });
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);
        expect(await screen.findByRole("heading", { name: "Saved for later review" })).toBeInTheDocument();
        expect(screen.getByText("This record does not choose or contact a runner, authorize installation, or start work.")).toBeInTheDocument();
        const blockers = screen.getByRole("list", { name: "What still needs to be in place" });
        expect(within(blockers).getAllByRole("listitem")[0]).toHaveTextContent("No runner is selected");
        expect(within(blockers).getAllByRole("listitem")[1]).toHaveTextContent("A safe way to start installation is not defined");
        expect(screen.getByText("Permission record ID")).not.toBeVisible();
        screen.getAllByText("a".repeat(64)).forEach((node) => expect(node).not.toBeVisible());
        fireEvent.click(screen.getByText("Record identity and technical status"));
        expect(screen.getByText("Permission record ID").nextSibling).toHaveTextContent(uuid4);
        expect(screen.getByText("Evidence chain fingerprint").nextSibling).toHaveTextContent("a".repeat(64));
        fireEvent.click(screen.getByText("Audit and authority details"));
        expect(screen.getByText(/Idempotency and permission-record use are reserved permanently/i)).toBeInTheDocument();
        const flags = screen.getByLabelText("Admission fixed-false authority fields");
        expect(within(flags).getByText("Runner binding allowed").nextSibling).toHaveTextContent("false");
        expect(within(flags).getByText("Execution start allowed").nextSibling).toHaveTextContent("false");
    });

    it("uses two-step evidence-only creation through the exact API", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.admission.record"] }, csrfToken: "csrf" };
        vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue({ ...empty, admissions: [admissionResultFixture] });
        vi.mocked(createInstallationExecutionAdmission).mockResolvedValue(admissionResultFixture);
        render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={false} />);
        await screen.findByRole("heading", { name: "Saved for later review" });
        fireEvent.click(screen.getByRole("button", { name: "Review runner review record" }));
        expect(screen.getByLabelText("Admission evidence confirmation")).toHaveTextContent(/records your request for an installation runner to be considered later.*it does not choose or contact a runner, authorize installation, or start work/i);
        fireEvent.click(screen.getByRole("button", { name: "Save for later review" }));
        await waitFor(() => expect(createInstallationExecutionAdmission).toHaveBeenCalled());
        expect(createInstallationExecutionAdmission).toHaveBeenCalledWith(uuid4, expect.objectContaining({ permission_grant_id: uuid4, requested_scope: "future_installation_runner_consideration_only", execution_authorized: false, mutation_allowed: false, replay_allowed: false }), "csrf", "stable-admission-key");
        expect(screen.getByRole("list", { name: "Runner review records" }).children).toHaveLength(1);
    });

    it("keeps Home Assistant and expired grants blocked with no creation control", async () => {
        const expired = { ...grantResultFixture, status: { ...grantResultFixture.status!, lifecycle: "expired" as const } };
        const { rerender } = render(<InstallationExecutionAdmissions candidateId={uuid4} grants={[expired]} homeAssistantBlocked={false} />);
        await screen.findByText(/saving is unavailable/i);
        expect(screen.queryByRole("button", { name: /admission evidence/i })).not.toBeInTheDocument();
        rerender(<InstallationExecutionAdmissions candidateId={uuid4} grants={[grantResultFixture]} homeAssistantBlocked={true} />);
        expect(screen.getByText(/Atlas cannot install Home Assistant/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /admission evidence/i })).not.toBeInTheDocument();
    });
});
