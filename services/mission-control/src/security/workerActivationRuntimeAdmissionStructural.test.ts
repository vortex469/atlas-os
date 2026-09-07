import { describe, expect, it } from "vitest";
import api from "../api/workerActivationRuntimeAdmission.ts?raw";
import component from "../features/installation/WorkerActivationRuntimeAdmission.tsx?raw";
import parent from "../features/installation/WorkerActivationRuntimePrerequisite.tsx?raw";
import navigation from "../layouts/MainLayout.tsx?raw";
import router from "../app/router.tsx?raw";
const modules = import.meta.glob(["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;
describe("v0.54 read-only Mission Control isolation", () => {
    it("uses only credentialed Core collection and item reads", () => {
        expect(api.match(/atlas\.get/g)).toHaveLength(2);
        expect(api.match(/withCredentials: true/g)).toHaveLength(2);
        expect(api + component).not.toMatch(/atlas\.(post|put|patch|delete)|setInterval|setTimeout|WebSocket|EventSource|Worker\(|localStorage|sessionStorage|document\.cookie|Authorization|Bearer|Date\.now|crypto\./);
        expect(component).not.toMatch(/<(button|form|input|select|textarea)\b|dangerouslySetInnerHTML/i);
        expect(component).not.toMatch(/<details[^>]*\bopen/);
        expect(component).toContain("Runtime prerequisites remain incomplete");
    });
    it("has only exact evidence consumers nested beneath the prerequisite, with no navigation", () => {
        expect(parent).toContain("<WorkerActivationRuntimeAdmission prerequisite={state} />");
        expect(router + navigation).not.toMatch(/WorkerActivationRuntimeAdmission|worker-activation-runtime-admissions/);
        expect(Object.entries(modules).filter(([, source]) => /workerActivationRuntimeAdmission|WorkerActivationRuntimeAdmission|worker-activation-runtime-admissions/.test(source)).map(([path]) => path).sort()).toEqual([
            "../api/workerActivationRuntimeAdmission.ts",
            "../features/installation/WorkerActivationRuntimeAdmission.tsx",
            "../features/installation/WorkerActivationRuntimePrerequisite.tsx",
            "../types/workerActivationRuntimeAdmission.ts",
        ]);
    });
});
