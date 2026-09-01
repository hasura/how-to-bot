# Threat model

## Actors, assets, classifications, and boundaries

The requester is `synthetic-user-operator`; the operator is `synthetic-operator`.
Anushrut Gupta owns source policy, final disposition, sensitive exceptions, ledger
administration, and stop control. The synthetic reporter is the affected party.
The concrete tool is local-python adapter 0.4.0 with Python 3.14.4 and SQLite. There is
no model, credential, live source, network host, or external destination.

Assets are inbound content, reporter privacy, current authorization policy, routing
integrity, human disposition authority, replay state, and audit history. Fixtures are
synthetic; live inbound content is modeled as confidential; telemetry is redacted
operational metadata.

Trust boundaries:

1. Untrusted event metadata is compared with trusted current policy before content use.
2. Untrusted subject/body crosses into deterministic policy strictly as data.
3. Grounding stores source/version/field/span/hash, not quoted text, in results/history.
4. Final disposition remains outside the adapter with the named human.

## Threats and executable controls

| Threat | Control and regression evidence |
|---|---|
| Differently authorized or revoked requester | Current requester/record/source/version/reporter decision before content; denial-leak tests |
| Stale policy or source version | Exact policy/source-version match; drift tests |
| Prompt injection | Text cannot alter tools, scope, policy, approval, owner, or impact |
| Excessive agency | No destination/network/effect method; every result remains draft |
| Sensitive routine handling | Exact evidence triggers security transfer to Anushrut Gupta |
| Unsupported or contradictory evidence | Explicit abstention with no suggested resolution |
| Non-finite or reset runtime | Finite numeric limit validation and one shared absolute batch deadline |
| Oversized batch | Attributable batch run ID with governed received → failed trace |
| Concurrent/replayed delivery | SQLite atomic claim; owner_run_id-fenced completion/abort; finalized exact reuse; changed-content conflict |
| Adapter crash after claim | Durable intent, owner-marked interruption, fenced recovery, and stale-owner rejection |
| Finalization overrun | Deadline checks inside the durable transaction; failed publication emits no success telemetry |
| Reconciliation forgery | Owner-only compare-and-set against observed fingerprint and terminal state |
| Runaway work | Batch/text/freshness limits, fixed 30s global ceiling, six step timeouts, and repeated-error stop |
| Ignored stop | Activation-generation fence through final publication; ledger-verified owner resume |
| Telemetry leakage | No raw content; reconstructable redacted plan/outcome; ACL/retention/redaction tests |
| Telemetry outage | Terminal events are validated before publication and exposed only after the durable commit; failed telemetry publishes no result |
| Stale state | Seven-day owner-enforced purge, per-record delete, and full reset |

## Residual limits

Keyword policy is illustrative and can miss semantic nuance. SQLite covers local
cross-instance concurrency but not multiple hosts. The frozen set is small and
synthetic. No claim is made for live ingestion, distributed idempotency, model routing,
external actions, production accuracy, reliability, portability, or safety.