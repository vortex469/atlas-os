# Monitoring drafts and saved feedback

Choosing a different monitoring expectation clears that row's previous save-success message. The editor labels a selected value that differs from the loaded, configured expectation as “Unsaved change. Save to apply it.” Returning to the loaded value removes the draft label without restoring the old success message. A selection on an unconfigured resource is also a draft until saved.

Selection changes do not save automatically. Existing errors, including warnings about an acknowledged save whose refreshed state could not be loaded, remain visible. Permission checks, suppression acknowledgements, save serialization and Core request contracts are unchanged.

Regression coverage saves a value, changes the draft, then returns to the saved value and verifies that only one save request occurred. Browser coverage repeats the transition at 320, 390 and 1280 pixels while retaining the existing two-row concurrency checks.
