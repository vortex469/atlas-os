import type { CandidatePlanningResponse } from "../src/types/atlasAgent";
import { expect, test } from "./mission-control-fixtures";

// Read-only synthetic planning state with deliberately long technical IDs.
const planning: CandidatePlanningResponse = {
    session_id: `planning-${"a".repeat(64)}`,
    candidate_id: `candidate-${"b".repeat(64)}`,
    status: "ready_for_planning",
    planning_allowed: true,
    predecessor_session_id: `planning-previous-${"d".repeat(40)}`,
    successor_session_id: `planning-newer-${"e".repeat(40)}`,
    intake_status: "accepted_for_planning",
    intake_reason_codes: [],
    candidate_fingerprint: `candidate-fingerprint-v1:${"c".repeat(64)}`,
    unsupported_reason: null,
    plan: null,
    planning_failure: null,
};

for (const viewport of [{ width: 320, height: 844 }, { width: 390, height: 844 }, { width: 1280, height: 900 }]) {
    test.describe(`Plain planning summary at ${viewport.width}px`, () => {
        test.use({ viewport });
        test("keeps plain next steps visible and session IDs under read-only details", async ({ page, baseURL, rejectedMutationRequests }) => {
            const expectedOrigin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
            let reads = 0;
            await page.route(`**/agent-api/candidate-planning/${planning.session_id}`, async (route) => {
                const request = route.request();
                if (request.method() !== "GET" || new URL(request.url()).origin !== expectedOrigin) {
                    await route.fulfill({ status: 405, json: { detail: "Fixture permits exact-origin reads only." } });
                    return;
                }
                reads += 1;
                await route.fulfill({ json: planning });
            });
            await page.goto(`/candidate-planning/${planning.session_id}`);
            await expect(page.getByRole("heading", { name: "Plan this change", exact: true })).toBeVisible();
            await expect(page.getByRole("heading", { name: "Plan", exact: true, level: 2 })).toBeVisible();
            const disclosure = page.locator("details").filter({ has: page.getByText("Technical details", { exact: true }) });
            await expect(disclosure).not.toHaveAttribute("open");
            await expect(page.getByText(planning.candidate_fingerprint!, { exact: true })).toBeHidden();
            await expect(page.getByText(planning.predecessor_session_id!, { exact: true })).toBeHidden();
            await expect(page.getByText(planning.successor_session_id!, { exact: true })).toBeHidden();
            await expect(page.getByRole("link", { name: "Open earlier session" })).toHaveAttribute("href", `/candidate-planning/${planning.predecessor_session_id}`);
            await expect(page.getByRole("link", { name: "Open newer session" })).toHaveAttribute("href", `/candidate-planning/${planning.successor_session_id}`);
            const nextStep = page.getByRole("button", { name: "Generate Plan", exact: true });
            await expect(nextStep).toBeEnabled();
            await expect(nextStep).toBeVisible();
            const initialReads = reads;
            await disclosure.locator("summary").click();
            await expect(page.getByText(planning.candidate_fingerprint!, { exact: true })).toBeVisible();
            await expect(page.getByText(planning.predecessor_session_id!, { exact: true })).toBeVisible();
            await expect(page.getByText(planning.successor_session_id!, { exact: true })).toBeVisible();
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            expect(reads).toBe(initialReads);
            expect(rejectedMutationRequests).toEqual([]);
            await disclosure.locator("summary").click();
            await expect(disclosure).not.toHaveAttribute("open");
            await page.screenshot({ path: `/tmp/atlas-plain-planning-${viewport.width}.png`, fullPage: true });
        });
    });
}
