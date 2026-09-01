# How to Bot

**Status: Gate 2 needs independent retest — not approved for merge, release, or publication**

How to Bot is an open operating manual for persistent workplace bots. It publishes
testable operational contracts—not prompt snippets. Every tutorial defines the job,
actors, permissions, state, approval boundaries, tests, observability, failure
behavior, recovery, stop path, evidence, and maintenance status.

## Gate 2 contents

- A strict machine-readable tutorial contract and five JSON Schemas.
- A risk-tier model and the frozen evidence-label taxonomy.
- Cross-file manifest, link, secret, lint, and test checks.
- A synthetic **inbound triage** pilot demonstrating current-policy authorization,
  deterministic draft routing/abstention, exact evidence spans, named human disposition,
  owner-fenced durable replay handling, reconstructable redacted histories, enforced
  step/global deadlines, and a generation-fenced independently activatable stop control.
- A predeclared versioned evaluation set with raw numerators/denominators, nine zero-failure invariants, and the six independent attacks.
- An exact row-by-row remediation ledger for all 18 failures in the second independent review.

## Exact tested environment

- CPython 3.14.4
- uv 0.12.8
- local-python adapter 0.3.0
- Exact dependency versions are locked in `uv.lock` and repeated in the tutorial manifest.

Prerequisites: install [uv](https://docs.astral.sh/uv/) 0.12.8. `uv sync --frozen`
uses `.python-version` to obtain the tested Python version when needed.

## Complete local gate

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

The pilot uses only synthetic data and performs no network call, external write, send,
assignment, closure, alert, publication, or final disposition. Its SQLite ledger is
durable across local adapter instances but is not a distributed ledger.

## Repository map

- `TUTORIAL_STANDARD.md` — normative authoring and publication contract.
- `EVIDENCE_POLICY.md` — frozen claim labels and evidence rules.
- `schemas/` — tutorial, permission, approval, claim, and evaluation schemas.
- `tools/` — repository validation.
- `tutorials/inbound-triage/` — the only runnable pilot.
- `tutorials/inbound-triage/remediation.yaml` — traceability for the 18 failed rows in the second review.
- `patterns/` — reusable operational patterns.
- `platforms/` — adapter contract guidance.

## Safety and evidence posture

The highest material risk dimension determines a tutorial's tier. A model or source
message never grants authorization or approves its own action. Current authorization is
enforced by trusted code before content use. Material changes force `needs_retest`.
T4 workflows are not publishable as ordinary runnable tutorials.

See [SECURITY.md](SECURITY.md), [TUTORIAL_STANDARD.md](TUTORIAL_STANDARD.md), and
the pilot [threat model](tutorials/inbound-triage/THREAT_MODEL.md).

All v0.3.0 claims remain `documented` while status is `needs_retest`. Passing author-side
checks does not promote them to `demonstrated` and does not establish independent
reproduction, production readiness, safety, reliability, portability, merge approval,
or publication approval.