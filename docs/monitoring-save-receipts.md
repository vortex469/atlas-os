# Confirming monitoring-save responses

Mission Control checks each successful HTTP save response against Core's public monitoring-mutation result contract. A response must identify the submitted request, provider, resource type, resource ID, management fingerprint and expectation. Its outcome, record version and replacement flag must agree with each other and the submitted base version. The request binding is copied before the response is awaited.

A malformed or unrelated response raises a fixed local error without reflecting response details. The monitoring panel treats it as an unconfirmed save: editing pauses, and the existing read-only state check offers recovery without replaying the request. A successful HTTP status alone no longer starts the saved-and-confirmed path.

The reader returns only the known result fields. Native created, updated and replacement results are covered by a fixture generated from Core's public models and verified by a native contract test. The browser requires record versions to be safe integers so it cannot confirm a rounded value; Core's wider 64-bit integer contract is unchanged.

Tests cover malformed fields, unrelated bindings, contradictory outcomes, wrong versions, integer precision and request mutation while awaiting a response. Browser cases at 320, 390 and 1280 pixels verify malformed and unrelated successful responses follow the read-only recovery journey, with exactly one synthetic policy PUT.

Request bodies, cookies, CSRF headers, Core authorization, identity checks and server admission behavior are unchanged. This result reader does not provide durable idempotency.
