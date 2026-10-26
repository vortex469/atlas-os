# Connection settings and uncertain saves

Connection settings reads, live-test results and save results are checked before
Mission Control uses them. Provider IDs must match the requested provider,
including the schema inside a save result. Field kinds, options, unique keys,
booleans, dates and nested object shapes follow Core's public connection models.
Optional defaults remain compatible. A response that exposes a secret field's
current value is rejected with an owned error, without reflecting that value.

A valid matching save result confirms the save, clears secret replacement inputs
and shows Connection settings saved. An unreadable or rejected save response
instead shows Save outcome not confirmed: the settings may have been saved.
Draft values remain in place, settings are marked unverified, and saving and
live testing pause. Previous live-test results are cleared when saving starts.

Reload settings is the recovery action. A failed reload keeps the pause. An
explicit successful reload replaces draft values with the current server schema,
clears secret replacements and restores only the controls that schema permits.
An automatic read after a provider-label change cannot clear the pause. No read
replays the save, and no request is retried automatically. The operator still
confirms each later save or live test using the existing confirmation prompts.

Reloading establishes current observed settings; it does not prove whether the
original request finished. This guard belongs to the mounted provider panel,
not a durable idempotency ledger. Navigating away or reloading the page creates
a new panel. Core retains authorization, configuration validation and execution
authority; request bodies and backend behavior are unchanged.

The native contract fixture covers every public connection field kind and all
three response models. Unit tests cover malformed/mismatched responses, field
and secret safety, failed reloads, automatic reads and preserved drafts. Browser
tests permit one exact confirmed synthetic fixture PUT per case, bind its origin,
path and body, and verify recovery performs only reads. No real provider,
production service, model invocation or runtime enablement is involved.
