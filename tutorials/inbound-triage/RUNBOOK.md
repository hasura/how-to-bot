# Runbook

## Start and verify

Install uv 0.12.8; `.python-version` selects CPython 3.14.4.

```bash
uv sync --frozen
uv run python tools/validate.py
uv run python tools/check_links.py
uv run python tools/secret_scan.py
uv run ruff check .
uv run pytest -vv
uv run python tutorials/inbound-triage/evaluate.py
uv run python tutorials/inbound-triage/run.py tutorials/inbound-triage/fixtures/events.json
```

Require every metric numerator/denominator to meet its predeclared threshold, every
critical invariant to have zero failures, all results to remain drafts, and all
exceptions to be visible.

## Stop while idle or mid-run

Anushrut Gupta calls `KillSwitch.activate(actor_id=..., reason=...)` independently of
event/model content. The switch blocks new work and is checked throughout execution.
Record the audit entry and inspect the ledger for executing/cancelled entries. There is
no side-effect inventory because this adapter has no effect capability.

## Reconcile and resume

Mark a genuinely abandoned `executing` claim interrupted using the owner-only ledger
operation. Reconcile every failed/cancelled entry. Recheck exact version, current
requester policy, source version, limits, and complete tests. Anushrut Gupta may then
call `resume(..., reconciled=True, reason=...)`. Resume without reconciliation fails.

A recovered run must emit retry and reconciled events and still yield only one semantic
outcome. Two failed attempts trigger the repeated-error stop; investigate rather than
retrying again.

## Authorization, denial, and degraded mode

Never infer authorization from retrieval or bot access. Denials are attributable by
run/requester/operator/policy IDs but omit subject/body. If telemetry is unavailable,
the run stops before protected content use. If policy/version access is stale, revoked,
or different, do not fall back to another identity or source.

## State, retention, and teardown

The owner can delete one ledger identity, reset all state, or purge entries older than
seven days. Telemetry reader roles can purge events older than 30 days. Local runner
teardown deletes its temporary SQLite file and generated output.

## Maintenance and escalation

Ordinary defects: <https://github.com/hasura/how-to-bot/issues>. Sensitive reports:
<https://github.com/hasura/how-to-bot/security/advisories/new>.

Permission, policy, runtime, dependency, model, adapter, or incident changes immediately
force `needs_retest`; do not represent prior demonstrated claims as current. Sensitive,
suspected-leakage, authorization, stop, or recovery failures go to Anushrut Gupta.
Expected external cost is zero; enforced per-run duration is at most 30 seconds.