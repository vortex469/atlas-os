# Home Assistant Sigstore proof fixture

`ha-2026.8.3-bundle.json` is the minimum immutable bundle captured externally
from the successful HermesII offline proof. It contains only public Sigstore
verification material: the signing certificate, DSSE envelope/signature,
Rekor transparency-log entry and inclusion proof, and RFC3161 timestamp.
Inspection found no credentials, tokens, secrets, private keys, or unrelated
research material.

Bundle media type: `application/vnd.dev.sigstore.bundle.v0.3+json`

SHA-256: `733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520`
