# Pattern: idempotency and reconciliation

Use a caller-generated key bound to semantic intent. Record intent before impact,
reuse the key on selective retries, and reconcile ambiguous responses against the
source of truth. A duplicate returns the original semantic outcome rather than
repeating impact. Document key lifetime, equivalence, concurrency, and residue.


For recoverable concurrent work, logical identity alone is insufficient: bind ownership
to a run identifier or fencing token and require it on completion, finalization, and
abort. Stage a result before making it replay-visible, recheck stop/deadline controls,
then finalize. A reassigned recovery owner must invalidate every stale owner's terminal
write. Controlled resume must verify durable reconciled state rather than trust a caller
boolean.
