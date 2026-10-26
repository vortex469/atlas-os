# Checking an uncertain monitoring save

A lost response or an unexpected server error does not prove that a monitoring save failed. Core can also return `security_audit_unavailable` after the intent mutation has completed. Mission Control therefore reports “Save outcome not confirmed” for these cases and pauses monitoring saves across the mounted provider panel.

The paused panel retains its public resource facts and offers **Check monitoring state**. This action reads public monitoring state and private operator readiness; it does not refresh provider discovery or repeat the save. Both reads must succeed before editing resumes. A failed check leaves the pause in place. Repeated clicks cannot overlap checks.

After a successful check, the affected editor resets to the returned setting, discards its reviewed suggestion and requires fresh suppression acknowledgement. The notice says that current state was reloaded, without claiming that the original request completed. While paused, the editor also hides its ordinary unsaved-change prompt because the submitted value may already have been applied.

Known rejection responses retain their existing feedback. In particular, the explicitly rejected 503 reasons `mutation_not_activated`, `store_migration_required`, `store_unavailable` and `provider_read_unavailable` remain rejection cases; other 503 responses are uncertain. Core request bodies, permission checks, record-version checks and audit behavior are unchanged.

This is a mounted-view recovery guard, not durable request idempotency. Leaving the provider or changing sessions discards local guard state and loads server facts again. Successful HTTP acknowledgements continue through the existing API reader.

Tests cover lost responses, post-commit audit errors, failed checks, duplicate check clicks, cross-row pauses and fresh suppression acknowledgement. Browser fixtures exercise the failed-check/recovery path at 320, 390 and 1280 pixels and allow exactly one synthetic policy PUT followed only by reads.
