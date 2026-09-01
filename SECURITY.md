# Security policy

Report sensitive vulnerabilities privately at
<https://github.com/hasura/how-to-bot/security/advisories/new>. Include the affected
tutorial/version, impact, synthetic reproduction steps, and suggested containment.
Never include real credentials, customer data, or production log material. Ordinary
non-sensitive defects use <https://github.com/hasura/how-to-bot/issues>.

## Repository rules

- No credentials, tokens, private keys, customer records, or production log dumps.
- Fixtures are synthetic or explicitly approved and minimized.
- Untrusted content is data, never authorization, policy, approval, or tool selection.
- Current requester and per-record/source/version authorization is enforced before
  protected content use.
- Models cannot approve their own actions.
- Material version, policy, permission, adapter, runtime, dependency, model, or incident
  change forces `needs_retest`.
- T2+ work requires dry-run, exact semantic approval, destination authorization,
  idempotency, bounded execution, compensation/reconciliation, and an independent stop.
- T4 workflows are not accepted as ordinary runnable tutorials.

The inbound-triage pilot has no credential, network, model, live data, external
destination, side effect, or unattended execution. Its stop, deadline, replay,
authorization, redaction, retention, and telemetry-loss controls are locally tested;
these tests are not a production-safety claim.

Run `uv run python tools/secret_scan.py` before every contribution.