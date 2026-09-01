from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time

import yaml

from howtobot.inbound_triage import (
    AuthorizationError,
    AuthorizationPolicy,
    CancelledError,
    DeadlineExceededError,
    DurableLedger,
    KillSwitch,
    REQUIRED_SCOPE,
    RequestContext,
    TelemetrySink,
    TriageError,
    triage_one,
)

ROOT = Path(__file__).parent
REQUESTER = "synthetic-user-operator"
OPERATOR = "synthetic-operator"
POLICY_VERSION = "policy-2026-09-01"
NOW = datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc)


def context(requester: str = REQUESTER) -> RequestContext:
    return RequestContext(
        requester_id=requester,
        operator_id=OPERATOR,
        granted_scopes=frozenset({REQUIRED_SCOPE}),
        policy_version=POLICY_VERSION,
    )


def policy_for(events: list[dict]) -> AuthorizationPolicy:
    return AuthorizationPolicy(
        version=POLICY_VERSION,
        record_grants={REQUESTER: frozenset(event["id"] for event in events)},
        source_grants={REQUESTER: frozenset(event["source"] for event in events)},
        record_versions={event["id"]: event["source_version"] for event in events},
    )


def run_cases(cases: list[dict], policy: AuthorizationPolicy) -> list[dict]:
    rows = []
    for case in cases:
        ledger = DurableLedger()
        telemetry = TelemetrySink()
        try:
            result = triage_one(
                case["event"],
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=KillSwitch(owner_id="Anushrut Gupta"),
                evaluation_time=NOW,
            )
            actual = result.to_dict()
            passed = (
                "expected_error" not in case
                and actual["suggested_route"] == case["expected_route"]
                and actual["abstained"] == case["expected_abstained"]
            )
            outcome = "result"
        except TriageError as exc:
            actual = {"error": exc.code}
            passed = case.get("expected_error") == exc.code
            outcome = "error"
        finally:
            ledger.close_and_delete(actor_id="Anushrut Gupta")
        rows.append(
            {
                "case_id": case["case_id"],
                "outcome": outcome,
                "passed": passed,
                "actual": actual,
            }
        )
    return rows


def probe_critical_invariants(cases: list[dict], rows: list[dict], policy: AuthorizationPolicy) -> dict[str, int]:
    failures = {
        "authorization_failures": 0,
        "privacy_leaks": 0,
        "automatic_final_dispositions": 0,
        "duplicate_semantic_outcomes": 0,
        "unsupported_non_abstentions": 0,
        "missed_sensitive_escalations": 0,
        "deadline_or_kill_switch_bypasses": 0,
    }

    # Differently authorized requester must fail before result/state exposure.
    authorized_event = cases[0]["event"]
    denied_ledger = DurableLedger()
    try:
        try:
            triage_one(
                authorized_event,
                context=context("synthetic-other-user"),
                authorization_policy=policy,
                ledger=denied_ledger,
                telemetry=TelemetrySink(),
                kill_switch=KillSwitch(owner_id="Anushrut Gupta"),
                evaluation_time=NOW,
            )
            failures["authorization_failures"] += 1
        except AuthorizationError:
            pass
        if denied_ledger.snapshot(actor_role="independent-reviewer"):
            failures["authorization_failures"] += 1
    finally:
        denied_ledger.close_and_delete(actor_id="Anushrut Gupta")

    successful = [row["actual"] for row in rows if row["outcome"] == "result"]
    raw_values = {
        case["event"]["subject"] for case in cases
    } | {
        case["event"]["body"] for case in cases
    }
    for result in successful:
        serialized = json.dumps(result, sort_keys=True)
        if any(value in serialized for value in raw_values):
            failures["privacy_leaks"] += 1
        if (
            result["status"] != "draft"
            or result["requires_human_disposition"] is not True
            or result["disposition_owner"] != "Anushrut Gupta"
        ):
            failures["automatic_final_dispositions"] += 1

    # Exact replay must reuse one result and one durable record.
    replay_ledger = DurableLedger()
    try:
        first = triage_one(
            authorized_event,
            context=context(),
            authorization_policy=policy,
            ledger=replay_ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id="Anushrut Gupta"),
            evaluation_time=NOW,
        )
        second = triage_one(
            authorized_event,
            context=context(),
            authorization_policy=policy,
            ledger=replay_ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id="Anushrut Gupta"),
            evaluation_time=NOW,
        )
        snapshot = replay_ledger.snapshot(actor_role="independent-reviewer")
        if (
            first.duplicate
            or not second.duplicate
            or first.idempotency_key != second.idempotency_key
            or first.suggested_route != second.suggested_route
            or len(snapshot) != 1
        ):
            failures["duplicate_semantic_outcomes"] += 1
    finally:
        replay_ledger.close_and_delete(actor_id="Anushrut Gupta")

    row_by_id = {row["case_id"]: row for row in rows}
    for case_id in ("unsupported-abstention", "contradictory-abstention"):
        actual = row_by_id[case_id]["actual"]
        if not actual.get("abstained") or actual.get("suggested_resolution") is not None:
            failures["unsupported_non_abstentions"] += 1
    sensitive = row_by_id["sensitive-security"]["actual"]
    if (
        sensitive.get("suggested_route") != "security"
        or not sensitive.get("sensitive_case")
        or sensitive.get("disposition_owner") != "Anushrut Gupta"
    ):
        failures["missed_sensitive_escalations"] += 1

    # Deadline and independently activated idle stop must each prevent a result.
    deadline_ledger = DurableLedger()
    try:
        def delay(stage: str) -> None:
            if stage == "planned":
                time.sleep(0.02)

        try:
            triage_one(
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=deadline_ledger,
                telemetry=TelemetrySink(),
                kill_switch=KillSwitch(owner_id="Anushrut Gupta"),
                evaluation_time=NOW,
                max_runtime_seconds=0.005,
                step_hook=delay,
            )
            failures["deadline_or_kill_switch_bypasses"] += 1
        except DeadlineExceededError:
            pass
    finally:
        deadline_ledger.close_and_delete(actor_id="Anushrut Gupta")

    stop_ledger = DurableLedger()
    try:
        stop = KillSwitch(owner_id="Anushrut Gupta")
        stop.activate(actor_id="Anushrut Gupta", reason="frozen evaluation stop probe")
        try:
            triage_one(
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=stop_ledger,
                telemetry=TelemetrySink(),
                kill_switch=stop,
                evaluation_time=NOW,
            )
            failures["deadline_or_kill_switch_bypasses"] += 1
        except CancelledError:
            pass
    finally:
        stop_ledger.close_and_delete(actor_id="Anushrut Gupta")

    return failures


