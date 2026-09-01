from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import yaml
import howtobot.inbound_triage as triage_module

from howtobot.inbound_triage import (
    AuthorizationError,
    AuthorizationPolicy,
    CancelledError,
    ConflictError,
    DeadlineExceededError,
    DurableLedger,
    KillSwitch,
    PolicyError,
    REQUIRED_SCOPE,
    RequestContext,
    TelemetrySink,
    TelemetryUnavailableError,
    TriageError,
    ValidationError,
    _fingerprint,
    triage_batch,
    triage_one,
)

ROOT = Path(__file__).parent
REQUESTER = "synthetic-user-operator"
OPERATOR = "synthetic-operator"
POLICY_VERSION = "policy-2026-09-01"
OWNER = "Anushrut Gupta"
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


def event_fingerprint(event: dict) -> str:
    return _fingerprint(event)


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
                kill_switch=KillSwitch(owner_id=OWNER),
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
            ledger.close_and_delete(actor_id=OWNER)
        rows.append(
            {
                "case_id": case["case_id"],
                "outcome": outcome,
                "passed": passed,
                "actual": actual,
            }
        )
    return rows


def run_adversarial_probes(
    authorized_event: dict,
    policy: AuthorizationPolicy,
) -> list[dict]:
    probes: list[dict] = []

    basic = {**authorized_event, "received_at": "20260901T190000+00:00"}
    ledger = DurableLedger()
    try:
        try:
            triage_one(
                basic,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=TelemetrySink(),
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
            )
            passed = False
        except ValidationError:
            passed = True
        probes.append({"id": "strict_rfc3339", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    telemetry = TelemetrySink()
    try:
        try:
            triage_one(
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
                max_runtime_seconds=3_630,
            )
            passed = False
        except PolicyError as exc:
            trace = telemetry.events_for(
                exc.run_id,
                actor_role="independent-reviewer",
            )
            passed = bool(
                [row["state"] for row in trace] == ["received", "failed"]
                and trace[-1]["code"] == "policy"
            )
        probes.append({"id": "runtime_ceiling", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    switch = KillSwitch(owner_id=OWNER)
    try:
        mode, _, _ = ledger.claim(
            event_id=authorized_event["id"],
            fingerprint=event_fingerprint(authorized_event),
            run_id="cancelled-evaluation-owner",
            deadline=time.monotonic() + 1,
        )
        assert mode == "owner"
        ledger.abort(
            authorized_event["id"],
            "cancelled",
            run_id="cancelled-evaluation-owner",
        )
        switch.activate(actor_id=OWNER, reason="evaluation reconciliation probe")
        try:
            switch.resume(
                actor_id=OWNER,
                reconciled=True,
                reason="unverified assertion",
                ledger=ledger,
            )
            passed = False
        except PolicyError:
            passed = True
        probes.append({"id": "ledger_verified_resume", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    telemetry = TelemetrySink()
    switch = KillSwitch(owner_id=OWNER)
    stale_started = threading.Event()
    release_stale = threading.Event()

    def pause_stale(stage: str) -> None:
        if stage == "executing":
            stale_started.set()
            if not release_stale.wait(timeout=2):
                raise RuntimeError("stale-owner probe synchronization failed")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            stale = pool.submit(
                triage_one,
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=switch,
                evaluation_time=NOW,
                step_hook=pause_stale,
            )
            started = stale_started.wait(timeout=1)
            if started:
                ledger.mark_interrupted_for_recovery(
                    authorized_event["id"],
                    actor_id=OWNER,
                )
                recovered = pool.submit(
                    triage_one,
                    authorized_event,
                    context=context(),
                    authorization_policy=policy,
                    ledger=ledger,
                    telemetry=telemetry,
                    kill_switch=switch,
                    evaluation_time=NOW,
                ).result(timeout=2)
                release_stale.set()
                try:
                    stale.result(timeout=2)
                    stale_rejected = False
                except ConflictError:
                    stale_rejected = True
                passed = (
                    stale_rejected
                    and recovered.duplicate is False
                    and recovered.terminal_state == "reconciled"
                    and ledger.snapshot(actor_role="independent-reviewer")
                    == {authorized_event["id"]: "reconciled"}
                )
            else:
                release_stale.set()
                passed = False
        probes.append({"id": "stale_owner_fencing", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    telemetry = TelemetrySink()
    switch = KillSwitch(owner_id=OWNER)
    entered_completion = threading.Event()
    release_completion = threading.Event()
    original_complete = ledger.complete

    def delayed_complete(*args, **kwargs):
        entered_completion.set()
        if not release_completion.wait(timeout=2):
            raise RuntimeError("completion-window probe synchronization failed")
        return original_complete(*args, **kwargs)

    ledger.complete = delayed_complete
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(
                triage_one,
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=switch,
                evaluation_time=NOW,
            )
            entered = entered_completion.wait(timeout=1)
            if entered:
                switch.activate(actor_id=OWNER, reason="evaluation completion-window probe")
                release_completion.set()
                try:
                    running.result(timeout=2)
                    cancelled = False
                except CancelledError:
                    cancelled = True
                passed = (
                    cancelled
                    and ledger.snapshot(actor_role="independent-reviewer")
                    == {authorized_event["id"]: "cancelled"}
                )
            else:
                release_completion.set()
                passed = False
        probes.append({"id": "completion_window_kill", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    malformed = {**authorized_event}
    del malformed["received_at"]
    ledger = DurableLedger()
    telemetry = TelemetrySink()
    try:
        try:
            triage_batch(
                [malformed],
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
            )
            passed = False
        except ValidationError as exc:
            trace = telemetry.events_for(
                exc.run_id,
                actor_role="independent-reviewer",
            )
            passed = bool(
                trace
                and trace[0]["state"] == "received"
                and trace[-1]["state"] == "failed"
                and trace[-1]["code"] == "validation"
            )
        probes.append({"id": "malformed_batch_trace", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    # Third-review probes: these independently execute the eight newly fixed attacks.
    ledger = DurableLedger()
    telemetry = TelemetrySink()
    try:
        try:
            triage_one(
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
                max_runtime_seconds=float("nan"),
            )
            passed = False
        except PolicyError as exc:
            trace = telemetry.events_for(exc.run_id, actor_role="independent-reviewer")
            passed = bool(trace and trace[-1]["code"] == "policy" and not ledger.snapshot(
                actor_role="independent-reviewer"
            ))
        probes.append({"id": "finite_runtime", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    original_finalize = ledger.finalize
    original_monotonic = triage_module.time.monotonic
    finalization_clock = {"now": 100.0}
    triage_module.time.monotonic = lambda: finalization_clock["now"]

    def delayed_finalize(*args, **kwargs):
        finalization_clock["now"] += 0.012
        return original_finalize(*args, **kwargs)

    ledger.finalize = delayed_finalize
    try:
        try:
            triage_one(
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=TelemetrySink(),
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
                max_runtime_seconds=0.01,
            )
            passed = False
        except DeadlineExceededError:
            passed = ledger.snapshot(actor_role="independent-reviewer").get(
                authorized_event["id"]
            ) == "failed"
        probes.append({"id": "finalization_deadline", "passed": passed})
    finally:
        triage_module.time.monotonic = original_monotonic
        ledger.close_and_delete(actor_id=OWNER)

    class FailTerminalOnce(TelemetrySink):
        def __init__(self):
            super().__init__()
            self.failed = False

        def publish_with_terminal_events(self, events, *, publish):
            if not self.failed:
                self.failed = True
                raise TelemetryUnavailableError("synthetic terminal telemetry outage")
            return super().publish_with_terminal_events(events, publish=publish)

    ledger = DurableLedger()
    telemetry = FailTerminalOnce()
    try:
        try:
            triage_one(
                authorized_event,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
            )
            passed = False
        except TelemetryUnavailableError as exc:
            trace = telemetry.events_for(exc.run_id, actor_role="independent-reviewer")
            passed = bool(
                ledger.snapshot(actor_role="independent-reviewer").get(
                    authorized_event["id"]
                ) == "failed"
                and trace
                and trace[-1]["state"] == "failed"
                and not any(row["state"] == "succeeded" for row in trace)
            )
        probes.append({"id": "prepublication_terminal_telemetry", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    batch_events = [
        {**authorized_event, "id": "eval-batch-a"},
        {**authorized_event, "id": "eval-batch-b"},
    ]
    batch_policy = policy_for(batch_events)
    ledger = DurableLedger()
    original_route = triage_module._route
    original_monotonic = triage_module.time.monotonic
    batch_clock = {"now": 100.0}
    triage_module.time.monotonic = lambda: batch_clock["now"]

    def slow_route(item):
        batch_clock["now"] += 0.018
        return original_route(item)

    triage_module._route = slow_route
    try:
        try:
            triage_batch(
                batch_events,
                context=context(),
                authorization_policy=batch_policy,
                ledger=ledger,
                telemetry=TelemetrySink(),
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
                max_runtime_seconds=0.03,
            )
            passed = False
        except DeadlineExceededError:
            snapshot = ledger.snapshot(actor_role="independent-reviewer")
            passed = (
                snapshot.get("eval-batch-a") == "succeeded"
                and snapshot.get("eval-batch-b") == "failed"
            )
        probes.append({"id": "shared_batch_deadline", "passed": passed})
    finally:
        triage_module._route = original_route
        triage_module.time.monotonic = original_monotonic
        ledger.close_and_delete(actor_id=OWNER)

    oversized = [
        {**authorized_event, "id": f"eval-oversized-{index:02}"}
        for index in range(26)
    ]
    ledger = DurableLedger()
    telemetry = TelemetrySink()
    try:
        try:
            triage_batch(
                oversized,
                context=context(),
                authorization_policy=policy_for(oversized),
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
            )
            passed = False
        except PolicyError as exc:
            trace = telemetry.events_for(exc.run_id, actor_role="independent-reviewer")
            passed = bool(
                exc.run_id
                and [(row["state"], row["code"]) for row in trace]
                == [("received", "received"), ("failed", "policy")]
            )
        probes.append({"id": "oversized_batch_trace", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    try:
        mode, _, _ = ledger.claim(
            event_id=authorized_event["id"],
            fingerprint=_fingerprint(authorized_event),
            run_id="reconcile-evaluation-owner",
            deadline=time.monotonic() + 1,
        )
        assert mode == "owner"
        ledger.abort(
            authorized_event["id"],
            "failed",
            run_id="reconcile-evaluation-owner",
        )
        denied = mismatched = False
        try:
            ledger.reconcile(
                authorized_event["id"],
                actor_id="not-owner",
                expected_fingerprint=_fingerprint(authorized_event),
                expected_terminal_state="failed",
                reason="forged",
            )
        except AuthorizationError:
            denied = True
        try:
            ledger.reconcile(
                authorized_event["id"],
                actor_id=OWNER,
                expected_fingerprint="0" * 64,
                expected_terminal_state="failed",
                reason="manufactured",
            )
        except PolicyError:
            mismatched = True
        ledger.reconcile(
            authorized_event["id"],
            actor_id=OWNER,
            expected_fingerprint=_fingerprint(authorized_event),
            expected_terminal_state="failed",
            reason="verified synthetic no-side-effect adapter",
        )
        passed = (
            denied
            and mismatched
            and ledger.snapshot(actor_role="independent-reviewer").get(
                authorized_event["id"]
            ) == "reconciled"
        )
        probes.append(
            {"id": "authorized_evidence_bound_reconciliation", "passed": passed}
        )
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    unicode_event = {
        **authorized_event,
        "id": "eval-unicode",
        "subject": "Café ☕ invoice question",
    }
    ledger = DurableLedger()
    try:
        result = triage_one(
            unicode_event,
            context=context(),
            authorization_policy=policy_for([unicode_event]),
            ledger=ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id=OWNER),
            evaluation_time=NOW,
        )
        span = next(item for item in result.evidence if item.field == "subject")
        source_bytes = unicode_event["subject"].encode("utf-8")
        passed = (
            source_bytes[span.start:span.end].decode("utf-8").casefold() == "invoice"
            and span.start != unicode_event["subject"].casefold().index("invoice")
        )
        probes.append({"id": "utf8_byte_offsets", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    ledger = DurableLedger()
    try:
        triage_one(
            authorized_event,
            context=context(),
            authorization_policy=policy,
            ledger=ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id=OWNER),
            evaluation_time=NOW,
        )
        changed = {**authorized_event, "body": authorized_event["body"] + " "}
        try:
            triage_one(
                changed,
                context=context(),
                authorization_policy=policy,
                ledger=ledger,
                telemetry=TelemetrySink(),
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
            )
            passed = False
        except ConflictError:
            passed = True
        probes.append({"id": "exact_payload_identity", "passed": passed})
    finally:
        ledger.close_and_delete(actor_id=OWNER)

    return probes


def probe_critical_invariants(
    cases: list[dict],
    rows: list[dict],
    policy: AuthorizationPolicy,
    adversarial_probes: list[dict],
) -> dict[str, int]:
    failures = {
        "authorization_failures": 0,
        "privacy_leaks": 0,
        "automatic_final_dispositions": 0,
        "duplicate_semantic_outcomes": 0,
        "unsupported_non_abstentions": 0,
        "missed_sensitive_escalations": 0,
        "deadline_or_kill_switch_bypasses": 0,
        "malformed_input_bypasses": 0,
        "unreconciled_resume_bypasses": 0,
    }

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
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
            )
            failures["authorization_failures"] += 1
        except AuthorizationError:
            pass
        if denied_ledger.snapshot(actor_role="independent-reviewer"):
            failures["authorization_failures"] += 1
    finally:
        denied_ledger.close_and_delete(actor_id=OWNER)

    successful = [row["actual"] for row in rows if row["outcome"] == "result"]
    raw_values = {case["event"]["subject"] for case in cases} | {
        case["event"]["body"] for case in cases
    }
    for result in successful:
        serialized = json.dumps(result, sort_keys=True)
        if any(value in serialized for value in raw_values):
            failures["privacy_leaks"] += 1
        if (
            result["status"] != "draft"
            or result["requires_human_disposition"] is not True
            or result["disposition_owner"] != OWNER
        ):
            failures["automatic_final_dispositions"] += 1

    replay_ledger = DurableLedger()
    try:
        first = triage_one(
            authorized_event,
            context=context(),
            authorization_policy=policy,
            ledger=replay_ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id=OWNER),
            evaluation_time=NOW,
        )
        second = triage_one(
            authorized_event,
            context=context(),
            authorization_policy=policy,
            ledger=replay_ledger,
            telemetry=TelemetrySink(),
            kill_switch=KillSwitch(owner_id=OWNER),
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
        replay_ledger.close_and_delete(actor_id=OWNER)

    row_by_id = {row["case_id"]: row for row in rows}
    for case_id in ("unsupported-abstention", "contradictory-abstention"):
        actual = row_by_id[case_id]["actual"]
        if not actual.get("abstained") or actual.get("suggested_resolution") is not None:
            failures["unsupported_non_abstentions"] += 1
    sensitive = row_by_id["sensitive-security"]["actual"]
    if (
        sensitive.get("suggested_route") != "security"
        or not sensitive.get("sensitive_case")
        or sensitive.get("disposition_owner") != OWNER
    ):
        failures["missed_sensitive_escalations"] += 1

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
                kill_switch=KillSwitch(owner_id=OWNER),
                evaluation_time=NOW,
                max_runtime_seconds=0.005,
                step_hook=delay,
            )
            failures["deadline_or_kill_switch_bypasses"] += 1
        except DeadlineExceededError:
            pass
    finally:
        deadline_ledger.close_and_delete(actor_id=OWNER)

    stop_ledger = DurableLedger()
    try:
        stop = KillSwitch(owner_id=OWNER)
        stop.activate(actor_id=OWNER, reason="frozen evaluation stop probe")
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
        stop_ledger.close_and_delete(actor_id=OWNER)

    probe_pass = {row["id"]: row["passed"] for row in adversarial_probes}
    failures["duplicate_semantic_outcomes"] += int(
        not probe_pass["stale_owner_fencing"]
    )
    failures["deadline_or_kill_switch_bypasses"] += sum(
        int(not probe_pass[probe_id])
        for probe_id in ("runtime_ceiling", "completion_window_kill")
    )
    failures["malformed_input_bypasses"] += sum(
        int(not probe_pass[probe_id])
        for probe_id in ("strict_rfc3339", "malformed_batch_trace")
    )
    failures["unreconciled_resume_bypasses"] += int(
        not probe_pass["ledger_verified_resume"]
    )
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

    adversarial_probes = run_adversarial_probes(events[0], policy)
    declared_probes = {
        item["id"] for item in contract["adversarial_probes"] if item["required_pass"]
    }
    actual_probes = {item["id"] for item in adversarial_probes}
    if actual_probes != declared_probes:
        raise ValueError("evaluation probe implementation does not match frozen contract")
    failure_counts = probe_critical_invariants(
        cases,
        rows,
        policy,
        adversarial_probes,
    )
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
    passed_probes = sum(row["passed"] for row in adversarial_probes)
    report = {
        "tutorial_id": contract["tutorial_id"],
        "fixture_version": contract["fixture_version"],
        "frozen_before_run": contract["frozen_before_run"],
        "metrics": metrics,
        "critical_invariants": invariants,
        "adversarial_summary": {
            "passed": passed_probes,
            "total": len(adversarial_probes),
        },
        "adversarial_probes": adversarial_probes,
        "cases": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    all_passed = (
        all(row["passed"] for row in metrics)
        and all(row["passed"] for row in invariants)
        and all(row["passed"] for row in adversarial_probes)
        and all(row["passed"] for row in rows)
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())