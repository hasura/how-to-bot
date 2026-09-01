import pytest

from howtobot.inbound_triage import (
    AuthorizationError,
    CancelledError,
    InMemoryLedger,
    PolicyError,
    REQUIRED_SCOPE,
    ValidationError,
    triage_batch,
    triage_one,
)


def event(event_id="evt-test"):
    return {
        "id": event_id,
        "received_at": "2026-08-31T13:00:00Z",
        "source": "synthetic",
        "subject": "Invoice question",
        "body": "A synthetic invoice has a charge.",
    }


def test_duplicate_replay():
    ledger = InMemoryLedger()
    first = triage_one(event(), granted_scopes={REQUIRED_SCOPE}, ledger=ledger)
    second = triage_one(event(), granted_scopes={REQUIRED_SCOPE}, ledger=ledger)
    assert first.duplicate is False
    assert second.duplicate is True
    assert first.idempotency_key == second.idempotency_key
    assert first.suggested_route == second.suggested_route


@pytest.mark.parametrize("scopes", [set(), {REQUIRED_SCOPE, "records:write"}, {"admin"}])
def test_permission_denial_has_no_fallback(scopes):
    with pytest.raises(AuthorizationError):
        triage_one(event(), granted_scopes=scopes, ledger=InMemoryLedger())


def test_malformed_input_is_quarantined():
    broken = event()
    del broken["body"]
    with pytest.raises(ValidationError):
        triage_one(broken, granted_scopes={REQUIRED_SCOPE}, ledger=InMemoryLedger())


def test_oversized_content_is_rejected():
    oversized = event()
    oversized["body"] = "x" * 4_001
    with pytest.raises(PolicyError):
        triage_one(oversized, granted_scopes={REQUIRED_SCOPE}, ledger=InMemoryLedger())


def test_scope_explosion_is_rejected():
    with pytest.raises(PolicyError):
        triage_batch(
            [event(f"evt-{i}") for i in range(26)],
            granted_scopes={REQUIRED_SCOPE},
        )


def test_kill_switch_stops_before_execution():
    with pytest.raises(CancelledError):
        triage_one(
            event(),
            granted_scopes={REQUIRED_SCOPE},
            ledger=InMemoryLedger(),
            kill_switch=True,
        )