def main() -> int:
    contract = yaml.safe_load((ROOT / "evaluation.yaml").read_text())
    cases = json.loads((ROOT / "fixtures" / "evaluation.json").read_text())
    events = [case["event"] for case in cases]
    policy = policy_for(events)
    rows = run_cases(cases, policy)
    case_by_id = {case["case_id"]: case for case in cases}

    route_rows = [
        row
        for row in rows
        if "expected_route" in case_by_id[row["case_id"]]
        and not case_by_id[row["case_id"]]["expected_abstained"]
    ]
    abstain_rows = [
        row for row in rows if case_by_id[row["case_id"]].get("expected_abstained") is True
    ]
    exception_rows = [
        row for row in rows if "expected_error" in case_by_id[row["case_id"]]
    ]
    grounded_rows = [
        row
        for row in route_rows
        if row["outcome"] == "result"
        and row["actual"]["evidence"]
        and all(
            evidence["source"]
            and evidence["source_version"]
            and evidence["field"]
            and evidence["start"] < evidence["end"]
            and len(evidence["text_sha256"]) == 64
            for evidence in row["actual"]["evidence"]
        )
    ]
    metric_inputs = {
        "correct_route_rate": (sum(row["passed"] for row in route_rows), len(route_rows)),
        "correct_abstention_rate": (
            sum(row["passed"] for row in abstain_rows),
            len(abstain_rows),
        ),
        "exact_grounding_rate": (len(grounded_rows), len(route_rows)),
        "exception_detection_rate": (
            sum(row["passed"] for row in exception_rows),
            len(exception_rows),
        ),
    }
    metrics = []
    for definition in contract["metrics"]:
        numerator, denominator = metric_inputs[definition["id"]]
        value = numerator / denominator if denominator else 0.0
        metrics.append(
            {
                "id": definition["id"],
                "numerator": numerator,
                "denominator": denominator,
                "value": value,
                "threshold": definition["threshold"],
                "passed": value >= definition["threshold"],
            }
        )

    failure_counts = probe_critical_invariants(cases, rows, policy)
    invariant_definitions = {
        item["id"]: item["maximum_failures"] for item in contract["critical_invariants"]
    }
    invariants = [
        {
            "id": invariant_id,
            "failures": failure_counts[invariant_id],
            "maximum_failures": maximum,
            "passed": failure_counts[invariant_id] <= maximum,
        }
        for invariant_id, maximum in invariant_definitions.items()
    ]
    report = {
        "tutorial_id": contract["tutorial_id"],
        "fixture_version": contract["fixture_version"],
        "frozen_before_run": contract["frozen_before_run"],
        "metrics": metrics,
        "critical_invariants": invariants,
        "cases": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    all_passed = (
        all(row["passed"] for row in metrics)
        and all(row["passed"] for row in invariants)
        and all(row["passed"] for row in rows)
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
