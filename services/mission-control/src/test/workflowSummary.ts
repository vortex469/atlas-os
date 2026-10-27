// Malformed public replies used at both workflow-summary entry points.
export const unreadableWorkflowFields: [string, object][] = [
    ["conversion", { conversion_status: {} }], ["blank conversion", { conversion_status: " " }],
    ["workflow status", { workflow_status: {} }], ["workflow ID", { workflow_session_id: {} }],
    ["missing workflow ID", { workflow_session_id: undefined }], ["workflow traversal", { workflow_session_id: ".." }],
    ["workflow Unicode", { workflow_session_id: "\ud800" }], ["approval reference", { implementation_approval_request_id: {} }],
    ["candidate fingerprint", { candidate_fingerprint: {} }], ["missing fingerprint", { candidate_fingerprint: undefined }],
    ["plan fingerprint", { candidate_plan_fingerprint: {} }], ["reasons", { reason_codes: null }],
    ["reason item", { reason_codes: [{}] }], ["missing failure", { failure: undefined }],
    ["failure", { failure: {} }], ["failure message", { failure: { code: "failed", message: {} } }],
];
