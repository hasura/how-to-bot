# Changelog

## 0.4.0 — 2026-09-01

Foundation first cut after the third independent review of
`5e9f9628ae0bb2620fc82893f06d2ee4e70693dd`:

- Rejected non-finite runtime values.
- Enforced record-step and shared global deadlines through durable finalization.
- Prevented fallible terminal telemetry from occurring after replay-visible publication.
- Applied one absolute runtime budget across each batch.
- Added governed run IDs and terminal traces for oversized batches.
- Required owner-authorized, evidence-bound reconciliation.
- Changed evidence spans from character indices to UTF-8 byte offsets.
- Bound event identity to exact validated payload bytes, including whitespace.
- Preserved all eight attacks as pytest and frozen evaluation regressions.
- Froze evaluation v4 with original exact denominators, nine zero-failure invariants,
  and 14 mandatory adversarial probes.
- Added canonical role/playbook/pattern discovery, MAINTAIN/COMPLETE ownership, and
  Try it → Run it repeatedly → Operate it safely stages to the tutorial schema.
- Added a deterministic dependency-light static catalog generated from canonical manifests.
- Marked all v0.4.0 claims `documented` pending fresh independent reproduction.

This is a runnable foundation first cut, not a production-ready workflow or public
operational approval.

## 0.3.0 — 2026-09-01

Second remediation after independent review of commit
`1f4e4a6c835c402abe44cbcfbb5e526edca7e859`:

- Preserved the six reviewer-authored attacks as canonical pytest and evaluation probes.
- Added strict RFC3339 syntax, a non-expandable 30-second runtime ceiling, and all six
  declared step-timeout fences.
- Added `owner_run_id` fencing, staged/finalized results, stale-owner rejection, and
  kill-switch generation serialization through final publication.
- Made resume depend on DurableLedger-verified reconciliation.
- Made malformed pre-sort batches produce governed, attributable validation histories.
- Added redacted claim, plan, and outcome telemetry sufficient to reconstruct success.
- Froze evaluation v3 with original exact denominators, nine zero-failure invariants,
  and six mandatory adversarial probes.
- Replaced prior remediation assertions with the exact 18-row review matrix.
- Marked the tutorial `needs_retest` pending fresh independent review.

## 0.2.0 — 2026-09-01

First remediation after independent review of commit
`c88b8f9ba54c8a9feb9e06e281ed8cfd23820ca9`:

- Completed strict identity, lifecycle, outcome, actor/data-flow, step, state,
  observability, evaluation, and maintenance contracts.
- Aligned claims to the frozen label taxonomy.
- Added trusted current requester/per-record/source/version authorization.
- Added transactional SQLite replay state, conflict handling, interruption recovery,
  governance, deterministic ordering, and repeated-error stop.
- Added strict timestamp freshness, exact evidence spans, fact/inference separation,
  grounded resolution, contradiction/unsupported abstention, and named human ownership.
- Added enforced deadlines, independent audited mid-run stop, controlled resume, and
  reconstructable redacted histories with ACL/retention/degraded behavior.
- Added predeclared thresholds, seven-case evaluation, lifecycle invalidation, 30-test
  adversarial/conformance suite, and row-level remediation traceability.

## 0.1.0 — 2026-08-31

- Added draft neutral contract and local Python adapter.
- Added synthetic fixtures, conformance tests, and initial failure-injection tests.