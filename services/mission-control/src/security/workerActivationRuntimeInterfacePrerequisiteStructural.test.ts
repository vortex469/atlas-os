import { describe, expect, it } from "vitest";
import api from "../api/workerActivationRuntimeInterfacePrerequisite.ts?raw";
import component from "../features/installation/WorkerActivationRuntimeInterfacePrerequisite.tsx?raw";
import parent from "../features/installation/WorkerActivationRuntimePlanReview.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";
import hook from "../hooks/useWorkerActivationRuntimeInterfacePrerequisite.ts?raw";
const modules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
describe("v0.58 retained read-only Mission Control isolation", () => {
    it("uses only credentialed Core collection and item reads", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/withCredentials: true/g)).toHaveLength(2);
        expect(api + component + hook).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|WebSocket|EventSource|Worker\(|localStorage|sessionStorage|document\.cookie|Authorization|Bearer|Date\.now|crypto\./);
        expect(component).not.toMatch(/<(button|form|input|select|textarea)\b|dangerouslySetInnerHTML/i);
        expect(component).not.toMatch(/<details[^>]*\bopen/);
        expect(component).toContain("Interface prerequisite inventory is evidence; runtime prerequisites remain incomplete");
        expect(api + component + hook).not.toMatch(/worker_activation_runtime_interface_admitted|worker-activation-runtime-interface-admissions/);
    });
    it("has only exact evidence consumers nested beneath the prerequisite, with no navigation", () => {
        expect(parent).toContain("<WorkerActivationRuntimeInterfacePrerequisite review={state} />");
        expect(router + navigation).not.toMatch(/WorkerActivationRuntimeInterfacePrerequisite|worker-activation-runtime-interface-prerequisites/);
        expect(Object.entries(modules).filter(([, source]) => /workerActivationRuntimeInterfacePrerequisite|WorkerActivationRuntimeInterfacePrerequisite|worker-activation-runtime-interface-prerequisites/.test(source)).map(([path]) => path).sort()).toEqual([
            "../api/workerActivationRuntimeInterfacePrerequisite.ts",
            "../features/installation/WorkerActivationRuntimeInterfacePrerequisite.tsx",
            "../features/installation/WorkerActivationRuntimePlanReview.tsx",
            "../hooks/useWorkerActivationRuntimeInterfacePrerequisite.ts",
            "../types/workerActivationRuntimeInterfacePrerequisite.ts",
        ]);
    });
});
