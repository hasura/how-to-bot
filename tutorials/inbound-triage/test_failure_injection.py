from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import time

import pytest

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
    RepeatedErrorStop,
    STEP_TIMEOUT_SECONDS,
    RequestContext,
    TelemetrySink,
    TelemetryUnavailableError,
    ValidationError,
    WORKFLOW_STATES,
    triage_batch,
    triage_one,
)

REQUESTER = "synthetic-user-operator"
OTHER = "synthetic-other-user"
OPERATOR = "synthetic-operator"
POLICY_VERSION = "policy-2026-09-01"
NOW = datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc)


def event(event_id="evt-test", *, reporter=REQUESTER):
    return {
        "id": event_id,
        "received_at": "2026-09-01T19:00:00Z",
        "source": "synthetic",
        "source_version": "fixture-v2",
        "subject": "Invoice question",
        "body": "A synthetic invoice has a charge.",
        "reporter": reporter,
    }


def runtime(items, *, requester=REQUESTER, revoked=False, telemetry_available=True):
    context = RequestContext(
        requester_id=requester,
        operator_id=OPERATOR,
        granted_scopes=frozenset({REQUIRED_SCOPE}),
        policy_version=POLICY_VERSION,
    )
    policy = AuthorizationPolicy(
        version=POLICY_VERSION,
        record_grants={
            REQUESTER: frozenset(item["id"] for item in items if item["reporter"] == REQUESTER),
            OTHER: frozenset(item["id"] for item in items if item["reporter"] == OTHER),
        },
        source_grants={REQUESTER: frozenset({"synthetic"}), OTHER: frozenset({"synthetic"})},
        record_versions={item["id"]: item["source_version"] for item in items},
        revoked_requesters=frozenset({requester}) if revoked else frozenset(),
    )
    return (
        context,
        policy,
        DurableLedger(),
        TelemetrySink(available=telemetry_available),
        KillSwitch(owner_id="Anushrut Gupta"),
    )


def invoke(item, state, **kwargs):
    context, policy, ledger, telemetry, switch = state
    return triage_one(
        item,
        context=context,
        authorization_policy=policy,
        ledger=ledger,
        telemetry=telemetry,
        kill_switch=switch,
        evaluation_time=NOW,
        **kwargs,
    )


def test_serial_exact_replay_reuses_one_semantic_outcome():
    item = event()
    state = runtime([item])
    first = invoke(item, state)
    second = invoke(item, state)
    assert first.duplicate is False
    assert second.duplicate is True
    assert first.idempotency_key == second.idempotency_key
    assert first.suggested_route == second.suggested_route
    assert state[2].snapshot(actor_role="independent-reviewer") == {item["id"]: "succeeded"}


def test_concurrent_exact_replay_is_atomic():
    item = event()
    state = runtime([item])
    owner_started = threading.Event()

    def slow(stage):
        if stage == "executing" and not owner_started.is_set():
            owner_started.set()
            time.sleep(0.08)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(invoke, item, state, step_hook=slow)
        owner_started.wait(timeout=1)
        second = pool.submit(invoke, item, state)
        results = [first.result(), second.result()]
    assert sorted(row.duplicate for row in results) == [False, True]
    assert len({row.idempotency_key for row in results}) == 1


def test_same_event_identity_changed_content_is_conflict():
    item = event()
    state = runtime([item])
    invoke(item, state)
    changed = {**item, "body": "Changed synthetic content with a refund."}
    with pytest.raises(ConflictError):
        invoke(changed, state)


def test_reordered_batch_has_deterministic_order():
    items = [event("evt-b"), event("evt-a")]
    context, policy, ledger, telemetry, switch = runtime(items)
    result = triage_batch(
        list(reversed(items)),
        context=context,
        authorization_policy=policy,
        ledger=ledger,
        telemetry=telemetry,
        kill_switch=switch,
        evaluation_time=NOW,
    )
    assert [row["event_id"] for row in result] == ["evt-a", "evt-b"]


@pytest.mark.parametrize(
    "requester,item,revoked",
    [
        (OTHER, event(), False),
        (REQUESTER, event(reporter=OTHER), False),
        (REQUESTER, event(), True),
    ],
)
def test_current_per_record_authorization_denies_without_content_leak(requester, item, revoked):
    state = runtime([item], requester=requester, revoked=revoked)
    with pytest.raises(AuthorizationError) as exc:
        invoke(item, state)
    assert "invoice" not in str(exc.value).casefold()
    trace = state[3].events_for(exc.value.run_id, actor_role="independent-reviewer")
    assert trace[-1]["state"] == "failed"
    assert trace[-1]["code"] == "authorization"
    assert "subject" not in repr(trace).casefold()
    assert "body" not in repr(trace).casefold()


