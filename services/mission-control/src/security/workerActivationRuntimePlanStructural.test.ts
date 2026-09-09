import { describe, expect, it } from "vitest";
import api from "../api/workerActivationRuntimePlan.ts?raw";
import component from "../features/installation/WorkerActivationRuntimePlan.tsx?raw";
import parent from "../features/installation/WorkerActivationRuntimeAdmission.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";
const modules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
describe("v0.55 read-only Mission Control isolation", () => {
    it("uses only credentialed Core collection and item reads", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/withCredentials: true/g)).toHaveLength(2);
        expect(api + component).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|WebSocket|EventSource|Worker\(|localStorage|sessionStorage|document\.cookie|Authorization|Bearer|Date\.now|crypto\./);
        expect(component).not.toMatch(/<(button|form|input|select|textarea)\b|dangerouslySetInnerHTML/i);
        expect(component).not.toMatch(/<details[^>]*\bopen/);
        expect(component).toContain("Runtime plan is evidence; runtime prerequisites remain incomplete");
    });
    it("has only exact evidence consumers nested beneath the prerequisite, with no navigation", () => {
        expect(parent).toContain("<WorkerActivationRuntimePlan admission={state} />");
        expect(router + navigation).not.toMatch(/WorkerActivationRuntimePlan|worker-activation-runtime-plans/);
        expect(Object.entries(modules).filter(([, source]) => /workerActivationRuntimePlan|WorkerActivationRuntimePlan|worker-activation-runtime-plans/.test(source)).map(([path]) => path).sort()).toEqual([
            "../api/workerActivationRuntimePlan.ts",
            "../api/workerActivationRuntimePlanReview.ts",
            "../features/installation/WorkerActivationRuntimeAdmission.tsx",
            "../features/installation/WorkerActivationRuntimePlan.tsx",
            "../features/installation/WorkerActivationRuntimePlanReview.tsx",
            "../hooks/useWorkerActivationRuntimePlanReview.ts",
            "../types/workerActivationRuntimePlan.ts",
            "../types/workerActivationRuntimePlanReview.ts",
        ]);
    });
});
