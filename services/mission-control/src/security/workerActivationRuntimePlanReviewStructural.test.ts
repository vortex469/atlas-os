import { describe, expect, it } from "vitest";
import api from "../api/workerActivationRuntimePlanReview.ts?raw";
import component from "../features/installation/WorkerActivationRuntimePlanReview.tsx?raw";
import parent from "../features/installation/WorkerActivationRuntimePlan.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";
import hook from "../hooks/useWorkerActivationRuntimePlanReview.ts?raw";
const modules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
describe("v0.56 read-only Mission Control isolation", () => {
    it("uses only credentialed Core collection and item reads", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/withCredentials: true/g)).toHaveLength(2);
        expect(api + component + hook).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|WebSocket|EventSource|Worker\(|localStorage|sessionStorage|document\.cookie|Authorization|Bearer|Date\.now|crypto\./);
        expect(component).not.toMatch(/<(button|form|input|select|textarea)\b|dangerouslySetInnerHTML/i);
        expect(component).not.toMatch(/<details[^>]*\bopen/);
        expect(component).toContain("Plan review is evidence; runtime prerequisites remain incomplete");
    });
    it("has only exact evidence consumers nested beneath the prerequisite, with no navigation", () => {
        expect(parent).toContain("<WorkerActivationRuntimePlanReview plan={state} />");
        expect(router + navigation).not.toMatch(/WorkerActivationRuntimePlanReview|worker-activation-runtime-plan-reviews/);
        expect(Object.entries(modules).filter(([, source]) => /workerActivationRuntimePlanReview|WorkerActivationRuntimePlanReview|worker-activation-runtime-plan-reviews/.test(source)).map(([path]) => path).sort()).toEqual([
            "../api/workerActivationRuntimePlanReview.ts",
            "../features/installation/WorkerActivationRuntimePlan.tsx",
            "../features/installation/WorkerActivationRuntimePlanReview.tsx",
            "../hooks/useWorkerActivationRuntimePlanReview.ts",
            "../types/workerActivationRuntimePlanReview.ts",
        ]);
    });
});