def test_stale_malformed_and_future_timestamps_fail_closed():
    for received_at, error in [
        ("not-a-time", ValidationError),
        ("2001-01-01T00:00:00Z", PolicyError),
        ("2026-09-02T00:00:00Z", PolicyError),
    ]:
        item = {**event(), "id": f"evt-{received_at[:4]}", "received_at": received_at}
        state = runtime([item])
        with pytest.raises(error):
            invoke(item, state)


def test_malformed_and_oversized_content_are_rejected():
    broken = event()
    del broken["body"]
    with pytest.raises(ValidationError):
        invoke(broken, runtime([broken]))
    oversized = event("evt-large")
    oversized["body"] = "x" * 4_001
    with pytest.raises(PolicyError):
        invoke(oversized, runtime([oversized]))


def test_scope_and_batch_limits_are_enforced():
    item = event()
    context, policy, ledger, telemetry, switch = runtime([item])
    for scopes in (frozenset(), frozenset({REQUIRED_SCOPE, "records:write"}), frozenset({"admin"})):
        bad_context = RequestContext(REQUESTER, OPERATOR, scopes, POLICY_VERSION)
        with pytest.raises(AuthorizationError):
            triage_one(
                item,
                context=bad_context,
                authorization_policy=policy,
                ledger=ledger,
                telemetry=telemetry,
                kill_switch=switch,
                evaluation_time=NOW,
            )
    many = [event(f"evt-{i:02}") for i in range(26)]
    many_state = runtime(many)
    with pytest.raises(PolicyError):
        triage_batch(
            many,
            context=many_state[0],
            authorization_policy=many_state[1],
            evaluation_time=NOW,
        )


def test_runtime_deadline_is_enforced():
    item = event()
    state = runtime([item])

    def delay(stage):
        if stage == "planned":
            time.sleep(0.03)

    with pytest.raises(DeadlineExceededError):
        invoke(item, state, max_runtime_seconds=0.01, step_hook=delay)


def test_idle_and_midrun_kill_switch_and_controlled_resume():
    item = event()
    state = runtime([item])
    switch = state[4]
    with pytest.raises(AuthorizationError):
        switch.activate(actor_id="not-owner", reason="forged")
    switch.activate(actor_id="Anushrut Gupta", reason="idle stop test")
    with pytest.raises(CancelledError):
        invoke(item, state)
    with pytest.raises(PolicyError):
        switch.resume(actor_id="Anushrut Gupta", reconciled=False, reason="unsafe")
    switch.resume(actor_id="Anushrut Gupta", reconciled=True, reason="idle reconciled", ledger=state[2])

    midrun = event("evt-midrun")
    state2 = runtime([midrun])
    started = threading.Event()

    def delay(stage):
        if stage == "executing":
            started.set()
            time.sleep(0.05)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(invoke, midrun, state2, step_hook=delay)
        started.wait(timeout=1)
        state2[4].activate(actor_id="Anushrut Gupta", reason="mid-run stop test")
        with pytest.raises(CancelledError):
            future.result()
    assert state2[2].snapshot(actor_role="independent-reviewer")[midrun["id"]] == "cancelled"
    assert [row["action"] for row in state2[4].audit_log()] == ["activated"]
    state2[2].reconcile(midrun["id"])
    state2[4].resume(actor_id="Anushrut Gupta", reconciled=True, reason="run reconciled", ledger=state2[2])
    recovered = invoke(midrun, state2)
    assert recovered.terminal_state == "reconciled"
    assert state2[4].audit_log()[-1]["action"] == "resumed"


def test_failed_retry_recovery_and_repeated_error_stop_are_reconstructable():
    item = event()
    state = runtime([item])

    def fail(stage):
        if stage == "executing":
            raise RuntimeError("synthetic failure")

    for _ in range(2):
        with pytest.raises(PolicyError):
            invoke(item, state, step_hook=fail)
    with pytest.raises(RepeatedErrorStop):
        invoke(item, state)

    recover_item = event("evt-recover")
    recover_state = runtime([recover_item])
    with pytest.raises(PolicyError):
        invoke(recover_item, recover_state, step_hook=fail)
    recovered = invoke(recover_item, recover_state)
    assert recovered.terminal_state == "reconciled"
    all_events = recover_state[3].all_events(actor_role="independent-reviewer")
    assert any(row["kind"] == "retry" for row in all_events)
    assert any(row["state"] == "failed" for row in all_events)
    assert any(row["state"] == "reconciled" for row in all_events)


