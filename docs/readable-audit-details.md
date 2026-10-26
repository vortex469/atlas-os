# Readable audit details

The audit-detail screen leads with the recorded action, outcome, provider name,
result message and completion time. Existing Confirmed and Destructive badges
remain visible. Audit/request/provider/action IDs, parameter names, exact duration
and the detailed timing rows are retained under a closed Technical details
section, following the accepted Mission Control layout.

The original phone preview placed the provider after two long correlation IDs,
near the bottom of a 900-pixel viewport. The change addresses information order
and clutter; the original preview already fit the viewport horizontally.

Copy link, back navigation, identity checks, read validation, loading/error
recovery and all request handlers are unchanged. Opening technical details does
not load another record or perform an action. This is a presentation change with
no backend, API, approval or execution-contract changes.

Verification uses the existing UI/browser gates and isolated built-app previews
at 320, 390 and 1280 pixels for successful and failed/destructive results, with
long IDs. Preview data is synthetic, and only local read requests are permitted. Deployment and runtime
acceptance remain separate work.
