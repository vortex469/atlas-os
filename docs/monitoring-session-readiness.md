# Monitoring editor session ownership

Public resource inventory and monitoring facts remain visible when an operator
signs out or changes accounts. Caller readiness, advisory suggestions, reviewed
choices, save feedback and suppression acknowledgements belong to the current
operator session and are discarded when that session changes.

The private editor boundary uses public principal metadata, never a CSRF token
or credential, to identify its lifetime. Replies from a disposed session cannot
restore its grants, replace the current session's data or invalidate the current
session with an old 401. Within a session, only the latest private read applies.
Late save replies likewise cannot attach feedback to another operator's view.
Disposing the view does not cancel a request already admitted by Core.

An editor requires available current operator state as well as Core's capability
and resource-safety fields. Cached grants cannot override anonymous or unavailable
state. Losing readiness resets local editor state and suppression acknowledgement;
a new session starts from reported configuration and requires its own decisions.

Core retains authorization, CSRF validation, fingerprint/version checks and all
execution authority. HTTP requests and backend behavior are unchanged. Tests use
synthetic session/permission responses, preserve read-only public facts and bind
fixture writes to exact local origins, paths and bodies; no real operator login,
provider action, deployment or runtime enablement is involved.
