# Contributing

## Lifecycle

1. **Proposal** — define outcome, non-goals, affected parties, risk tier, systems,
   exact owners, and a predeclared evidence plan.
2. **Draft** — add the neutral contract, adapter manifest, synthetic fixtures, frozen
   thresholds, conformance/failure tests, claims, runbook, and changelog.
3. **Automated checks** — run every command in the root README.
4. **Human review** — domain and reliability review; non-author clean-room reproduction
   whenever the applicable rubric requires it.
5. **Publish** — only after every applicable blocker and threshold passes; record exact
   version, evidence, limitations, owners, and next review.
6. **Maintain or retire** — permission, policy, runtime, dependency, model, adapter, or
   incident changes force `needs_retest` through the lifecycle invalidation rule.

## Pull requests and reporting

Keep one material operational claim per claims entry and use only the frozen claim-label
taxonomy. Use synthetic or explicitly approved privacy-safe data. Never commit
credentials, customer-derived records, private screenshots, or copied production logs.

Ordinary defects and improvements:
<https://github.com/hasura/how-to-bot/issues>.

Sensitive vulnerabilities:
<https://github.com/hasura/how-to-bot/security/advisories/new>.

A tutorial PR must include the reviewer checklist, raw evaluation numerators and
denominators, exact tool/runtime versions, and row-level remediation traceability for
prior failures. Do not defer an applicable authorization, privacy, approval, recovery,
observability, stop, or truthful-claims blocker as a follow-up.

By contributing, you agree that your contribution is licensed under Apache-2.0.