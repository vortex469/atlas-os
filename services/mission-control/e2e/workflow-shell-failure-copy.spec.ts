import { expect, test } from '@playwright/test';
import { installMissionControlMocks } from './mission-control-fixtures';

const sessionId = 'workflow-shell-failure-fixture';
const candidateFingerprint = 'candidate-fingerprint';
const planFingerprint = 'plan-fingerprint';

for (const width of [320, 390, 1280]) test(`workflow preparation failures use plain language at ${width}px`, async ({page}) => {
    const mutations: string[] = [];
    const writes: string[] = [];
    await installMissionControlMocks(page, 'available', mutations);
    await page.setViewportSize({width, height: 900});

    await page.route(`**/agent-api/candidate-planning/${sessionId}/workflow`, route => {
        expect(route.request().method()).toBe('GET');
        return route.fulfill({json: {
            candidate_planning_session_id: sessionId,
            candidate_id: 'candidate-fixture',
            candidate_fingerprint: candidateFingerprint,
            candidate_plan_id: 'plan-fixture',
            candidate_plan_fingerprint: planFingerprint,
            workflow_session_id: 'workflow-fixture',
            workflow_status: 'awaiting_approval',
            implementation_approval_request_id: 'approval-fixture',
            conversion_status: 'workflow_created',
            core_revalidation_status: 'accepted_for_planning',
            reason_codes: [],
            failure: null,
        }});
    });
    await page.route(`**/agent-api/candidate-planning/${sessionId}/implementation`, async route => {
        expect(route.request().method()).toBe('POST');
        expect(route.request().postDataJSON()).toEqual({
            expected_candidate_fingerprint: candidateFingerprint,
            expected_plan_fingerprint: planFingerprint,
        });
        writes.push('prepare exact request');
        return route.fulfill({json: {
            candidate_planning_session_id: sessionId,
            workflow_session_id: 'workflow-fixture',
            translation_status: 'implementation_translation_failed',
            implementation_request_id: null,
            exact_approval_request_id: null,
            candidate_fingerprint: candidateFingerprint,
            plan_fingerprint: planFingerprint,
            repository_head: null,
            translator_version: 'fixture-translator',
            reason_codes: ['repository_stale'],
            failure: {
                code: 'repository_stale',
                message: 'Trusted repository HEAD differs from the reviewed candidate plan.',
            },
        }});
    });

    await page.goto(`/candidate-planning/${sessionId}/workflow`);
    await expect(page.getByRole('heading', {name: 'Review workflow', exact: true})).toBeVisible();
    await page.getByRole('button', {name: 'Prepare exact request', exact: true}).click();

    const alert = page.getByRole('alert');
    await expect(alert).toContainText('The repository changed after review. Re-plan against the current repository before preparing this request again.');
    const failureCode = page.getByText('Failure code: repository_stale', {exact: true});
    await expect(failureCode).toBeHidden();
    const technicalDetails = page.getByText('Request technical details', {exact: true});
    await expect(technicalDetails.locator('..')).not.toHaveAttribute('open');
    await technicalDetails.click();
    await expect(failureCode).toBeVisible();
    await expect(page.getByRole('button', {name: 'Re-plan against current repository', exact: true})).toBeVisible();
    expect(writes).toEqual(['prepare exact request']);
    expect(mutations).toHaveLength(1);
    expect(mutations[0]).toContain(`/candidate-planning/${sessionId}/implementation`);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
