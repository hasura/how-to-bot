# Platform adapters

An adapter maps the neutral contract to concrete identities, scopes, APIs, approval
enforcement, idempotency, errors, telemetry, kill switch, credential revocation, and
teardown. It must run the common conformance suite. Unsupported guarantees must be
declared; adapters may not silently weaken invariants.
