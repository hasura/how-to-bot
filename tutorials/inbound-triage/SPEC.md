# Inbound triage neutral specification

## Outcome and boundaries

Given one inbound event, the adapter first verifies the trusted requester against the
current policy for the exact record, source, source version, reporter, and
`inbound_events:read` scope. It then validates freshness and bounds, suggests one
private-draft queue or explicitly abstains, provides exact evidence spans, and separates
extracted facts from policy inference. Anushrut Gupta owns final disposition and
sensitive exceptions.

The adapter never sends, alerts, assigns, closes, creates, updates, publishes, or makes
a final disposition. It has no network, credential, model, live source, external
destination, or recurring execution path.

## Input and output

Required event fields are `id`, `received_at`, `source`, `source_version`, `reporter`,
`subject`, and `body`. The adapter also requires a trusted request context, current
authorization policy, durable replay ledger, redacted telemetry sink, and independent
kill switch.

A successful output contains event/source versions, `draft` status, suggested route,
optional grounded suggested resolution, reason codes, exact source/version/field byte
span and hash evidence, extracted facts, inference status, confidence, human-owner
fields, sensitive/abstention/duplicate flags, idempotency/run IDs, and terminal state.
Raw subject/body are absent.

## State and steps

The full vocabulary is `received`, `validated`, `planned`, `awaiting_approval`,
`executing`, `succeeded`, `partially_succeeded`, `failed`, `cancelled`, and
`reconciled`. Awaiting approval and partial success are unreachable in this T1 no-write
adapter but remain explicit for neutral-contract completeness.

Normal execution is:

`received → validated → planned → executing → succeeded`

Authorization, validation, conflict, policy, telemetry, deadline, or runtime failures
end visibly at `failed`. Stop activation ends visibly at `cancelled`. A controlled retry
after failed/cancelled/interrupted work ends at `reconciled`. Illegal transitions fail.

Machine-readable contracts for authorize, validate, claim, plan, record, and recover
steps live in `tutorial.yaml`, including schemas, pre/postconditions, invariants,
timeouts, errors, and exits.

## Authorization and content policy

Authorization happens before subject/body validation or routing. Retrieval success and
bot capability never imply requester authorization. Missing, broader, revoked, stale,
differently owned, differently sourced, or source-version-mismatched access fails
without returning content.

Untrusted text cannot define policy, permission, tools, recipients, approval, or impact.
Security matches outrank only when uniquely strongest or sensitive. Equal-strength
cross-route evidence is contradictory and abstains. No match abstains to
`general-review`. Sensitive evidence forces security escalation with named human review.

## Replay, deadline, and stop

Event ID is logical identity. A fingerprint binds timestamp, source, source version,
reporter, subject, and body. SQLite transactions atomically claim intent across adapter
instances. Exact replay returns the original semantic result; changed content under the
same ID conflicts. Batch ordering is received time then event ID. Interrupted claims
require owner marking before controlled recovery. Two failed attempts stop further work.

A monotonic 30-second deadline and owner-controlled kill switch are checked at every
boundary. Only Anushrut Gupta can activate/resume the switch; resume requires explicit
reconciliation. Every activation/resume is audited.

## State and telemetry governance

The SQLite ledger retains minimal fingerprint/state/result data for seven days, with
owner-only deletion, reset, and retention purge. Telemetry retains redacted transition,
policy-decision, and retry events for 30 days; only tutorial-maintainer and
independent-reviewer roles may read or purge it. Telemetry loss stops visibly before
authorization or routing and cannot authorize impact.

This local implementation is not a distributed ledger or production classifier.