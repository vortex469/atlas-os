import axios, { isAxiosError } from "axios";

import type {
  ApprovalRequest,
  ApprovalDecision,
  ApprovalResult,
} from "../../types/approval";

const ATLAS_AGENT_API_BASE_URL =
  import.meta.env.VITE_ATLAS_AGENT_API_BASE_URL ?? "/agent-api";

export const approvalApi = axios.create({
  baseURL: ATLAS_AGENT_API_BASE_URL,
  timeout: 15_000,
  headers: {
    Accept: "application/json",
  },
});

export async function createApprovalRequest(
  approvalRequest: ApprovalRequest
): Promise<{ identifier: string }> {
  const response = await approvalApi.post<{ identifier: string }>(
    "/api/v1/agent/approval/request",
    approvalRequest
  );
  return response.data;
}

export async function getPendingApprovals(): Promise<ApprovalResult[]> {
  const response = await approvalApi.get<ApprovalResult[]>(
    "/api/v1/agent/approval/pending"
  );
  return response.data;
}

export async function getApprovalRequest(
  requestId: string
): Promise<ApprovalResult> {
  const response = await approvalApi.get<ApprovalResult>(
    `/api/v1/agent/approval/${requestId}`
  );
  return response.data;
}

export async function submitApprovalDecision(
  requestId: string,
  decision: ApprovalDecision
): Promise<{
  status: string;
  identifier: string;
  approval_status: string;
  reviewer: string;
  reason: string;
}> {
  const response = await approvalApi.post<{
    status: string;
    identifier: string;
    approval_status: string;
    reviewer: string;
    reason: string;
  }>(`/api/v1/agent/approval/${requestId}/decision`, decision);
  return response.data;
}

export function getApprovalErrorMessage(
  error: unknown,
  fallback: string
): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data as
      | { detail?: string }
      | undefined;

    return detail?.detail ?? error.message ?? fallback;
  }

  return error instanceof Error ? error.message : fallback;
}
