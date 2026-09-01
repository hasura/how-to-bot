# Contributing

## Lifecycle

1. **Proposal** — define outcome, non-goals, risk tier, affected systems, and evidence plan.
2. **Draft** — add a neutral specification, at least one adapter, synthetic fixtures,
   tests, failure cases, and claims manifest.
3. **Automated checks** — run `uv run python tools/validate.py`,
   `uv run python tools/check_links.py`, `uv run python tools/secret_scan.py`, and
   `uv run pytest`.
4. **Human review** — domain and reproducibility review; independent reproduction
   for T2+; designated security review for T3.
5. **Publish** — record version, evidence, supported adapters, limitations, and next review.
6. **Maintain or retire** — retest after material changes or incidents; mark stale,
   deprecate, or withdraw with cleanup guidance.

## Pull requests

Keep one operational claim per claims entry. Use synthetic or explicitly approved,
privacy-safe data. Never commit credentials, customer-derived records, private
screenshots, or copied production logs. A tutorial PR must include the reviewer
checklist from `TUTORIAL_STANDARD.md`.

By contributing, you agree that your contribution is licensed under Apache-2.0.
