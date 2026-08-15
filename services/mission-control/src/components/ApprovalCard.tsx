import { Link } from "react-router-dom";

import type { ApprovalResult } from "../types/approval";

interface ApprovalCardProps {
  approval: ApprovalResult;
}

export function ApprovalCard({ approval }: ApprovalCardProps) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex justify-between items-start">
        <div>
          <h4 className="font-medium text-slate-200">{approval.request.title}</h4>
          <p className="mt-1 text-sm text-slate-400">{approval.request.rationale}</p>
          <div className="mt-2 flex items-center space-x-2">
            <span className="inline-flex items-center rounded-full bg-amber-900/30 px-2.5 py-0.5 text-xs font-medium text-amber-300">
              {approval.request.requested_tool}
            </span>
          </div>
        </div>
        {approval.actionable && approval.request.workflow_id && (
          <Link
            to={`/workflows/${approval.request.workflow_id}`}
            className="rounded-md bg-blue-500 px-3 py-1.5 text-sm font-medium text-blue-950 hover:bg-blue-400"
          >
            Review workflow
          </Link>
        )}
      </div>
      <p className="mt-2 text-xs text-slate-500">{approval.presentation_reason}</p>
    </div>
  );
}
