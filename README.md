# How to Bot

**Status: foundation first cut — runnable on synthetic data; v0.4 awaits independent review**

How to Bot is the open operating manual for persistent workplace bots. It publishes
testable operational playbooks—not prompt snippets. Every tutorial teaches a bot to own
a bounded, observable outcome and defines the trigger, actors, permissions, state,
approval boundaries, evidence, tests, monitoring, recovery, maintenance, and stop path.

The canonical library supports three discovery views:

- **Role = who** delegates the work.
- **Playbook = what** concrete responsibility and outcome the bot owns.
- **Pattern = how** the reusable operating mechanism works.

Ownership is either **MAINTAIN** (an ongoing control loop with a healthy condition) or
**COMPLETE** (a bounded mission with a done condition). Tutorials disclose complexity
progressively: **Try it → Run it repeatedly → Operate it safely**.

## Foundation first cut

- A strict machine-readable tutorial contract and five JSON Schemas.
- A generated static catalog with role, playbook, and pattern views.
- Machine-readable MAINTAIN/COMPLETE ownership and progressive tutorial stages.
- A risk-tier model and frozen evidence-label taxonomy.
- Cross-file manifest, generated-site, link, secret, lint, test, and evaluation checks.
- A synthetic **inbound triage** COMPLETE pilot demonstrating current-policy
  authorization, deterministic private-draft routing/abstention, UTF-8 byte evidence
  spans, named human disposition, owner-fenced durable replay handling, reconstructable
  redacted histories, shared batch and step/global deadlines, and an independently
  activatable generation-fenced stop control.
- Evaluation v4 with raw numerators/denominators, nine zero-failure invariants, and all
  14 independent adversarial probes preserved as executable regressions.
- Row-level remediation traceability for the unchanged 36-check review contract and the
  eight attacks from the third independent review.

The static site is generated from canonical manifests and contains no external
JavaScript, CSS, fonts, analytics, credentials, or live data.

## Exact tested environment

- CPython 3.14.4
- uv 0.12.8
- local-python adapter 0.4.0
- Exact dependency versions are locked in `uv.lock` and repeated in the tutorial manifest.

Prerequisite: install [uv](https://docs.astral.sh/uv/) 0.12.8. `uv sync --frozen`
uses `.python-version` to obtain the tested Python version when needed.

## Complete local gate

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

Preview the generated site locally:

```bash
python -m http.server 8000 --directory site/dist
```

The pilot uses only synthetic data and performs no network call, external write, send,
assignment, closure, alert, publication, or final disposition. Its SQLite ledger is
durable across local adapter instances on one shared filesystem; it is not distributed.

## Repository map

- `TUTORIAL_STANDARD.md` — normative authoring and publication contract.
- `EVIDENCE_POLICY.md` — frozen claim labels and evidence rules.
- `schemas/` — tutorial, permission, approval, claim, and evaluation schemas.
- `tools/` — repository and deterministic site validation.
- `site/` — site source, generated catalog, and local preview instructions.
- `tutorials/inbound-triage/` — the first runnable pilot.
- `tutorials/inbound-triage/remediation.yaml` — review and attack traceability.
- `patterns/` — reusable operational patterns.
- `platforms/` — adapter contract guidance.

## Safety and evidence posture

The highest material risk dimension determines a tutorial's tier. A model or source
message never grants authorization or approves its own action. Trusted code enforces
current authorization before protected content use. Material changes force
`needs_retest`. T4 workflows are not publishable as ordinary runnable tutorials.

See [SECURITY.md](SECURITY.md), [TUTORIAL_STANDARD.md](TUTORIAL_STANDARD.md), and
the pilot [threat model](tutorials/inbound-triage/THREAT_MODEL.md).

All v0.4.0 claims remain `documented` while status is `needs_retest`. Passing author-side
checks does not promote them to `demonstrated` and does not establish independent
reproduction, production readiness, safety, reliability, portability, release approval,
or public operational approval.