# Runbook

## Start and verify

Install uv 0.12.8; `.python-version` selects CPython 3.14.4.

```bash
uv sync --frozen
uv run python tools/validate.py
uv run python tools/build_site.py --check
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
event/model content. The switch blocks new work and is checked throughout execution, including after staged ledger completion and atomically at final publication. Terminal telemetry and durable publication share one locked boundary: neither a false success event nor a replay-visible result may survive if the other side fails.
Record the audit entry and inspect the ledger for executing/cancelled entries. There is
no side-effect inventory because this adapter has no effect capability.

## Reconcile and resume

Mark a genuinely abandoned `executing` claim interrupted using the owner-only ledger
operation. Recheck the observed event fingerprint and terminal state, then reconcile
with the owner identity, exact fingerprint, expected terminal state, and a non-empty
reason. Recheck exact version, current requester policy, source version, limits, and
complete tests. Anushrut Gupta may then call
`resume(..., reconciled=True, reason=..., ledger=ledger)`. A caller assertion without
the ledger, manufactured reconciliation evidence, or a ledger with any executing,
failed, cancelled, or staged entry fails.

A recovered run must emit claim, retry, outcome, and reconciled events and still yield only one finalized semantic outcome; stale owners must receive a conflict. Two failed attempts trigger the repeated-error stop; investigate rather than
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
Expected external cost is zero. Callers may shorten but cannot expand the 30-second global maximum. Enforced step ceilings are authorize 5s, validate 5s, claim 10s, plan 5s, record 5s, and recover 30s.