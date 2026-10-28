import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import { StrictMode } from "react";
import type { InstallationReadinessReviewResponseV1 } from "../types/installationReadinessReview";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getInstallationReadinessReview } from "../api/installationReadinessReview";
import { createExecutionPermissionGrant, listExecutionPermissionGrants } from "../api/executionPermissionGrant";
import { listInstallationExecutionAdmissions } from "../api/installationExecutionAdmission";
import { listRunnerBindingPlans } from "../api/runnerBindingPlan";
import { grantResultFixture } from "../test/executionPermissionGrant";
import { blockedFixture, readinessGatedFixture, uuid4 } from "../test/installationReadinessReview";
import { InstallationReadinessReviewPage } from "./InstallationReadinessReviewPage";

const session = vi.hoisted(() => ({ value: { authenticated: false, principal: null as { operator_id: string; permissions: string[] } | null, csrfToken: null as string | null } }));
vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: () => session.value }));

vi.mock("../api/installationReadinessReview", async (original) => {
    const module = await original<typeof import("../api/installationReadinessReview")>();
    return { ...module, getInstallationReadinessReview: vi.fn() };
});
vi.mock("../api/executionPermissionGrant", async (original) => {
    const module = await original<typeof import("../api/executionPermissionGrant")>();
    return { ...module, listExecutionPermissionGrants: vi.fn(), createExecutionPermissionGrant: vi.fn(), executionPermissionGrantIdempotencyKey: () => "stable-key" };
});
vi.mock("../api/installationExecutionAdmission", async (original) => {
    const module = await original<typeof import("../api/installationExecutionAdmission")>();
    return { ...module, listInstallationExecutionAdmissions: vi.fn(), createInstallationExecutionAdmission: vi.fn(), installationExecutionAdmissionIdempotencyKey: () => "stable-admission-key" };
});
vi.mock("../api/runnerBindingPlan", () => ({ listRunnerBindingPlans: vi.fn() }));

function renderPage(path = `/installation/candidate-records/${uuid4}/readiness-review`) {
    return render(<MemoryRouter initialEntries={[path]}><Routes>
        <Route path="/installation/candidate-records/:candidateRecordId/readiness-review" element={<InstallationReadinessReviewPage />} />
        <Route path="/empty" element={<InstallationReadinessReviewPage />} />
    </Routes></MemoryRouter>);
}

