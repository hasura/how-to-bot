from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from howtobot.inbound_triage import (
    AuthorizationPolicy,
    DurableLedger,
    KillSwitch,
    REQUIRED_SCOPE,
    RequestContext,
    TelemetrySink,
    triage_batch,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run.py <events.json>", file=sys.stderr)
        return 2
    events = json.loads(Path(sys.argv[1]).read_text())
    requester = "synthetic-user-operator"
    context = RequestContext(
        requester_id=requester,
        operator_id="synthetic-operator",
        granted_scopes=frozenset({REQUIRED_SCOPE}),
        policy_version="policy-2026-09-01",
    )
    policy = AuthorizationPolicy(
        version=context.policy_version,
        record_grants={requester: frozenset(event["id"] for event in events)},
        source_grants={requester: frozenset(event["source"] for event in events)},
        record_versions={event["id"]: event["source_version"] for event in events},
    )
    ledger = DurableLedger()
    try:
        results = triage_batch(
            events,
            context=context,
            authorization_policy=policy,
            ledger=ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id="Anushrut Gupta"),
            evaluation_time=datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc),
        )
        print(json.dumps(results, indent=2))
    finally:
        ledger.close_and_delete(actor_id="Anushrut Gupta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
