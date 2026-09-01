# Threat model

## Assets and boundaries

Assets: inbound content, reporter privacy, routing integrity, and human disposition
authority. Trust crosses from untrusted event text into deterministic validation and
policy code, then into a private draft viewed by an authorized operator.

## Threats and controls

| Threat | Control |
|---|---|
| Prompt injection in subject/body | Text is treated as data; it cannot alter scopes, tools, or rules |
| Excessive agency | No write/send adapter exists; output is always a human-owned draft |
| Confused deputy / broader identity | Exact required scope; broader or missing scope fails closed |
| Sensitive content routed routinely | Sensitive terms force the security queue |
| Replay | Semantic idempotency key and explicit duplicate result |
| Scope explosion | Batch cardinality and text-size limits |
| Data leakage | Synthetic fixtures, no network, no raw-content logging in output |
| Runaway work | Fixed batch/text/runtime operating envelope and independent kill-switch input |
| Similar/ambiguous target | Pilot suggests a queue only; it does not resolve or mutate records |

Residual risk: keyword routing is illustrative, can miss nuance, and must not be
represented as a production classifier. Live adapters require data-owner review,
durable replay state, privacy controls, and independent reproduction.