describe("InstallationReadinessReviewPage", () => {
    it.each(["review", "audit_evidence"] as const)("refuses a mismatched %s candidate identity before reading permission evidence", async (field) => {
        const response = structuredClone(readinessGatedFixture);
        response[field].candidate_record_id = "00000000-0000-4000-8000-000000000002";
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(response);
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load this review");
        expect(listExecutionPermissionGrants).not.toHaveBeenCalled();
        expect(createExecutionPermissionGrant).not.toHaveBeenCalled();
        expect(screen.queryByText("operator-a")).not.toBeInTheDocument();
    });

    it("retries only the review read and avoids duplicate initial reads under Strict Mode", async () => {
        vi.mocked(getInstallationReadinessReview).mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(readinessGatedFixture);
        render(<StrictMode><MemoryRouter initialEntries={[`/installation/candidate-records/${uuid4}/readiness-review`]}><Routes>
            <Route path="/installation/candidate-records/:candidateRecordId/readiness-review" element={<InstallationReadinessReviewPage />} />
        </Routes></MemoryRouter></StrictMode>);
        fireEvent.click(await screen.findByRole("button", { name: "Reload review" }));
        await screen.findByRole("heading", { name: "Evidence check complete" });
        expect(getInstallationReadinessReview).toHaveBeenCalledTimes(2);
        expect(createExecutionPermissionGrant).not.toHaveBeenCalled();
    });

    it("clears the previous candidate's review and permission confirmation when navigating", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.permission.grant"] }, csrfToken: "csrf" };
        let resolveNext!: (value: InstallationReadinessReviewResponseV1) => void;
        vi.mocked(getInstallationReadinessReview).mockResolvedValueOnce(readinessGatedFixture)
            .mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/installation/candidate-records/:candidateRecordId/readiness-review", element: <InstallationReadinessReviewPage /> }], { initialEntries: [`/installation/candidate-records/${uuid4}/readiness-review`] });
        render(<RouterProvider router={router} />);
        fireEvent.click(await screen.findByRole("button", { name: "Review permission choice" }));
        expect(screen.getByLabelText("Permission evidence confirmation")).toBeInTheDocument();
        const nextId = "00000000-0000-4000-8000-000000000002";
        await act(() => router.navigate(`/installation/candidate-records/${nextId}/readiness-review`));
        expect(screen.queryByLabelText("Permission evidence confirmation")).not.toBeInTheDocument();
        expect(screen.queryByText("operator-a")).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Loading installation readiness review");
        const next = structuredClone(readinessGatedFixture);
        next.review.candidate_record_id = nextId; next.audit_evidence.candidate_record_id = nextId;
        await act(async () => resolveNext(next));
        await screen.findByRole("button", { name: "Review permission choice" });
        expect(screen.queryByLabelText("Permission evidence confirmation")).not.toBeInTheDocument();
        expect(createExecutionPermissionGrant).not.toHaveBeenCalled();
    });

    beforeEach(() => { vi.resetAllMocks(); session.value = { authenticated: false, principal: null, csrfToken: null }; vi.mocked(listExecutionPermissionGrants).mockResolvedValue({ grants: [], evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false }); vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue({ admissions: [], evidence_only: true, execution_start_allowed: false, runner_binding_allowed: false, execution_authorized: false, installation_allowed: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false }); vi.mocked(listRunnerBindingPlans).mockResolvedValue({ schema: "runner-binding-plan-collection-v1", plans: [], evidence_only: true, execution_authorized: false, mutation_allowed: false }); });

    it("shows review and permission expiry dates in local time with exact machine timestamps", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.permission.grant"] }, csrfToken: "csrf" };
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(readinessGatedFixture);
        vi.mocked(listExecutionPermissionGrants).mockResolvedValue({ grants: [grantResultFixture], evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false });
        renderPage();
        expect(await screen.findByRole("heading", { name: "Current record for later review" })).toBeInTheDocument();

        const localTime = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
        const expectLocalTimestamp = (value: string, root: ParentNode = document) => {
            const timestamp = Array.from(root.querySelectorAll("time")).find((node) => node.dateTime === value);
            expect(timestamp).toBeDefined();
            if (!timestamp) throw new Error(`Expected visible time for ${value}`);
            expect(timestamp).toHaveTextContent(localTime(value));
        };
        const reviewState = screen.getByRole("heading", { name: "Evidence check complete" }).closest("section");
        if (!reviewState) throw new Error("Expected readiness review section");
        expectLocalTimestamp(readinessGatedFixture.review.observed_at, reviewState);

        const grantRow = screen.getByRole("heading", { name: "Current record for later review" }).closest("li");
        if (!grantRow) throw new Error("Expected permission record");
        expectLocalTimestamp(grantResultFixture.grant!.recorded_at, grantRow);
        expectLocalTimestamp(grantResultFixture.grant!.valid_until, grantRow);
        fireEvent.click(screen.getByText("Record and evidence details"));
        const observedLabel = screen.getByText("Observed at", { exact: true });
        expectLocalTimestamp(grantResultFixture.status!.observed_at, observedLabel.parentElement ?? document);
        fireEvent.click(screen.getByRole("button", { name: "Review permission choice" }));
        const confirmation = screen.getByLabelText("Permission evidence confirmation");
        fireEvent.click(within(confirmation).getByText("Verify the exact review"));
        const checkedLabel = within(confirmation).getByText("Review checked at");
        expectLocalTimestamp(readinessGatedFixture.review.observed_at, checkedLabel.parentElement ?? document);

        fireEvent.click(screen.getByText("Evidence chain (14 records)"));
        const chain = screen.getByRole("list", { name: "Installation evidence chain" });
        const firstEvidenceItem = within(chain).getAllByRole("listitem")[0]!;
        fireEvent.click(within(firstEvidenceItem).getByText("Record identity and expiry"));
        const evidenceExpiry = readinessGatedFixture.review.evidence[0]!.valid_until;
        if (!evidenceExpiry) throw new Error("Expected first evidence fixture expiry");
        expectLocalTimestamp(evidenceExpiry, firstEvidenceItem);
    });

    it("renders loading then the readiness-gated evidence, linkage, audit, and authority boundary", async () => {
        let resolve!: (value: typeof readinessGatedFixture) => void;
        vi.mocked(getInstallationReadinessReview).mockReturnValue(new Promise((done) => { resolve = done; }));
        renderPage();
        expect(screen.getByRole("status")).toHaveTextContent(/loading installation readiness review/i);
        resolve(readinessGatedFixture);
        expect(await screen.findByRole("heading", { name: "Evidence check complete" })).toBeInTheDocument();
        expect(screen.queryByText("operator-a")).not.toBeVisible();
        screen.getAllByText(readinessGatedFixture.review.review_fingerprint.value).forEach((node) => expect(node).not.toBeVisible());
        fireEvent.click(screen.getByText("Review identity and technical codes"));
        expect(screen.getByText("Authenticated operator").nextSibling).toHaveTextContent("operator-a");
        fireEvent.click(screen.getByText("Evidence chain (14 records)"));
        const chain = screen.getByRole("list", { name: "Installation evidence chain" });
        expect(within(chain).getAllByRole("listitem")).toHaveLength(14);
        expect(within(chain).getByText(/Saved candidate review · Current at last check/i)).toBeInTheDocument();
        expect(within(chain).getByText(/Delivery receipt · Current at last check/i)).toBeInTheDocument();
        within(chain).queryAllByText("a".repeat(64)).forEach((node) => expect(node).not.toBeVisible());
        expect(screen.getAllByText("a".repeat(64)).length).toBeGreaterThan(10);
        fireEvent.click(screen.getByText("Technical evidence links"));
        expect(screen.getByText("v033_verification_fingerprint")).toBeInTheDocument();
        fireEvent.click(screen.getByText("Audit record and authority flags"));
        expect(screen.getByText("Mutation attempted").nextSibling).toHaveTextContent("false");
    });

    it("renders ordered blocked and Home Assistant golden state", async () => {
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(blockedFixture);
        renderPage();
        expect(await screen.findByRole("heading", { name: "Blocked" })).toBeInTheDocument();
        const blockers = screen.getByRole("list", { name: "Readiness issues" });
        const items = within(blockers).getAllByRole("listitem");
        expect(items[0]).toHaveTextContent("The evidence is out of date");
        expect(items[1]).toHaveTextContent("Atlas cannot install this application");
        expect(screen.queryByText("stale_evidence")).not.toBeVisible();
        fireEvent.click(screen.getByText("Review identity and technical codes"));
        expect(screen.getByText("stale_evidence")).toBeVisible();
        fireEvent.click(screen.getByText(/Evidence chain \(/));
        expect(screen.getByText(/expired or stale evidence stays recorded but blocks readiness/i)).toBeInTheDocument();
    });

    it("renders redacted error and empty states without leaked details", async () => {
        vi.mocked(getInstallationReadinessReview).mockRejectedValue(new Error("secret token at /internal/path 10.0.0.1"));
        const { unmount } = renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Sensitive details are hidden.");
        expect(document.body).not.toHaveTextContent(/secret token|internal\/path|10\.0\.0\.1/i);
        unmount();
        renderPage("/empty");
        expect(screen.getByRole("status")).toHaveTextContent("No candidate record selected.");
    });

    it("contains explicit non-authorizing copy and no effect controls or action navigation", async () => {
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(readinessGatedFixture);
        renderPage();
        expect(await screen.findByText("These checks are saved for your account. Reading this page does not update or use them.")).toBeVisible();
        await waitFor(() => expect(screen.getByRole("heading", { name: "Evidence check complete" })).toBeInTheDocument());
        const boundary = screen.getByLabelText("Read-only authority boundary");
        expect(boundary).toHaveTextContent(/does not install anything or start work/i);
        expect(boundary).toHaveTextContent(/does not approve or authorize installation/i);
        expect(screen.queryAllByRole("button")).toHaveLength(0);
        const links = screen.getAllByRole("link");
        expect(links).toHaveLength(1);
        expect(links[0]).toHaveTextContent("Discovery");
        expect(document.body.textContent).not.toMatch(/install now|execute now|run now|deploy now|dispatch now|retry now|resend now|send to agent|start workflow|roll back now/i);
    });

    it("uses a two-step exact evidence-only confirmation and renders create/readback", async () => {
        session.value = { authenticated: true, principal: { operator_id: "operator-a", permissions: ["installation.execution.permission.grant"] }, csrfToken: "csrf" };
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(readinessGatedFixture);
        vi.mocked(listExecutionPermissionGrants).mockResolvedValue({ grants: [grantResultFixture], evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false });
        vi.mocked(createExecutionPermissionGrant).mockResolvedValue(grantResultFixture);
        renderPage();
        expect(await screen.findByRole("heading", { name: "Current record for later review" })).toBeInTheDocument();
        screen.getAllByText("a".repeat(64)).forEach((node) => expect(node).not.toBeVisible());
        fireEvent.click(screen.getByText("Record and evidence details"));
        expect(screen.getByText("v0.20–v0.34 linkage fingerprint").nextSibling).toHaveTextContent("a".repeat(64));
        fireEvent.click(screen.getByText("Authority and retry details"));
        expect(screen.getByText(/permanent reservation: true/i)).toHaveTextContent(/retry allowed: false · replay allowed: false/i);
        fireEvent.click(screen.getByRole("button", { name: "Review permission choice" }));
        expect(screen.getByLabelText("Permission evidence confirmation")).toHaveTextContent(/saves evidence for a later review only/i);
        fireEvent.click(screen.getByRole("button", { name: "Save permission record" }));
        await waitFor(() => expect(createExecutionPermissionGrant).toHaveBeenCalled());
        expect(createExecutionPermissionGrant).toHaveBeenCalledWith(uuid4, expect.objectContaining({ confirmation_text: expect.stringContaining("This does not install or execute anything."), execution_authorized: false, mutation_allowed: false }), "csrf", "stable-key");
        expect(within(screen.getByRole("list", { name: "Execution permission grants" })).getAllByRole("listitem")).toHaveLength(1);
    });
});
