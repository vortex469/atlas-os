import { describe, expect, it } from "vitest";

import navigation from "../app/navigation.ts?raw";
import router from "../app/router.tsx?raw";

const productionModules = import.meta.glob(
    ["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../test/**"],
    { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

const successorTerms = /control[-_ ]plane[-_ ]evidence|controlPlaneEvidence|ControlPlaneEvidence|atlas[-_/]control[-_/]plane/i;

describe("v0.65 P4 Mission Control projection boundary", () => {
    it("keeps the Sync-excluded successor API, types, and client absent", () => {
        const consumers = Object.entries(productionModules)
            .filter(([, source]) => successorTerms.test(source))
            .map(([path]) => path);

        expect(consumers).toEqual([]);
        expect(router).not.toMatch(successorTerms);
        expect(navigation).not.toMatch(successorTerms);
    });

    it("does not add a successor route, mutation, polling, or execution control", () => {
        const shell = `${router}\n${navigation}`;
        expect(shell).not.toMatch(/atlas\.(post|put|patch|delete)/);
        expect(shell).not.toMatch(/setInterval|setTimeout|WebSocket|EventSource|localStorage|sessionStorage/);
        expect(shell).not.toMatch(/<(button|form|input|select|textarea)\b/i);
    });
});
