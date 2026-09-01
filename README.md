# How to Bot

**Status: v0.1 draft foundation**

How to Bot is an open operating manual for persistent workplace bots. It publishes
verified operational playbooks—not prompt snippets. Every tutorial defines the job,
actors, permissions, state, approval boundaries, tests, observability, failure
behavior, recovery, stop path, evidence, and maintenance status.

## What is in v0.1

- A machine-readable tutorial contract and JSON Schemas.
- A risk-tier and evidence model.
- Automated manifest, link, and secret checks.
- A synthetic **inbound triage** pilot demonstrating bounded classification,
  suggested routing, citations, escalation, replay protection, and permission checks.
- A CI workflow that runs the complete local validation suite.

## Quick start

Prerequisites: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
uv run python tools/validate.py
uv run python tools/check_links.py
uv run python tools/secret_scan.py
uv run pytest
uv run python tutorials/inbound-triage/run.py   tutorials/inbound-triage/fixtures/events.json
```

The pilot uses only synthetic data and performs no network calls or durable external
writes.

## Repository map

- `TUTORIAL_STANDARD.md` — normative v0.1 authoring and publication contract.
- `EVIDENCE_POLICY.md` — claim labels and evidence thresholds.
- `schemas/` — machine-readable tutorial, permission, approval, and claim schemas.
- `tools/` — repository validation.
- `tutorials/inbound-triage/` — the first runnable pilot.
- `patterns/` — reusable operational patterns.
- `platforms/` — adapter contract guidance.

## Safety posture

The highest material risk dimension determines a tutorial's tier. A model never
approves its own action. Authorization is enforced by trusted code. Changed targets,
payloads, permissions, or cost invalidate prior approval. T4 workflows are not
publishable as ordinary runnable tutorials.

See [SECURITY.md](SECURITY.md), [TUTORIAL_STANDARD.md](TUTORIAL_STANDARD.md), and
the pilot [threat model](tutorials/inbound-triage/THREAT_MODEL.md).

## Project state

This repository foundation is a draft. Passing automated tests establishes only the
claims listed as `VERIFIED`; it does not make the pilot production-ready. Publication
requires the review gates in `TUTORIAL_STANDARD.md`.
