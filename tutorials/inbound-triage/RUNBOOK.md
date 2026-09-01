# Runbook

## Start and verify

```bash
uv sync --frozen
uv run python tools/validate.py
uv run pytest tutorials/inbound-triage
uv run python tutorials/inbound-triage/run.py tutorials/inbound-triage/fixtures/events.json
```

Verify every row is `draft`, `requires_human_disposition=true`, and contains citations.

## Pause or stop

Do not invoke new runs. For embedded use, pass `kill_switch=True`; the implementation
fails before reading or classifying an event. A real adapter's kill switch must be
reachable without model cooperation and revoke source access.

## Resume

Confirm the exact scope, fixture provenance, limits, and version; rerun regression tests.
Do not resume impact after model, policy, permission, or adapter drift without review.

## Recover and reconcile

This adapter has no side effects. Restart with a new in-memory ledger only for local
demonstration. A production adapter must check durable idempotency state before retry
and compare against the source of truth after ambiguous responses.

## Escalate

Escalate validation/policy failures to the tutorial maintainer, permission failures to
the source-system owner, and sensitive or suspected-leakage cases to the designated
security owner. Preserve reason codes and correlation/idempotency IDs, not raw secrets.

## Teardown

Delete generated output. No external records or credentials are created.
Expected runtime: under 30 seconds; expected external cost: zero.
