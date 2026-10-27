import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { WorkflowShellPage } from './WorkflowShellPage';
import { createCandidateWorkflowShell, getCandidateWorkflowShell } from '../api/atlas-agent';
vi.mock('../api/atlas-agent', () => ({
  createCandidateWorkflowShell: vi.fn(), getCandidateWorkflowShell: vi.fn(),
  createCandidateImplementationRequest: vi.fn(), createSuccessorCandidatePlanningSession: vi.fn(),
  getCandidatePlanningSession: vi.fn(),
  getAtlasAgentErrorMessage: (_error: unknown, fallback: string) => fallback,
}));
const shell = { candidate_planning_session_id: 'session-1', candidate_id: 'candidate-1',
 candidate_fingerprint: 'fp-1', candidate_plan_id: 'plan-1', candidate_plan_fingerprint: 'plan-fp',
 workflow_session_id: 'workflow-1', workflow_status: 'awaiting_approval', implementation_approval_request_id: 'approval-1',
 conversion_status: 'workflow_created', core_revalidation_status: 'accepted_for_planning', reason_codes: [], failure: null };
function open() { render(<MemoryRouter initialEntries={['/candidate-planning/session-1/workflow']}><Routes><Route path='/candidate-planning/:sessionId/workflow' element={<WorkflowShellPage />} /></Routes></MemoryRouter>); }
beforeEach(() => { vi.resetAllMocks(); vi.mocked(getCandidateWorkflowShell).mockResolvedValue(shell); vi.mocked(createCandidateWorkflowShell).mockResolvedValue(shell); });
it('opening a workflow summary only reads the saved workflow', async () => {
 open(); await screen.findByRole('button', {name: 'Prepare exact request'});
 expect(getCandidateWorkflowShell).toHaveBeenCalledWith('session-1');
 expect(createCandidateWorkflowShell).not.toHaveBeenCalled();
});
it('a failed summary read can retry without creating a workflow', async () => {
 vi.mocked(getCandidateWorkflowShell).mockRejectedValueOnce(new Error('offline'));
 open(); await screen.findByRole('alert');
 await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
 await screen.findByRole('button', {name: 'Prepare exact request'});
 expect(getCandidateWorkflowShell).toHaveBeenCalledTimes(2);
 expect(createCandidateWorkflowShell).not.toHaveBeenCalled();
});