def test_success_denial_failure_cancel_and_recovery_can_be_reconstructed():
    success = event("evt-success")
    success_state = runtime([success])
    success_result = invoke(success, success_state)

    denied = event("evt-denied", reporter=OTHER)
    denied_state = runtime([denied], requester=REQUESTER)
    with pytest.raises(AuthorizationError) as denied_exc:
        invoke(denied, denied_state)

    failed = event("evt-failed")
    failed_state = runtime([failed])
    with pytest.raises(PolicyError) as failed_exc:
        invoke(failed, failed_state, step_hook=lambda _: (_ for _ in ()).throw(RuntimeError()))

    cancelled = event("evt-cancelled")
    cancelled_state = runtime([cancelled])
    cancelled_state[4].activate(actor_id="Anushrut Gupta", reason="test")
    with pytest.raises(CancelledError) as cancelled_exc:
        invoke(cancelled, cancelled_state)

    for telemetry, run_id, expected in [
        (success_state[3], success_result.run_id, "succeeded"),
        (denied_state[3], denied_exc.value.run_id, "failed"),
        (failed_state[3], failed_exc.value.run_id, "failed"),
        (cancelled_state[3], cancelled_exc.value.run_id, "cancelled"),
    ]:
        trace = telemetry.events_for(run_id, actor_role="independent-reviewer")
        assert trace
        assert trace[-1]["state"] == expected
        assert all(row["requester_id"] and row["operator_id"] for row in trace)


def test_telemetry_loss_is_visible_and_safe():
    item = event()
    state = runtime([item], telemetry_available=False)
    with pytest.raises(TelemetryUnavailableError):
        invoke(item, state)
    assert state[2].snapshot(actor_role="independent-reviewer") == {}


def test_telemetry_redacts_untrusted_content():
    item = {**event(), "body": "password=TOP-SECRET token=ABC invoice"}
    state = runtime([item])
    result = invoke(item, state)
    serialized = repr(state[3].all_events(actor_role="independent-reviewer"))
    assert "TOP-SECRET" not in serialized
    assert "token=ABC" not in serialized
    assert "password=" not in serialized
    assert result.suggested_route == "security"


def test_state_machine_contract_contains_all_frozen_states():
    assert WORKFLOW_STATES == {
        "received",
        "validated",
        "planned",
        "awaiting_approval",
        "executing",
        "succeeded",
        "partially_succeeded",
        "failed",
        "cancelled",
        "reconciled",
    }


def test_ledger_delete_and_reset_are_owner_controlled():
    item = event()
    state = runtime([item])
    invoke(item, state)
    with pytest.raises(AuthorizationError):
        state[2].snapshot(actor_role="unauthorized")
    with pytest.raises(AuthorizationError):
        state[2].delete(item["id"], actor_id="not-owner")
    state[2].delete(item["id"], actor_id="Anushrut Gupta")
    assert state[2].snapshot(actor_role="independent-reviewer") == {}
    invoke(item, state)
    state[2].reset(actor_id="Anushrut Gupta")
    assert state[2].snapshot(actor_role="independent-reviewer") == {}

def test_source_version_and_policy_version_drift_fail_closed():
    item = event()
    state = runtime([item])
    drifted_source = {**item, "source_version": "fixture-v3"}
    with pytest.raises(AuthorizationError):
        invoke(drifted_source, state)
    drifted_context = RequestContext(
        REQUESTER,
        OPERATOR,
        frozenset({REQUIRED_SCOPE}),
        "policy-stale",
    )
    with pytest.raises(AuthorizationError):
        triage_one(
            item,
            context=drifted_context,
            authorization_policy=state[1],
            ledger=state[2],
            telemetry=state[3],
            kill_switch=state[4],
            evaluation_time=NOW,
        )


