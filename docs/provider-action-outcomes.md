# Honest provider action outcomes

Provider actions now distinguish catalog reads, action responses and follow-up
status refreshes. A rejected refresh callback cannot turn an already confirmed
action result into an Action unavailable error. The result stays visible, and
Refresh provider status repeats only the existing read callback. Catalog failures
say Action list unavailable and offer Reload action list.

The action response reader checks the requested provider and action IDs, controlled
status/success agreement, message type, warning strings and result-data shape.
Core's optional data/warnings defaults and additive fields remain compatible.
The request URL, confirmation flag and parameters are unchanged. A missing,
malformed, mismatched or failed response does not prove that an action never ran.
It produces Action outcome not confirmed, without reflecting raw error content.

Unconfirmed outcomes pause action controls for the current mounted provider panel.
Review action history and provider status before another attempt. A status refresh
does not resolve the original request and does not clear that pause. There is no
action-retry button, automatic replay or retry after a status-refresh failure.
Synchronous in-flight guards prevent overlapping submissions and status reads.
Results and uncertainty are still bound to the provider panel's existing key;
late responses from a departed provider cannot attach to its replacement.

This is a view-scoped guard, not durable idempotency or proof of exactly-once
execution. Navigation/reload can create a new panel. Core retains action admission,
confirmation and execution authority; no server request/approval contract changes.
A matching reported failed result remains distinct from an unreadable outcome.
Provider-page structure and its existing retained-data behavior are unchanged.

Unit coverage exercises confirmed/failed results, lost responses, mismatched and
malformed responses, duplicate clicks, refresh rejection/retry, provider changes,
catalog reads and declined confirmation. Browser cases at 320/390/1280 pixels
allow one exact confirmed synthetic fixture POST, bind its origin/path/body, and
verify that status reads never repeat it. Other writes use the existing rejection
fixture; the shared read-only browser suite is unchanged. No real provider or
production service is contacted, and no runtime is enabled or deployed.
