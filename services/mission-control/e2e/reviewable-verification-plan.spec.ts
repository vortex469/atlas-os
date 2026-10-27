import { expect, test } from '@playwright/test';
import { installRepositoryJourney, journey, workflowDetail } from './repository-journey-fixture';

for (const width of [320, 390, 1280]) for (const approved of [false, true]) for (const kind of ['missing', 'malformed'] as const) {
    test(`${kind} ${approved ? 'approved' : 'pending'} verification plan recovers through reads at ${width}px`, async ({page, baseURL}) => {
        const fixture = await installRepositoryJourney(page, true, {baseURL});
        await page.setViewportSize({width, height: 900});
        const saved = workflowDetail('verification', approved);
        let reads = 0;
        await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => {
            expect(route.request().method()).toBe('GET');
            reads += 1;
            return route.fulfill({json: reads > 1 ? saved : {...saved, verification_plan: kind === 'missing' ? null : {...saved.verification_plan, verification_check_ids: 'compose-config'}}});
        });
        await page.goto(`/workflows/${journey.workflow}`);
        await expect(page.getByRole('button', {name: 'Check verification plan', exact: true})).toBeEnabled();
        await expect(page.getByRole('button', {name: /Approve Verification|Reject Verification|Resume Approved Verification/})).toHaveCount(0);
        const approval = page.getByRole('region', {name: 'Verification approval', exact: true});
        await expect(approval).toContainText(approved ? 'Verification approval is recorded.' : 'Verification approval is paused');
        if (width === 390 && !approved) await page.getByRole('region', {name: 'Verification Plan', exact: true}).screenshot({path: `/tmp/atlas-unreadable-verification-${kind}-390.png`});
        expect(fixture.writes).toEqual([]);
        await page.getByRole('button', {name: 'Check verification plan', exact: true}).click();
        await expect(page.getByRole('button', {name: approved ? 'Resume Approved Verification' : 'Approve Verification', exact: true})).toBeEnabled();
        await expect(page.getByRole('button', {name: 'Check verification plan', exact: true})).toHaveCount(0);
        expect(reads).toBe(2);
        expect(fixture.writes).toEqual([]);
        expect(fixture.unexpected).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    });
}


for (const stage of ['verification', 'commit'] as const) test(`${stage} approval does not suggest resume after review data disappears`, async ({page, baseURL}) => {
    const fixture = await installRepositoryJourney(page, true, {baseURL});
    await page.setViewportSize({width: 390, height: 900});
    let approved = false;
    let decisions = 0;
    const before = workflowDetail(stage, false);
    const after = workflowDetail(stage, true);
    const unavailable = stage === 'verification' ? {...after, verification_plan: {...after.verification_plan, verification_plan_id: null}} : {...after, commit_request: null};
    await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/implementation-request`, route => {
        expect(route.request().method()).toBe('GET');
        return route.fulfill({json: approved ? unavailable : before});
    });
    await page.route(`**/agent-api/api/v1/agent/workflows/${journey.workflow}/${stage}-approval`, route => {
        expect(new URL(route.request().url()).origin).toBe(new URL(baseURL!).origin);
        expect(route.request().method()).toBe('POST');
        expect(route.request().postDataJSON()).toEqual({workflow_id: journey.workflow, decision: 'approve'});
        decisions += 1;
        expect(decisions).toBe(1);
        approved = true;
        return route.fulfill({json: {workflow_id: journey.workflow, workflow_state: `awaiting_${stage}_approval`, [`${stage}_approval_status`]: 'approved', message: null}});
    });
    const verification = stage === 'verification';
    await page.goto(`/workflows/${journey.workflow}`);
    await page.getByRole('button', {name: verification ? 'Approve Verification' : 'Approve Commit', exact: true}).click();
    await expect(page.getByRole('button', {name: verification ? 'Check verification plan' : 'Check commit request', exact: true})).toBeEnabled();
    await expect(page.getByText(verification ? 'Verification approved. Resume to run the checks.' : 'Commit approved. Resume to finish the local commit.', {exact: true})).toHaveCount(0);
    await expect(page.getByRole('button', {name: verification ? 'Resume Approved Verification' : 'Resume Approved Commit', exact: true})).toHaveCount(0);
    await expect(page.getByRole('region', {name: verification ? 'Verification approval' : 'Commit approval', exact: true})).toContainText('approval is recorded.');
    expect(decisions).toBe(1);
    expect(fixture.writes).toEqual([]);
    expect(fixture.unexpected).toEqual([]);
});
