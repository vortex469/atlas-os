import { describe, expect, it } from "vitest";

import navigation from "../layouts/MainLayout.tsx?raw";
import navigationMetadata from "../app/navigation.ts?raw";
import router from "../app/router.tsx?raw";

describe("Mission Control 2.0 shell navigation boundary", () => {
    it("renders navigation from shared metadata, not duplicated definitions", () => {
        // The shell must import the shared metadata module.
        expect(navigation).toMatch(/from "\.\.\/app\/navigation"/);
        // The shell must not define its own enabled destination list.
        expect(navigation).not.toMatch(/label:\s*"Mission Control"/);
        expect(navigation).not.toMatch(/label:\s*"Deployment analysis"/);
        // Every enabled destination label lives in exactly one metadata
        // module so desktop and mobile surfaces cannot drift apart.
        expect(navigationMetadata).toMatch(/label:\s*"Overview"/);
        expect(navigationMetadata).toMatch(/label:\s*"Deployment analysis"/);
    });

    it("keeps only supported destinations in the visible menu", () => {
        expect(navigationMetadata).toMatch(/path:\s*"\//);
        expect(navigationMetadata).toMatch(/path:\s*"\/operations"/);
        expect(navigationMetadata).toMatch(/path:\s*"\/operations\/history"/);
        expect(navigationMetadata).toMatch(/path:\s*"\/operations\/request"/);
        expect(navigationMetadata).toMatch(/path:\s*"\/discovery"/);
        expect(navigationMetadata).toMatch(/path:\s*"\/execution-candidates"/);
        expect(navigationMetadata).toMatch(/path:\s*"\/workflows"/);
        expect(navigationMetadata).toMatch(/path:\s*"\/forge"/);
        expect(navigationMetadata).not.toMatch(/disabledNavigationItems|enabled:\s*false/);
        expect(navigationMetadata).not.toMatch(/label:\s*"(Knowledge|Developer|Settings)"/);
        // The router is untouched by the shell refactor.
        expect(router).toMatch(/path:\s*"operations\/request"/);
        expect(router).toMatch(/path:\s*"operator\/login"/);
    });

    it("does not render nonfunctional future-destination placeholders", () => {
        expect(navigation).not.toMatch(/disabledNavigationItems|Soon/);
        expect(navigationMetadata).not.toMatch(/disabledNavigationItems|Soon/);
    });

    it("adds no authority-bearing navigation or browser storage to the shell", () => {
        for (const forbidden of [
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "Authorization",
            "Bearer",
            "X-Atlas-Operator",
            "X-User",
            "WebSocket",
            "EventSource",
            "atlas.post",
            "atlas.put",
            "atlas.patch",
            "atlas.delete",
        ]) {
            expect(navigation).not.toContain(forbidden);
            expect(navigationMetadata).not.toContain(forbidden);
        }
    });
});
