# Controlled Doctor failure messages

Doctor reports are displayed in Mission Control and printed by the local CLI.
Previously, configuration and collection exceptions were converted directly to
strings, and an offline Docker payload's native error entered a public finding.
Those details can contain credentials, connection URLs or configuration excerpts.
Exception formatting can also fail and prevent the diagnostic report itself.

Configuration failures and failed checks now produce fixed guidance identifying
the configuration/access areas to review. The check name, failed collection flag,
critical status and existing score deductions remain available. An offline Docker
payload is copied with an owned error message before the existing finding rule
runs; the source payload is untouched. Successful collection of an offline Docker
response still has a passed collection check and a critical health finding, as
before. Collection success is not service health.

The API and CLI use the same controlled report. No raw-error field, debug mode,
logging of native exceptions, or error-string matching is added. The dedicated
Doctor DTOs, route, finding rules, score calculation, provider clients, approvals
and execution capabilities remain unchanged. This constrains the Doctor report's
projection of captured errors; it does not change other finding consumers.

A regression test against the previous source demonstrates reflection of a
synthetic credential canary. Native tests cover configuration and check failures,
offline Docker error payloads, exceptions whose string conversion raises, source
payload preservation, CLI output and HTTP serialization. Existing Docker and Home
Assistant finding tests verify classification behavior. Tests run with injected
collectors in a network-disabled container, read-only source and disposable state.
No production diagnostic collection is performed.
