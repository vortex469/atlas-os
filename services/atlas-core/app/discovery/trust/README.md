# Sigstore production trust root

`sigstore-production-trusted-root.json` is the official production trusted root
bundled with `sigstore==4.5.0`.

- SHA-256: `6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66`
- Exact byte size: `6787`
- Purpose: Atlas Home Assistant Sigstore verification
- Runtime behavior: read-only
- Automatic refresh: forbidden
- Update policy: explicit, reviewed Atlas commit only

This file is a production trust anchor, not ordinary test data. Runtime
verification must read this repository-owned file directly and must not consult
or modify user caches, `$HOME`, XDG state, TUF network state, or system trust
roots.
