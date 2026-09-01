# Security policy

Do not open a public issue for a vulnerability that could expose credentials,
sensitive data, or bypass approval/authorization controls. Until a dedicated private
reporting channel is published, contact the repository owner through Hasura's
established security channel and include the affected tutorial/version, impact,
reproduction steps, and suggested containment. Do not include real secrets or
customer data.

## Repository rules

- No credentials, tokens, private keys, customer records, or production log dumps.
- Fixtures must be synthetic or explicitly approved and minimized.
- Untrusted content is data, never authorization.
- Models cannot approve their own actions.
- Tool calls are checked by deterministic policy code.
- T2+ work requires dry-run, exact preview, idempotency, bounded execution, and an
  independent kill switch.
- T4 workflows are not accepted as ordinary runnable tutorials.

Run `uv run python tools/secret_scan.py` before every contribution.
