# How to Bot tutorial standard v0.2

Normative keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** describe requirements.

## Tutorial information architecture

A tutorial MUST teach ownership of a bounded, observable outcome—not merely task
execution or a prompt. One canonical tutorial library MUST support:

- **Role (who):** the person or team delegating responsibility.
- **Playbook (what):** the concrete job, owned object, and observable outcome.
- **Pattern (how):** reusable operational mechanisms independent of one role or job.

Every tutorial MUST classify ownership as:

- **MAINTAIN:** an ongoing control loop that keeps an owned object within a defined
  healthy condition.
- **COMPLETE:** a bounded mission that reaches a verifiable done condition and stops.

Every tutorial MUST name the delegated responsibility, owned object or situation,
healthy/done condition, verification evidence, and stop/approval/escalation boundary.
Tutorials MUST present the same canonical contract progressively as **Try it → Run it
repeatedly → Operate it safely**. Progressive presentation MUST NOT omit or weaken the
underlying authorization, approval, failure, evidence, or stop contract.

## Required contract

Every tutorial MUST define:

1. **Identity/lifecycle:** stable ID, title, version, status, owners, dates, license,
   changelog, adapters, tested versions, risk tier and rationale.
2. **Discovery/ownership:** roles, playbooks, patterns, MAINTAIN/COMPLETE mode,
   responsibility, owned object, healthy/done condition, evidence, and boundaries.
3. **Progression:** Try it, Run it repeatedly, and Operate it safely stages, each with
   a goal, concrete actions, and an exit condition.
4. **Outcome:** job, users, non-goals, preconditions, inputs, outputs, side effects,
   success criteria, unacceptable outcomes, assumptions, limitations.
5. **Actors/trust:** requester, operator, approver, data owner, affected parties,
   bot/tools/downstream systems, untrusted inputs, assets, classifications, and threats.
6. **Capabilities:** exact resources/scopes, credential identity/owner, required versus
   optional permissions, storage/rotation/revocation, allowlists, and run limits.
7. **Neutral workflow:** trigger, termination, states, step contracts, deterministic
   policy checks, ordering, compensation/reconciliation, and ambiguous-input behavior.
8. **Approval:** actions, approvers, semantic preview, expiry/invalidation, denial,
   timeout, separation of duties, and break-glass behavior.
9. **Failure semantics:** taxonomy, retry policy, idempotency, replay/concurrency,
   partial completion, rollback/compensation, recovery, and fail-safe mode.
10. **Observability:** correlation/idempotency IDs, structured events, metrics, traces,
    alerts/owners, redaction/retention/access, and user-visible history.
11. **Operations:** dry-run for writes, independent kill switch, stop limits, canary for
    T2+, runbook, restoration, incident owner, and post-incident learning.
12. **Evaluation:** versioned representative tests, provenance, separated metrics,
    thresholds, zero-failure invariants, trial counts, raters, baseline, regression triggers.
13. **Reproduction:** clean setup, locked dependencies, no-secret config, synthetic
    fixtures, commands, expected outputs, teardown, troubleshooting, cost/time envelope.
14. **Evidence:** claim ID/text/source/label/scope/evidence/date/procedure/limitations.
    Allowed labels are exactly `vendor_claim`, `documented`, `anecdotal`,
    `demonstrated`, `recurring`, or `measured`.
15. **Adapters:** concrete identity, permissions, tools, approval enforcement, retries,
    telemetry, kill switch, teardown, and unsupported guarantees.

## Risk tiers

| Tier | Work | Minimum posture |
|---|---|---|
| T0 | Public/synthetic local work; no side effects | Reproducibility and provenance |
| T1 | Bounded read or private draft | Minimum read scope, redaction, audit, bounded execution |
| T2 | Reversible bounded write | Exact preview, approval, idempotency, limits, kill switch, canary |
| T3 | Sensitive, broad, external, destructive, financial, privilege, or production action | Named point-of-action human; two people for destructive/privilege/bulk/high-value actions |
| T4 | Surveillance, credential harvesting, autonomous high-stakes decisions, unbounded destructive access, safeguard bypass | Prohibited as an ordinary runnable tutorial |

The highest material dimension wins. Splitting a workflow does not lower aggregate risk.
A model MUST NOT approve its own action. Trusted application or downstream code MUST
enforce authorization. Any material post-approval mutation invalidates approval.

## Required states

`received`, `validated`, `planned`, `awaiting_approval` when applicable, `executing`,
`succeeded`, `partially_succeeded`, `failed`, `cancelled`, and `reconciled`.

## Publication gates

1. Completeness and internal consistency.
2. Clean-environment reproducibility.
3. Functional evidence for every success criterion and unacceptable outcome.
4. Minimal permissions, threat coverage, secret absence, and enforced approvals.
5. Tested retries, duplicates, partial completion, recovery, and stop paths.
6. Reconstructable successful, denied, retried, failed, and cancelled/recovered runs.
7. Claims no stronger than the achieved evidence level.
8. Generated human and machine-readable catalog views match canonical manifests.

T2+ requires non-author reproduction. T3 requires designated security/safety review.

## Mandatory serious-workflow failures

Serious workflows (credentials, non-public data, side effects, affected people,
unattended operation, or T2+) MUST test authentication loss, authorization denial,
timeouts/429/5xx, malformed/adversarial input, replay, late success, partial completion,
retry storms, approval denial/expiry, post-approval mutation, policy bypass, ambiguous
targets, scope explosion, leakage, runaway cost, observability loss, kill switch,
crash recovery, version/config drift, and recovery verification.

## Reviewer checklist

- Role, playbook, pattern, ownership mode, owned object, and healthy/done condition agree.
- Outcome, non-goals, affected parties, unacceptable outcomes, and tier are clear.
- Claims are labeled and supported.
- Trust boundaries, prompt injection, excessive agency, minimal permissions, retention,
  deletion, and redaction are covered.
- Exact approval precedes impact; mutation, denial, expiry, cancellation, bypass, and
  kill switch are tested.
- Retries are selective/bounded; side effects are idempotent and reconcilable.
- Limits, alerts, owners, runbook, degraded mode, and incident path exist.
- Edge/adversarial/failure cases and critical invariants pass individually.
- Neutral contract and adapter mappings agree; unsupported guarantees are explicit.
- Try/repeat/operate stages preserve the full contract rather than implying new authority.
- Dependencies, owners, review dates, changelog, deprecation, and reporting are present.