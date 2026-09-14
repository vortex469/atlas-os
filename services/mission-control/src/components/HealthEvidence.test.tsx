import { act, render, screen } from "@testing-library/react";
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
        ["blocked", "Blocked"], ["unknown", "Unknown"],
        [null, "Unknown"], [42, "Unknown"], [{}, "Unknown"],
        ["success", "Unknown"], ["running", "Unknown"], ["constructor", "Unknown"],
    ])("presents %j as %s without treating operational states as health", (status, label) => {
        render(<HealthEvidence status={status} />);
        expect(screen.getByText(label)).toBeInTheDocument();
        expect(screen.getByText(/Evidence age unknown/)).toBeInTheDocument();
    });

    it("retains source critical severity and renders reasons as plain text", () => {
        render(<HealthEvidence status="critical" reason="<script>bad()</script>" />);
        expect(screen.getByText("Source status: critical")).toBeInTheDocument();
        expect(screen.getByText("<script>bad()</script>")).toBeInTheDocument();
        expect(document.querySelector("script")).toBeNull();
    });

    it("ages current timestamped evidence without changing the authoritative status", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-09-13T12:00:00Z"));
        render(<HealthEvidence status="healthy" checkedAt="2026-09-13T12:00:00Z" />);
        expect(screen.getByText(/Current evidence/)).toBeInTheDocument();
        act(() => vi.advanceTimersByTime(90_000));
        expect(screen.getByText(/Stale evidence/)).toBeInTheDocument();
        expect(screen.queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(screen.getByText(/Last-known status: Healthy/)).toBeInTheDocument();
        expect(document.querySelector("time")).toHaveAttribute("dateTime", "2026-09-13T12:00:00Z");
    });

    it.each([null, "yesterday", "2026-09-13", {}, "2099-01-01T00:00:00Z", "2026-02-30T00:00:00Z", "2026-09-13T24:00:00Z", "2026-09-13T12:00Z"])("does not claim freshness for timestamp %j", (checkedAt) => {
        render(<HealthEvidence status="healthy" checkedAt={checkedAt} reason={{ unsafe: true }} />);
        expect(screen.getByText(/Evidence age unknown/)).toBeInTheDocument();
        expect(screen.queryByText(/Current evidence/)).not.toBeInTheDocument();
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
        expect(screen.getByText(/Current evidence/)).toBeInTheDocument();
    });

    it("marks retained dashboard evidence stale until refresh recovers", () => {
        const { rerender } = render(<HealthEvidenceContext.Provider value={{ stale: true }}><HealthEvidence status="online" /></HealthEvidenceContext.Provider>);
        expect(screen.getByText(/Last-known status/)).toBeInTheDocument();
        rerender(<HealthEvidenceContext.Provider value={{ stale: false }}><HealthEvidence status="offline" reason="Connection refused" /></HealthEvidenceContext.Provider>);
        expect(screen.queryByText(/Last-known status/)).not.toBeInTheDocument();
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
        expect(screen.getByText("Connection refused")).toBeInTheDocument();
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
        expect(screen.getAllByText("Unknown")).toHaveLength(3);
    });

    it("does not manufacture an aggregate from healthy services", () => {
        render(<SystemHealthSummary evidence={{ health: { data: { services: { core: { status: "healthy" } } } } }} />);
        expect(screen.getAllByText("Unknown")).toHaveLength(3);
        expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
    });
});
