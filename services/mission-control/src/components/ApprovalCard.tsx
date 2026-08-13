import { useState } from "react";

import type { ApprovalResult } from "../types/approval";
import { submitApprovalDecision } from "../api/approval/index";

interface ApprovalCardProps {
  approval: ApprovalResult;
}

export function ApprovalCard({ approval }: ApprovalCardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleApprove = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    
    try {
      await submitApprovalDecision(approval.identifier, {
        request: approval.request,
        status: "approved",
        reviewer: "current-user", // This would be replaced with actual user info
      });
      
      // In a real app, we would update the UI to show the approval was processed
      // For now, we'll just show a success message briefly
    } catch (error) {
      setSubmitError("Failed to submit approval. Please try again.");
      console.error("Approval submission error:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    
    try {
      await submitApprovalDecision(approval.identifier, {
        request: approval.request,
        status: "rejected",
        reviewer: "current-user", // This would be replaced with actual user info
      });
      
      // In a real app, we would update the UI to show the approval was processed
      // For now, we'll just show a success message briefly
    } catch (error) {
      setSubmitError("Failed to submit rejection. Please try again.");
      console.error("Rejection submission error:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

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
        <div className="flex space-x-2">
          <button
            onClick={handleReject}
            disabled={isSubmitting}
            className="rounded-md bg-red-900/30 px-3 py-1.5 text-sm font-medium text-red-300 hover:bg-red-900/50 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="rounded-md bg-emerald-900/30 px-3 py-1.5 text-sm font-medium text-emerald-300 hover:bg-emerald-900/50 disabled:opacity-50"
          >
            Approve
          </button>
        </div>
      </div>
      {submitError && (
        <p className="mt-2 text-sm text-red-400">{submitError}</p>
      )}
    </div>
  );
}
