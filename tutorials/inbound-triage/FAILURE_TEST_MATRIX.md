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
| Non-RFC3339 basic, invalid, stale, or future timestamp | Traced validation/policy failure | timestamp tests and v4 evaluation |
| Malformed batch before sort | Governed received → failed validation trace; no raw KeyError | reviewer malformed-batch test |
| Prompt injection | Content remains data; unsupported text abstains | conformance injection test |
| Unsupported evidence | `general-review`, abstained, no resolution | frozen evaluation |
| Equal contradictory route evidence | `general-review`, abstained | frozen evaluation |
| Sensitive evidence | Security transfer to Anushrut Gupta; still draft | conformance/evaluation |
| Serial exact replay | Original semantic result, duplicate=true | serial replay test |
| Concurrent exact replay | One owner and one duplicate | concurrent replay test |
| Same ID, changed content or whitespace | Exact-byte conflict; no second semantic result | conflict and third-review whitespace tests |
| Reordered delivery | Timestamp then event-ID deterministic order | reorder test |
| Crash/interruption after claim | Durable owner-marked failed state, owner_run_id-fenced recovery, stale-owner conflict | restart and reviewer stale-owner tests |
| NaN or infinite runtime | Traced policy failure before work or state publication | third-review finite-runtime tests and v4 evaluation |
| Shared batch deadline | One absolute budget; later item fails rather than receiving a reset clock | third-review batch-budget test and v4 evaluation |
| Oversized batch | Governed batch run ID and received → failed policy trace | third-review oversized-batch test and v4 evaluation |
| Finalization deadline | No durable success and no false success telemetry after deadline | third-review finalization test and v4 evaluation |
| Runtime/step deadline | Caller cannot exceed 30s; all six step ceilings fail visibly; no result/effect | global and per-step timeout tests |
| Repeated runtime error | Two failures then explicit stop | retry/repeated-error test |
| Kill switch idle/mid-run/completion window | Cancelled; generation fence prevents post-activation finalization | kill-switch and reviewer completion-window tests |
| Reconciliation with wrong actor or manufactured state/fingerprint | Authorization/policy failure | third-review reconciliation test and v4 evaluation |
| Resume without ledger-verified reconciliation | Policy failure even when caller passes reconciled=true | reviewer reconciliation test |
| Terminal telemetry outage | No replay-visible result; governed failed state and trace | third-review terminal-telemetry test and v4 evaluation |
| Telemetry outage | Visible failure before content routing | telemetry-loss test |
| Non-ASCII evidence prefix | UTF-8 byte slice resolves to exact grounded term | third-review Unicode-offset test and v4 evaluation |
| Secret-like content in telemetry | Raw subject/body and values absent | redaction test |
| Telemetry reconstruction/ACL/retention | Redacted claim/plan/outcome reconstruct success; unauthorized read denied; expiry purge works | telemetry outcome/governance tests |
| Ledger deletion/reset/retention | Owner-only operations; state removed | ledger governance tests |
| Permission/policy/runtime/dependency/model/adapter/incident drift | Manifest becomes `needs_retest` | lifecycle tests |
| Authentication loss, 429/5xx, dependency outage, backoff/jitter | N/A: no credential, network, or dependency call |
| Approval denial/expiry/mutation/bypass | N/A for impact: no write/send/approval-consumption path |
| Late/partial write, rollback, compensation | N/A: no side effect or destination |
| Model output malformation/drift | N/A: no model dependency |

N/A is bounded to local-python adapter 0.4.0. Adding a live source, credential, model,
network, schedule, destination, or side effect is a material adapter/risk change that
forces `needs_retest` and makes the corresponding rows applicable.