def test_durable_interrupted_claim_recovers_after_adapter_restart(tmp_path):
    item = event()
    state = runtime([item])
    ledger_path = tmp_path / "ledger.sqlite3"
    first_process = DurableLedger(ledger_path)
    fingerprint = __import__("hashlib").sha256(
        "\x1f".join(
            item[field].strip()
            for field in ("received_at", "source", "source_version", "subject", "body", "reporter")
        ).encode()
    ).hexdigest()
    mode, _, _ = first_process.claim(
        event_id=item["id"],
        fingerprint=fingerprint,
        run_id="crashed-run",
        deadline=time.monotonic() + 1,
    )
    assert mode == "owner"

    restarted = DurableLedger(ledger_path)
    restarted.mark_interrupted_for_recovery(item["id"], actor_id="Anushrut Gupta")
    restarted_state = (state[0], state[1], restarted, state[3], state[4])
    recovered = invoke(item, restarted_state)
    assert recovered.terminal_state == "reconciled"
    assert restarted.snapshot(actor_role="independent-reviewer") == {item["id"]: "reconciled"}


def test_telemetry_acl_and_retention_are_enforced():
    item = event()
    state = runtime([item])
    result = invoke(item, state)
    with pytest.raises(AuthorizationError):
        state[3].events_for(result.run_id, actor_role="unauthorized")
    assert state[3].events_for(result.run_id, actor_role="independent-reviewer")
    purged = state[3].purge_expired(
        actor_role="tutorial-maintainer",
        now=datetime(2027, 11, 1, tzinfo=timezone.utc),
    )
    assert purged > 0
    assert state[3].all_events(actor_role="independent-reviewer") == []


