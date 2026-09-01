# Failure-injection matrix

All applicable rows are executable in `test_failure_injection.py`; evaluation-specific
cases also run through the frozen `evaluate.py` set.

| Case | Expected safe outcome | Evidence |
|---|---|---|
| Missing/broader/admin scope | Failed authorization; no content/result | scope/batch limit test |
| Differently authorized record/reporter | Failed authorization without content leakage | per-record authorization test |
| Revoked requester/current policy drift | Failed authorization | revocation and drift tests |
| Source-version drift | Failed authorization before content use | version-drift test |
| Missing/malformed/oversized input | Failed validation/policy | malformed/oversized test |
| Invalid/stale/future timestamp | Failed validation/policy | timestamp test and frozen evaluation |
| Prompt injection | Content remains data; unsupported text abstains | conformance injection test |
| Unsupported evidence | `general-review`, abstained, no resolution | frozen evaluation |
| Equal contradictory route evidence | `general-review`, abstained | frozen evaluation |
| Sensitive evidence | Security transfer to Anushrut Gupta; still draft | conformance/evaluation |
| Serial exact replay | Original semantic result, duplicate=true | serial replay test |
| Concurrent exact replay | One owner and one duplicate | concurrent replay test |
| Same ID, changed content | Conflict; no second semantic result | conflict test |
| Reordered delivery | Timestamp then event-ID deterministic order | reorder test |
| Crash/interruption after claim | Durable owner-marked failed state and reconciled retry | restart recovery test |
| Runtime deadline | Failed deadline; no result/effect | deadline test |
| Repeated runtime error | Two failures then explicit stop | retry/repeated-error test |
| Kill switch idle/mid-run | Cancelled; audit entry; no continued work | kill-switch test |
| Resume without reconciliation | Policy failure | kill-switch test |
| Telemetry outage | Visible failure before content routing | telemetry-loss test |
| Secret-like content in telemetry | Raw subject/body and values absent | redaction test |
| Telemetry ACL/retention | Unauthorized read denied; expiry purge works | telemetry governance test |
| Ledger deletion/reset/retention | Owner-only operations; state removed | ledger governance tests |
| Permission/policy/runtime/dependency/model/adapter/incident drift | Manifest becomes `needs_retest` | lifecycle tests |
| Authentication loss, 429/5xx, dependency outage, backoff/jitter | N/A: no credential, network, or dependency call |
| Approval denial/expiry/mutation/bypass | N/A for impact: no write/send/approval-consumption path |
| Late/partial write, rollback, compensation | N/A: no side effect or destination |
| Model output malformation/drift | N/A: no model dependency |

N/A is bounded to local-python adapter 0.2.0. Adding a live source, credential, model,
network, schedule, destination, or side effect is a material adapter/risk change that
forces `needs_retest` and makes the corresponding rows applicable.