import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getInstallationReadinessReview } from "../api/installationReadinessReview";
import { createExecutionPermissionGrant, listExecutionPermissionGrants } from "../api/executionPermissionGrant";
import { listInstallationExecutionAdmissions } from "../api/installationExecutionAdmission";
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

function renderPage(path = `/installation/candidate-records/${uuid4}/readiness-review`) {
    return render(<MemoryRouter initialEntries={[path]}><Routes>
        <Route path="/installation/candidate-records/:candidateRecordId/readiness-review" element={<InstallationReadinessReviewPage />} />
        <Route path="/empty" element={<InstallationReadinessReviewPage />} />
    </Routes></MemoryRouter>);
}

describe("InstallationReadinessReviewPage", () => {
    beforeEach(() => { vi.resetAllMocks(); session.value = { authenticated: false, principal: null, csrfToken: null }; vi.mocked(listExecutionPermissionGrants).mockResolvedValue({ grants: [], evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false }); vi.mocked(listInstallationExecutionAdmissions).mockResolvedValue({ admissions: [], evidence_only: true, execution_start_allowed: false, runner_binding_allowed: false, execution_authorized: false, installation_allowed: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false }); });

    it("renders loading then the readiness-gated evidence, linkage, audit, and authority boundary", async () => {
        let resolve!: (value: typeof readinessGatedFixture) => void;
        vi.mocked(getInstallationReadinessReview).mockReturnValue(new Promise((done) => { resolve = done; }));
        renderPage();
        expect(screen.getByRole("status")).toHaveTextContent(/loading installation readiness review/i);
        resolve(readinessGatedFixture);
        expect(await screen.findByRole("heading", { name: /readiness gated — execution admission is not defined/i })).toBeInTheDocument();
        expect(screen.getByText("Authenticated operator").nextSibling).toHaveTextContent("operator-a");
        const chain = screen.getByRole("list", { name: "Installation evidence chain" });
        expect(within(chain).getAllByRole("listitem")).toHaveLength(14);
        expect(within(chain).getByText(/v0.20 · candidate_record · current/i)).toBeInTheDocument();
        expect(within(chain).getByText(/v0.33 · inert_delivery_receipt · current/i)).toBeInTheDocument();
        expect(screen.getAllByText("a".repeat(64)).length).toBeGreaterThan(10);
        expect(screen.getByRole("heading", { name: /required linkage and fingerprints/i })).toBeInTheDocument();
        expect(screen.getByText("v033_verification_fingerprint")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: /read-only audit evidence/i })).toBeInTheDocument();
        expect(screen.getByText("Mutation attempted").nextSibling).toHaveTextContent("false");
    });

    it("renders ordered blocked and Home Assistant golden state", async () => {
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(blockedFixture);
        renderPage();
        expect(await screen.findByRole("heading", { name: "Blocked" })).toBeInTheDocument();
        const blockers = screen.getByRole("list", { name: "Ordered readiness blockers" });
        const items = within(blockers).getAllByRole("listitem");
        expect(items[0]).toHaveTextContent("Stale evidence");
        expect(items[1]).toHaveTextContent("Installation capability unsupported");
        expect(screen.getByText(/expired or stale evidence remains evidence only and blocks readiness/i)).toBeInTheDocument();
    });

    it("renders redacted error and empty states without leaked details", async () => {
        vi.mocked(getInstallationReadinessReview).mockRejectedValue(new Error("secret token at /internal/path 10.0.0.1"));
        const { unmount } = renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Installation readiness review is unavailable.");
        expect(document.body).not.toHaveTextContent(/secret token|internal\/path|10\.0\.0\.1/i);
        unmount();
        renderPage("/empty");
        expect(screen.getByRole("status")).toHaveTextContent("No candidate record selected.");
    });

    it("contains explicit non-authorizing copy and no effect controls or action navigation", async () => {
        vi.mocked(getInstallationReadinessReview).mockResolvedValue(readinessGatedFixture);
        renderPage();
        await waitFor(() => expect(screen.getByRole("heading", { name: /readiness gated/i })).toBeInTheDocument());
        const boundary = screen.getByLabelText("Read-only authority boundary");
        expect(boundary).toHaveTextContent(/not installation, execution, dispatch, retry or resend, Agent invocation, workflow start, provider mutation, repository mutation, in-guest mutation, deployment, rollback, or permission to mutate anything/i);
        expect(boundary).toHaveTextContent(/not approval, admission, authorization, installability, or executability/i);
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
        expect(await screen.findByRole("heading", { name: "Active permission evidence" })).toBeInTheDocument();
        expect(screen.getByText("v0.20–v0.34 linkage fingerprint").nextSibling).toHaveTextContent("a".repeat(64));
        expect(screen.getByText(/permanent reservation: true/i)).toHaveTextContent(/retry allowed: false · replay allowed: false/i);
        fireEvent.click(screen.getByRole("button", { name: "Review permission evidence statement" }));
        expect(screen.getByLabelText("Permission evidence confirmation")).toHaveTextContent(/creates durable permission evidence only/i);
        fireEvent.click(screen.getByRole("button", { name: "Record permission evidence" }));
        await waitFor(() => expect(createExecutionPermissionGrant).toHaveBeenCalled());
        expect(createExecutionPermissionGrant).toHaveBeenCalledWith(uuid4, expect.objectContaining({ confirmation_text: expect.stringContaining("This does not install or execute anything."), execution_authorized: false, mutation_allowed: false }), "csrf", "stable-key");
    });
});
