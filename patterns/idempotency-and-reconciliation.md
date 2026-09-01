# Pattern: idempotency and reconciliation

Use a caller-generated key bound to semantic intent. Record intent before impact,
reuse the key on selective retries, and reconcile ambiguous responses against the
source of truth. A duplicate returns the original semantic outcome rather than
repeating impact. Document key lifetime, equivalence, concurrency, and residue.