def test_ledger_retention_is_owner_enforced():
    item = event()
    state = runtime([item])
    invoke(item, state)
    with pytest.raises(AuthorizationError):
        state[2].purge_expired(actor_id="not-owner", now=datetime(2027, 1, 1, tzinfo=timezone.utc))
    purged = state[2].purge_expired(
        actor_id="Anushrut Gupta",
        now=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    assert purged == 1
    assert state[2].snapshot(actor_role="independent-reviewer") == {}


# Canonicalized from the second independent Gate 2 review. These attacks must remain.
def test_reviewer_probe_rejects_iso_basic_timestamp():
    item = {**event("evt-basic-time"), "received_at": "20260901T190000+00:00"}
    with pytest.raises(ValidationError):
        invoke(item, runtime([item]))


def test_reviewer_probe_runtime_ceiling_cannot_be_expanded():
    item = event("evt-runtime-ceiling")
    state = runtime([item])
    with pytest.raises(PolicyError) as exc:
        invoke(item, state, max_runtime_seconds=3_630)
    trace = state[3].events_for(
        exc.value.run_id,
        actor_role="independent-reviewer",
    )
    assert [row["state"] for row in trace] == ["received", "failed"]
    assert trace[-1]["code"] == "policy"


def test_reviewer_probe_resume_requires_ledger_verified_reconciliation():
    item = event("evt-unverified-resume")
    state = runtime([item])
    ledger = state[2]
    switch = state[4]
    fingerprint = __import__("hashlib").sha256(
        "\x1f".join(
            item[field].strip()
            for field in ("received_at", "source", "source_version", "subject", "body", "reporter")
        ).encode()
    ).hexdigest()
    mode, _, _ = ledger.claim(
        event_id=item["id"],
        fingerprint=fingerprint,
        run_id="cancelled-run",
        deadline=time.monotonic() + 1,
    )
    assert mode == "owner"
    ledger.abort(item["id"], "cancelled", run_id="cancelled-run")
    switch.activate(actor_id="Anushrut Gupta", reason="independent resume attack")
    with pytest.raises(PolicyError):
        switch.resume(
            actor_id="Anushrut Gupta",
            reconciled=True,
            reason="caller assertion is not durable proof",
            ledger=ledger,
        )


def test_reviewer_probe_stale_owner_cannot_complete_after_recovery_owner():
    item = event("evt-stale-owner")
    state = runtime([item])
    stale_started = threading.Event()
    release_stale = threading.Event()

    def pause_stale(stage):
        if stage == "executing":
            stale_started.set()
            assert release_stale.wait(timeout=2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        stale = pool.submit(invoke, item, state, step_hook=pause_stale)
        assert stale_started.wait(timeout=1)
        state[2].mark_interrupted_for_recovery(item["id"], actor_id="Anushrut Gupta")
        recovered = pool.submit(invoke, item, state).result(timeout=2)
        release_stale.set()
        with pytest.raises(ConflictError):
            stale.result(timeout=2)

    assert recovered.duplicate is False
    assert recovered.terminal_state == "reconciled"
    assert state[2].snapshot(actor_role="independent-reviewer") == {
        item["id"]: "reconciled"
    }


def test_reviewer_probe_kill_activation_during_completion_prevents_success():
    item = event("evt-completion-kill")
    state = runtime([item])
    entered_completion = threading.Event()
    release_completion = threading.Event()
    original_complete = state[2].complete

    def delayed_complete(*args, **kwargs):
        entered_completion.set()
        assert release_completion.wait(timeout=2)
        return original_complete(*args, **kwargs)

    state[2].complete = delayed_complete
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(invoke, item, state)
        assert entered_completion.wait(timeout=1)
        state[4].activate(actor_id="Anushrut Gupta", reason="completion-window attack")
        release_completion.set()
        with pytest.raises(CancelledError):
            running.result(timeout=2)

    assert state[2].snapshot(actor_role="independent-reviewer") == {
        item["id"]: "cancelled"
    }


def test_reviewer_probe_malformed_batch_is_traced_validation_failure():
    item = event("evt-malformed-batch")
    del item["received_at"]
    context, policy, ledger, telemetry, switch = runtime([item])
    with pytest.raises(ValidationError) as exc:
        triage_batch(
            [item],
            context=context,
            authorization_policy=policy,
            ledger=ledger,
            telemetry=telemetry,
            kill_switch=switch,
            evaluation_time=NOW,
        )
    trace = telemetry.events_for(exc.value.run_id, actor_role="independent-reviewer")
    assert trace
    assert trace[0]["state"] == "received"
    assert trace[-1]["state"] == "failed"
    assert trace[-1]["code"] == "validation"



@pytest.mark.parametrize(
    ("step", "stage"),
    [
        ("authorize-record", "authorized"),
        ("validate-event", "validated"),
        ("claim-intent", "claimed"),
        ("plan-route", "classified"),
        ("record-draft", "recording"),
    ],
)
def test_each_declared_step_timeout_is_enforced(monkeypatch, step, stage):
    item = event(f"evt-timeout-{step}")
    state = runtime([item])
    monkeypatch.setitem(STEP_TIMEOUT_SECONDS, step, 0.005)

    def delay(current_stage):
        if current_stage == stage:
            time.sleep(0.01)

    with pytest.raises(DeadlineExceededError):
        invoke(item, state, step_hook=delay)


def test_recovery_step_timeout_is_enforced(monkeypatch):
    item = event("evt-timeout-recovery")
    state = runtime([item])

    def fail(stage):
        if stage == "executing":
            raise RuntimeError("create recoverable failure")

    with pytest.raises(PolicyError):
        invoke(item, state, step_hook=fail)

    monkeypatch.setitem(STEP_TIMEOUT_SECONDS, "recover-run", 0.005)

    def delay(stage):
        if stage == "executing":
            time.sleep(0.01)

    with pytest.raises(DeadlineExceededError):
        invoke(item, state, step_hook=delay)


def test_success_outcome_is_reconstructable_from_redacted_telemetry():
    item = event("evt-telemetry-outcome")
    state = runtime([item])
    result = invoke(item, state)
    trace = state[3].events_for(
        result.run_id,
        actor_role="independent-reviewer",
    )
    claim = next(row for row in trace if row["kind"] == "claim")
    plan = next(row for row in trace if row["kind"] == "plan")
    outcome = next(row for row in trace if row["kind"] == "outcome")
    assert claim["owner_run_id"] == result.run_id
    assert plan["suggested_route"] == result.suggested_route
    assert plan["reason_codes"] == result.reason_codes
    assert plan["evidence_count"] == len(result.evidence)
    assert outcome["outcome_status"] == "draft"
    assert outcome["terminal_state"] == result.terminal_state
    assert outcome["duplicate"] is False
    assert "subject" not in repr(trace).casefold()
    assert "body" not in repr(trace).casefold()



def test_staged_result_is_not_replay_visible_before_finalization():
    item = event("evt-staged-result")
    state = runtime([item])
    entered_finalization = threading.Event()
    release_finalization = threading.Event()
    original_finalize = state[2].finalize

    def delayed_finalize(*args, **kwargs):
        entered_finalization.set()
        assert release_finalization.wait(timeout=2)
        return original_finalize(*args, **kwargs)

    state[2].finalize = delayed_finalize
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(invoke, item, state)
        assert entered_finalization.wait(timeout=1)
        replay = pool.submit(invoke, item, state)
        time.sleep(0.03)
        assert replay.done() is False
        release_finalization.set()
        results = [owner.result(timeout=2), replay.result(timeout=2)]

    assert sorted(result.duplicate for result in results) == [False, True]
    assert state[2].snapshot(actor_role="independent-reviewer") == {
        item["id"]: "succeeded"
    }
