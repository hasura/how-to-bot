# Failure-injection matrix

| Case | v0.1 treatment |
|---|---|
| Missing/broader permission | Tested; fails closed |
| Malformed/oversized/adversarial input | Tested |
| Duplicate trigger/replay | Tested with example ledger |
| Wrong/ambiguous target | No mutation; general review or sensitive escalation |
| Scope explosion | Tested batch limit |
| Sensitive-data leakage | Output omits raw subject/body |
| Kill switch | Tested before execution |
| Authentication loss, timeout, 429/5xx, late response, partial write, retry storm | Not applicable: no credential, network, or side effect |
| Approval denial/expiry/mutation/bypass | Impact path prohibited; no approval path exists |
| Crash recovery/reconciliation | Documented limitation; durable adapter required |
| Model/tool drift | Deterministic adapter has no model/tool dependency |

“Not applicable” is bounded to the local v0.1 adapter and must be revisited for any live
source, model, network, recurring, or write-capable adapter.
