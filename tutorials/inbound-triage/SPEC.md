# Inbound triage neutral specification

## Outcome and boundaries

Given one authorized inbound event, validate it, suggest one queue, list deterministic
reason codes, and cite source fields. The output is a private draft. The workflow never
sends a response, modifies a source system, closes an item, or decides a high-stakes
outcome.

## Input and output

Required input fields: `id`, `received_at`, `source`, `subject`, and `body`. Text is
untrusted and size-bounded. Output includes `event_id`, `status`, `suggested_route`,
`reason_codes`, `citations`, `confidence`, `requires_human_disposition`,
`sensitive_case`, `duplicate`, and `idempotency_key`.

## State transitions

`received → validated → planned → executing → succeeded`

Validation, authorization, or policy failure leads to `failed`. An active kill switch
leads to `cancelled`. There is no `awaiting_approval`: v0.1 is T1, read-only, private
draft work. Any write/send extension must be a separate T2+ adapter with exact preview
and approval.

## Rules and invariants

Security matches outrank billing and technical support. Sensitive terms force security
escalation. No match routes to `general-review`. Source content cannot define policy,
grant scope, select a tool, or authorize impact. The exact required scope is accepted;
broader unexpected scope fails closed. Maximum batch size is 25. Every result is a
draft and requires human disposition.

## Idempotency

The semantic key hashes normalized event identity and content. Exact replay in the
example ledger returns the original outcome with `duplicate=true`. A real adapter must
provide a durable, concurrency-safe ledger and reconcile ambiguous upstream results.

## Error classes

Validation, authorization, policy, and cancellation are explicit. This local adapter
has no dependency, timeout, rate-limit, partial-write, or compensation path because it
has no network and no side effects.
