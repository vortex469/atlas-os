import { act, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HealthEvidence } from "./HealthEvidence";
import { HealthEvidenceContext } from "./healthEvidenceContext";
import { SystemHealthSummary } from "../features/mission-control/SystemHealthSummary";
import { evidenceTimestamp, healthState, normalizeAtlasHealth } from "../utils/healthPresentation";

afterEach(() => vi.useRealTimers());

describe("authoritative health presentation", () => {
    it.each([
        ["healthy", "Healthy"], ["online", "Healthy"],
        ["warning", "Degraded"], ["critical", "Degraded"], ["degraded", "Degraded"],
        ["offline", "Unavailable"], ["unavailable", "Unavailable"],
        ["blocked", "Blocked"], ["unknown", "Status unknown"],
        [null, "Status unknown"], [42, "Status unknown"], [{}, "Status unknown"],
        ["success", "Status unknown"], ["running", "Status unknown"], ["constructor", "Status unknown"],
    ])("presents %j as %s without treating operational states as health", (status, label) => {
        render(<HealthEvidence status={status} />);
        expect(screen.getByText(label)).toBeInTheDocument();
        expect(screen.getByText("Check time unavailable.")).toBeInTheDocument();
    });

    it("explains when neither a health status nor check time is available", () => {
        render(<HealthEvidence status="unknown" />);
        expect(screen.getByText("No status information is available.")).toBeInTheDocument();
        expect(screen.getByText("Check time unavailable.")).toBeInTheDocument();
    });

    it("retains source critical severity and renders reasons as plain text", () => {
        render(<HealthEvidence status="critical" reason="<script>bad()</script>" />);
        expect(screen.getByText("Reported status: critical")).toBeInTheDocument();
        expect(screen.getByText("<script>bad()</script>")).toBeInTheDocument();
        expect(document.querySelector("script")).toBeNull();
    });

    it("keeps overview health summaries compact while retaining the reason and distinct severity", () => {
        render(<>
            <HealthEvidence compact status="offline" reason="Connection refused" />
            <HealthEvidence compact status="critical" reason="Policy failure" />
        </>);
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        expect(screen.getByText("The service refused the connection.")).toBeInTheDocument();
        expect(screen.queryByText("Reported status: offline")).not.toBeInTheDocument();
        expect(screen.getByText("Reported status: critical")).toBeInTheDocument();
        expect(screen.queryByText("Check time unavailable.")).not.toBeInTheDocument();
    });

    it.each([
        ["[Errno 111] Connection refused", "The service refused the connection."],
        ["Connection refused", "The service refused the connection."],
        ["[Errno 113] No route to host", "The service could not be reached over the network."],
        ["No route to host", "The service could not be reached over the network."],
        ["[Errno 101] Network is unreachable", "Atlas Core has no reachable network path to the service host."],
        ["[Errno -3] Temporary failure in name resolution", "Atlas Core could not resolve the service host name."],
        ["[Errno 110] Connection timed out", "The service did not respond in time."],
        ["timed out", "The service did not respond in time."],
    ])("explains network failures in plain language: %s", (reason, explanation) => {
        render(<HealthEvidence compact status="offline" reason={reason} />);
        expect(screen.getByText(explanation)).toBeInTheDocument();
        expect(screen.queryByText(/Errno/)).not.toBeInTheDocument();
    });

    it("ages current timestamped evidence without changing the authoritative status", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-09-13T12:00:00Z"));
        render(<HealthEvidence status="healthy" checkedAt="2026-09-13T12:00:00Z" />);
        expect(screen.getByText(/Checked \(UTC\)/)).toBeInTheDocument();
        const time = document.querySelector("time");
        expect(time).toHaveTextContent(new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(Date.parse("2026-09-13T12:00:00Z")));
        expect(time).not.toHaveTextContent("2026-09-13T");
        act(() => vi.advanceTimersByTime(90_000));
        expect(screen.getByText("Last report: Healthy.")).toBeInTheDocument();
        expect(screen.getByText("Status unknown")).toBeInTheDocument();
        expect(screen.queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(screen.getByText(/Last checked \(UTC\)/)).toBeInTheDocument();
        expect(document.querySelector("time")).toHaveAttribute("dateTime", "2026-09-13T12:00:00Z");
    });

    it.each([null, "yesterday", "2026-09-13", {}, "2099-01-01T00:00:00Z", "2026-02-30T00:00:00Z", "2026-09-13T24:00:00Z", "2026-09-13T12:00Z"])("does not claim freshness for timestamp %j", (checkedAt) => {
        render(<HealthEvidence status="healthy" checkedAt={checkedAt} reason={{ unsafe: true }} />);
        expect(screen.getByText("Check time unavailable.")).toBeInTheDocument();
        expect(screen.queryByText(/Checked \(UTC\)/)).not.toBeInTheDocument();
    });

    it.each(["2024-02-29T12:00:00.123456Z", "2026-09-13T14:00:00+02:00", "2026-09-13T07:00:00-05:00"])("accepts authoritative timestamp %s", (timestamp) => {
        expect(evidenceTimestamp(timestamp)).toBe(Date.parse(timestamp));
    });

    it.each(["2025-02-29T00:00:00Z", "2100-02-29T00:00:00Z", "2026-00-01T00:00:00Z", "2026-01-00T00:00:00Z", "2026-01-01T00:00:00+24:00"])("rejects impossible timestamp %s", (timestamp) => {
        expect(evidenceTimestamp(timestamp)).toBeNull();
    });

    it("presents policy failure evidence and timestamp in the system summary", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-09-13T12:00:00Z"));
        render(<SystemHealthSummary evidence={{ policyHealth: { data: { status: "degraded", error: "Policy validation failed", checked_at: "2026-09-13T11:59:45Z" } } }} />);
        expect(screen.getByText("Degraded")).toBeInTheDocument();
        expect(screen.getByText("Policy validation failed")).toBeInTheDocument();
        expect(screen.getByText(/Checked \(UTC\)/)).toBeInTheDocument();
    });

    it("shows checking only for health reports that have not returned yet", () => {
        render(<SystemHealthSummary evidence={{ health: { data: { atlas: "healthy" } } }} loading />);
        const overall = within(screen.getByRole("article", { name: "Overall service status" }));
        const findings = within(screen.getByRole("article", { name: "System findings" }));
        const policy = within(screen.getByRole("article", { name: "Policy settings check" }));
        expect(overall.getByText("Healthy")).toBeInTheDocument();
        expect(findings.getByRole("status")).toHaveTextContent("Checking…");
        expect(policy.getByRole("status")).toHaveTextContent("Checking…");
        expect(findings.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
    });

    it("shows a single unavailable message when a health report failed without data", () => {
        render(<SystemHealthSummary evidence={{ policyHealth: { unavailable: true } }} />);
        const policy = within(screen.getByRole("article", { name: "Policy settings check" }));
        expect(policy.getByText("Current information could not be loaded.")).toBeInTheDocument();
        expect(policy.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(policy.queryByText("No status information is available.")).not.toBeInTheDocument();
    });

    it("omits missing-time placeholders from system summaries when sources do not report check times", () => {
        render(<SystemHealthSummary evidence={{
            health: { data: { atlas: "healthy" } },
            summary: { data: { status: "healthy", summary: "No findings." } },
            policyHealth: { data: { status: "healthy" } },
        }} />);
        expect(screen.getAllByText("Healthy")).toHaveLength(3);
        expect(screen.queryByText("Check time unavailable.")).not.toBeInTheDocument();
    });

    it("omits an unavailable-time placeholder when a compact source reports no timestamp", () => {
        render(<SystemHealthSummary evidence={{ policyHealth: { data: { status: "healthy", checked_at: null } } }} />);
        expect(screen.getByText("Healthy")).toBeInTheDocument();
        expect(screen.queryByText("Check time unavailable.")).not.toBeInTheDocument();
    });

    it("marks retained dashboard evidence stale until refresh recovers", () => {
        const { rerender } = render(<HealthEvidenceContext.Provider value={{ stale: true }}><HealthEvidence status="online" /></HealthEvidenceContext.Provider>);
        expect(screen.getByText("Status unknown")).toBeInTheDocument();
        rerender(<HealthEvidenceContext.Provider value={{ stale: false }}><HealthEvidence status="offline" reason="Connection refused" /></HealthEvidenceContext.Provider>);
        expect(screen.queryByText("Status unknown")).not.toBeInTheDocument();
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        expect(screen.getByText("The service refused the connection.")).toBeInTheDocument();
    });

    it.each([null, [], "healthy", { atlas: true, services: [] }, { services: { broken: null, bad: { status: {}, message: [], details: null, latency_ms: "5", http_status: {} } } }])("handles malformed API evidence %j", (payload) => {
        const health = normalizeAtlasHealth(payload);
        expect(healthState(health.atlas)).toBe("Unknown");
        Object.values(health.services).forEach((service) => {
            expect(healthState(service.status)).toBe("Unknown");
            expect(service.message).toBeNull();
            expect(service.latency_ms).toBeNull();
            expect(service.http_status).toBeNull();
            expect(service.details).toEqual({});
        });
        render(<SystemHealthSummary evidence={{ health: { data: payload }, policyHealth: { data: { checked_at: {}, error: [] } } }} />);
        expect(screen.getAllByText("Status unknown")).toHaveLength(3);
    });

    it("does not manufacture an aggregate from healthy services", () => {
        render(<SystemHealthSummary evidence={{ health: { data: { services: { core: { status: "healthy" } } } } }} />);
        expect(screen.getAllByText("Status unknown")).toHaveLength(3);
        expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
    });
});
