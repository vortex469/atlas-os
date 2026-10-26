import nativeReview from "./fixtures/readable-commit-review.json" with { type: "json" };
import { expect, test } from "./mission-control-fixtures";

// Synthetic response captured from the native Agent's read-only projection.
// Opening these saved facts must never submit approval or resume execution.
for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 900 }]) {
    test.describe(`Saved commit review at ${viewport.width}px`, () => {
        test.use({ viewport });

        for (const legacy of [false, true]) {
            test(`${legacy ? "older review explains unavailable facts" : "saved file facts stay collapsed until opened"}`, async ({ page, baseURL, rejectedMutationRequests }) => {
                const expectedOrigin = new URL(baseURL ?? "http://127.0.0.1:5173").origin;
                let detailReads = 0;
                await page.route(`**/agent-api/api/v1/agent/workflows/${nativeReview.workflow_id}/implementation-request`, async (route) => {
                    const request = route.request();
                    if (request.method() !== "GET" || new URL(request.url()).origin !== expectedOrigin) {
                        await route.fulfill({ status: 405, json: { detail: "Fixture permits exact-origin reads only." } });
                        return;
                    }
                    detailReads += 1;
                    const body = legacy ? {
                        ...nativeReview,
                        commit_request: { ...nativeReview.commit_request, reviewed_changes: null },
                    } : nativeReview;
                    await route.fulfill({ json: body });
                });
                await page.goto(`/workflows/${nativeReview.workflow_id}`);
                const disclosure = page.locator("details").filter({ has: page.getByText("Files in this review", { exact: true }) });
                await expect(disclosure).not.toHaveAttribute("open");
                await disclosure.getByText("Files in this review", { exact: true }).click();
                await expect(disclosure).toHaveAttribute("open");
                await expect(disclosure.getByText(/Saved when this review was created/)).toBeVisible();
                if (legacy) {
                    await expect(disclosure.getByText("File facts are unavailable for this request. Use the original reviewed evidence.")).toBeVisible();
                } else {
                    for (const file of nativeReview.commit_request.reviewed_changes) {
                        await expect(disclosure.getByText(file.path, { exact: true })).toBeVisible();
                    }
                    await expect(disclosure.getByText("Modified · Executable file", { exact: true })).toHaveCount(2);
                    for (const fingerprint of await disclosure.locator("details").all()) {
                        await expect(fingerprint).not.toHaveAttribute("open");
                    }
                    await disclosure.screenshot({ path: `/tmp/atlas-readable-review-${viewport.width}.png` });
                }
                expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
                const readsBeforeReload = detailReads;
                await page.reload();
                await expect(disclosure).not.toHaveAttribute("open");
                await expect.poll(() => detailReads).toBeGreaterThan(readsBeforeReload);
                expect(rejectedMutationRequests).toEqual([]);
            });
        }
    });
}
