"""Deterministic, side-effect-free inbound-triage reference implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from typing import Any, Callable
from uuid import uuid4

MAX_ITEMS_PER_RUN = 25
MAX_TEXT_LENGTH = 4_000
MAX_RUNTIME_SECONDS = 30.0
STEP_TIMEOUT_SECONDS = {
    "authorize-record": 5.0,
    "validate-event": 5.0,
    "claim-intent": 10.0,
    "plan-route": 5.0,
    "record-draft": 5.0,
    "recover-run": 30.0,
}
MAX_EVENT_AGE = timedelta(days=7)
MAX_FUTURE_SKEW = timedelta(minutes=5)
REQUIRED_SCOPE = "inbound_events:read"
DEFAULT_EVALUATION_TIME = datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc)

WORKFLOW_STATES = {
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
_ALLOWED_TRANSITIONS = {
    "received": {"validated", "failed", "cancelled"},
    "validated": {"planned", "failed", "cancelled"},
    "planned": {"awaiting_approval", "executing", "failed", "cancelled"},
    "awaiting_approval": {"executing", "failed", "cancelled"},
    "executing": {"succeeded", "partially_succeeded", "failed", "cancelled"},
    "succeeded": {"reconciled"},
    "partially_succeeded": {"reconciled", "failed"},
    "failed": {"reconciled"},
    "cancelled": {"reconciled"},
    "reconciled": set(),
}

ROUTES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("breach", "credential", "phishing", "security", "vulnerability")),
    ("billing", ("billing", "charge", "invoice", "payment", "refund")),
    ("technical-support", ("bug", "error", "failed", "outage", "support")),
)
SENSITIVE_TERMS = ("credential", "password", "secret", "ssn", "social security", "breach")


class TriageError(Exception):
    """Base class with a stable machine-readable error code and run identifier."""

    code = "unknown"

    def __init__(self, message: str, *, run_id: str | None = None):
        super().__init__(message)
        self.run_id = run_id


class ValidationError(TriageError):
    code = "validation"


class AuthorizationError(TriageError):
    code = "authorization"


class PolicyError(TriageError):
    code = "policy"


class ConflictError(TriageError):
    code = "conflict"


class DeadlineExceededError(TriageError):
    code = "deadline_exceeded"


class RepeatedErrorStop(TriageError):
    code = "repeated_error_stop"


class TelemetryUnavailableError(TriageError):
    code = "telemetry_unavailable"


class CancelledError(TriageError):
    code = "cancelled"


@dataclass(frozen=True)
class RequestContext:
    """Trusted invocation context supplied by the adapter, never by inbound content."""

    requester_id: str
    operator_id: str
    granted_scopes: frozenset[str]
    policy_version: str


@dataclass(frozen=True)
class AuthorizationPolicy:
    """Current source policy used at the point of record access."""

    version: str
    record_grants: dict[str, frozenset[str]]
    source_grants: dict[str, frozenset[str]]
    record_versions: dict[str, str]
    revoked_requesters: frozenset[str] = frozenset()
    active: bool = True

    def authorize(self, context: RequestContext, metadata: dict[str, str]) -> None:
        if not self.active or context.policy_version != self.version:
            raise AuthorizationError("current authorization policy is unavailable or changed")
        if context.requester_id in self.revoked_requesters:
            raise AuthorizationError("requester access is revoked")
        if context.granted_scopes != frozenset({REQUIRED_SCOPE}):
            raise AuthorizationError("exact inbound-events read scope is required")
        record_ids = self.record_grants.get(context.requester_id, frozenset())
        sources = self.source_grants.get(context.requester_id, frozenset())
        if metadata["id"] not in record_ids or metadata["source"] not in sources:
            raise AuthorizationError("record is not authorized for requester")
        if self.record_versions.get(metadata["id"]) != metadata["source_version"]:
            raise AuthorizationError("record source version is not authorized")
        if metadata["reporter"] != context.requester_id:
            raise AuthorizationError("record ownership does not match requester")


@dataclass(frozen=True)
class TelemetryEvent:
    sequence: int
    run_id: str
    correlation_id: str
    event_id: str
    requester_id: str
    operator_id: str
    kind: str
    state: str
    code: str
    timestamp: str
    policy_version: str
    owner_run_id: str | None = None
    suggested_route: str | None = None
    outcome_status: str | None = None
    terminal_state: str | None = None
    reason_codes: tuple[str, ...] = ()
    evidence_count: int | None = None
    confidence: float | None = None
    abstained: bool | None = None
    sensitive_case: bool | None = None
    duplicate: bool | None = None


class TelemetrySink:
    """Redacted in-memory audit sink with explicit access and retention metadata."""

    retention_days = 30
    access_roles = frozenset({"tutorial-maintainer", "independent-reviewer"})
    redacted_fields = frozenset({"subject", "body", "secret", "password", "token"})

    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self._lock = threading.Lock()
        self._events: list[TelemetryEvent] = []
        self._sequence = 0

    def _validate_event(self, event: TelemetryEvent) -> None:
        if not self.available:
            raise TelemetryUnavailableError(
                "telemetry unavailable; run stopped in visible degraded mode"
            )
        serialized = repr(asdict(event)).casefold()
        if any(field in serialized for field in ("password=", "token=", "secret=")):
            raise PolicyError("telemetry redaction invariant failed")

    def emit(self, event: TelemetryEvent) -> None:
        self._validate_event(event)
        with self._lock:
            self._sequence += 1
            self._events.append(replace(event, sequence=self._sequence))

    def publish_with_terminal_events(
        self,
        events: tuple[TelemetryEvent, ...],
        *,
        publish: Callable[[], None],
    ) -> None:
        """Make terminal events visible only after durable publication succeeds.

        Validation and availability checks happen before the publication callback.
        Once the callback returns, appending already-validated in-memory events is
        deliberately non-fallible and occurs while the sink lock is still held.
        """
        for event in events:
            self._validate_event(event)
        with self._lock:
            # Recheck availability after acquiring the publication lock.
            if not self.available:
                raise TelemetryUnavailableError(
                    "telemetry unavailable; run stopped in visible degraded mode"
                )
            publish()
            for event in events:
                self._sequence += 1
                self._events.append(replace(event, sequence=self._sequence))

    def events_for(self, run_id: str, *, actor_role: str) -> list[dict[str, Any]]:
        self._authorize_reader(actor_role)
        with self._lock:
            return [asdict(item) for item in self._events if item.run_id == run_id]

    def all_events(self, *, actor_role: str) -> list[dict[str, Any]]:
        self._authorize_reader(actor_role)
        with self._lock:
            return [asdict(item) for item in self._events]

    def purge_expired(self, *, actor_role: str, now: datetime) -> int:
        self._authorize_reader(actor_role)
        cutoff = now.astimezone(timezone.utc) - timedelta(days=self.retention_days)
        with self._lock:
            before = len(self._events)
            self._events = [
                item for item in self._events if _parse_timestamp(item.timestamp) >= cutoff
            ]
            return before - len(self._events)

    def _authorize_reader(self, actor_role: str) -> None:
        if actor_role not in self.access_roles:
            raise AuthorizationError("telemetry access denied")


@dataclass(frozen=True)
class KillSwitchAudit:
    sequence: int
    action: str
    actor_id: str
    reason: str
    timestamp: str


class KillSwitch:
    """Owner-controlled stop with an activation generation fenced through completion."""

    def __init__(self, *, owner_id: str) -> None:
        self.owner_id = owner_id
        self._active = False
        self._reconciliation_required = False
        self._generation = 0
        self._lock = threading.Lock()
        self._audit: list[KillSwitchAudit] = []

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def generation(self) -> int:
        with self._lock:
            return self._generation

    def activate(self, *, actor_id: str, reason: str) -> None:
        self._require_owner(actor_id)
        with self._lock:
            self._generation += 1
            self._active = True
            self._reconciliation_required = True
            self._audit.append(
                KillSwitchAudit(
                    len(self._audit) + 1,
                    "activated",
                    actor_id,
                    reason,
                    _utc_now_text(),
                )
            )

    def resume(
        self,
        *,
        actor_id: str,
        reconciled: bool,
        reason: str,
        ledger: DurableLedger | None = None,
    ) -> None:
        self._require_owner(actor_id)
        if not reconciled:
            raise PolicyError("controlled resume requires reconciliation")
        if ledger is None or ledger.has_unreconciled_entries():
            raise PolicyError("controlled resume requires ledger-verified reconciliation")
        with self._lock:
            self._active = False
            self._reconciliation_required = False
            self._audit.append(
                KillSwitchAudit(
                    len(self._audit) + 1,
                    "resumed",
                    actor_id,
                    reason,
                    _utc_now_text(),
                )
            )

    def check(self, *, run_id: str, expected_generation: int | None = None) -> None:
        with self._lock:
            self._check_locked(run_id=run_id, expected_generation=expected_generation)

    def finalize_if_unchanged(
        self,
        *,
        run_id: str,
        expected_generation: int,
        finalize: Callable[[], None],
    ) -> None:
        """Serialize the final ledger publication against switch activation."""
        with self._lock:
            self._check_locked(
                run_id=run_id,
                expected_generation=expected_generation,
            )
            finalize()

    def _check_locked(self, *, run_id: str, expected_generation: int | None) -> None:
        if (
            self._active
            or self._reconciliation_required
            or (
                expected_generation is not None
                and expected_generation != self._generation
            )
        ):
            raise CancelledError(
                "kill switch is active or changed; reconciliation required",
                run_id=run_id,
            )

    def audit_log(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(item) for item in self._audit]

    def _require_owner(self, actor_id: str) -> None:
        if actor_id != self.owner_id:
            raise AuthorizationError("only the kill-switch owner may change stop state")


@dataclass(frozen=True)
class EvidenceSpan:
    source: str
    source_version: str
    field: str
    start: int
    end: int
    text_sha256: str


@dataclass(frozen=True)
class TriageResult:
    event_id: str
    source_version: str
    status: str
    suggested_route: str
    suggested_resolution: str | None
    reason_codes: tuple[str, ...]
    evidence: tuple[EvidenceSpan, ...]
    extracted_facts: tuple[dict[str, Any], ...]
    inference: dict[str, Any]
    confidence: float
    requires_human_disposition: bool
    disposition_owner: str
    sensitive_case: bool
    abstained: bool
    duplicate: bool
    idempotency_key: str
    run_id: str
    terminal_state: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["reason_codes"] = list(self.reason_codes)
        result["evidence"] = [asdict(item) for item in self.evidence]
        result["extracted_facts"] = list(self.extracted_facts)
        return result


class DurableLedger:
    """SQLite replay ledger with atomic claims and controlled interruption recovery."""

    retention_days = 7
    owner = "Anushrut Gupta"
    access_roles = frozenset({"tutorial-operator", "independent-reviewer"})
    ordering = "received_at ascending, then event id"

    def __init__(self, path: str | Path | None = None, *, max_failures: int = 2) -> None:
        if path is None:
            handle = tempfile.NamedTemporaryFile(prefix="howtobot-ledger-", suffix=".sqlite3", delete=False)
            handle.close()
            path = handle.name
        self.path = str(path)
        self.max_failures = max_failures
        self._schema_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=1.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._schema_lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS triage_ledger (
                    event_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_json TEXT,
                    failures INTEGER NOT NULL DEFAULT 0,
                    owner_run_id TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _deserialize_result(payload: str) -> TriageResult:
        data = json.loads(payload)
        data["reason_codes"] = tuple(data["reason_codes"])
        data["evidence"] = tuple(EvidenceSpan(**item) for item in data["evidence"])
        data["extracted_facts"] = tuple(data["extracted_facts"])
        return TriageResult(**data)

    def claim(
        self,
        *,
        event_id: str,
        fingerprint: str,
        run_id: str,
        deadline: float,
    ) -> tuple[str, TriageResult | None, bool]:
        """Atomically claim new/recoverable intent or wait for an exact concurrent owner."""
        while True:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM triage_ledger WHERE event_id = ?", (event_id,)
                ).fetchone()
                now = _utc_now_text()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO triage_ledger
                        (event_id, fingerprint, state, failures, owner_run_id, updated_at)
                        VALUES (?, ?, 'executing', 0, ?, ?)
                        """,
                        (event_id, fingerprint, run_id, now),
                    )
                    connection.commit()
                    return "owner", None, False
                if row["fingerprint"] != fingerprint:
                    connection.rollback()
                    raise ConflictError("event identity was replayed with changed content")
                if (
                    row["state"] in {"succeeded", "reconciled"}
                    and row["result_json"]
                    and row["owner_run_id"] is None
                ):
                    result = self._deserialize_result(row["result_json"])
                    connection.commit()
                    return "duplicate", result, False
                if row["state"] in {"failed", "cancelled", "reconciled"}:
                    if row["failures"] >= self.max_failures:
                        connection.rollback()
                        raise RepeatedErrorStop("repeated-error stop threshold reached")
                    connection.execute(
                        """
                        UPDATE triage_ledger
                        SET state = 'executing', owner_run_id = ?, updated_at = ?
                        WHERE event_id = ? AND state IN ('failed', 'cancelled', 'reconciled')
                        """,
                        (run_id, now, event_id),
                    )
                    connection.commit()
                    return "owner", None, True
                connection.commit()
            if time.monotonic() > deadline:
                raise DeadlineExceededError("deadline exceeded waiting for concurrent replay")
            time.sleep(min(0.005, max(deadline - time.monotonic(), 0)))

    def complete(
        self,
        event_id: str,
        result: TriageResult,
        *,
        run_id: str,
        terminal_state: str,
    ) -> None:
        """Stage a terminal result only for the current fenced owner."""
        if terminal_state not in {"succeeded", "reconciled"}:
            raise PolicyError("invalid successful terminal state")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE triage_ledger
                SET result_json = ?, updated_at = ?
                WHERE event_id = ? AND state = 'executing' AND owner_run_id = ?
                """,
                (
                    json.dumps(result.to_dict(), sort_keys=True),
                    _utc_now_text(),
                    event_id,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ConflictError(
                    "stale ledger owner cannot complete recovered intent",
                    run_id=run_id,
                )
            connection.commit()

    def finalize(
        self,
        event_id: str,
        *,
        run_id: str,
        terminal_state: str,
        deadline: float,
        step_deadline: float,
    ) -> None:
        """Publish a staged result only while both global and step clocks remain valid."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if time.monotonic() > min(deadline, step_deadline):
                connection.rollback()
                raise DeadlineExceededError(
                    "deadline exceeded before durable finalization",
                    run_id=run_id,
                )
            cursor = connection.execute(
                """
                UPDATE triage_ledger
                SET state = ?, owner_run_id = NULL, updated_at = ?
                WHERE event_id = ? AND state = 'executing' AND owner_run_id = ?
                  AND result_json IS NOT NULL
                """,
                (terminal_state, _utc_now_text(), event_id, run_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ConflictError(
                    "ledger finalization lost its fenced ownership",
                    run_id=run_id,
                )
            if time.monotonic() > min(deadline, step_deadline):
                connection.rollback()
                raise DeadlineExceededError(
                    "deadline exceeded during durable finalization",
                    run_id=run_id,
                )
            connection.commit()

    def abort(self, event_id: str, state: str, *, run_id: str) -> bool:
        """Abort only the caller's live or staged claim; stale owners cannot overwrite."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE triage_ledger
                SET state = ?, result_json = NULL, failures = failures + 1,
                    owner_run_id = NULL, updated_at = ?
                WHERE event_id = ? AND owner_run_id = ?
                """,
                (state, _utc_now_text(), event_id, run_id),
            )
            return cursor.rowcount == 1

    def mark_interrupted_for_recovery(self, event_id: str, *, actor_id: str) -> None:
        self._require_owner(actor_id)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state, owner_run_id FROM triage_ledger WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if (
                row is None
                or row["state"] != "executing"
                or row["owner_run_id"] is None
            ):
                connection.rollback()
                raise PolicyError("only an owned executing intent may be marked interrupted")
            connection.execute(
                """
                UPDATE triage_ledger
                SET state = 'failed', result_json = NULL, failures = failures + 1,
                    owner_run_id = NULL, updated_at = ?
                WHERE event_id = ? AND state = 'executing'
                """,
                (_utc_now_text(), event_id),
            )
            connection.commit()

    def reconcile(
        self,
        event_id: str,
        *,
        actor_id: str,
        expected_fingerprint: str,
        expected_terminal_state: str,
        reason: str,
    ) -> None:
        """Owner-authorized compare-and-set reconciliation of an observed terminal row."""
        self._require_owner(actor_id)
        if expected_terminal_state not in {"failed", "cancelled", "succeeded"}:
            raise PolicyError("reconciliation requires an observed terminal state")
        if not isinstance(reason, str) or not reason.strip():
            raise PolicyError("reconciliation requires a non-empty reason")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE triage_ledger SET state = 'reconciled', updated_at = ?
                WHERE event_id = ? AND owner_run_id IS NULL
                  AND state = ? AND fingerprint = ?
                  AND (state = 'succeeded' OR failures > 0)
                """,
                (
                    _utc_now_text(),
                    event_id,
                    expected_terminal_state,
                    expected_fingerprint,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise PolicyError(
                    "reconciliation evidence does not match a finalized terminal ledger entry"
                )
            connection.commit()

    def has_unreconciled_entries(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM triage_ledger
                WHERE state IN ('executing', 'failed', 'cancelled')
                   OR owner_run_id IS NOT NULL
                LIMIT 1
                """
            ).fetchone()
        return row is not None

    def delete(self, event_id: str, *, actor_id: str) -> None:
        self._require_owner(actor_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM triage_ledger WHERE event_id = ?", (event_id,))

    def reset(self, *, actor_id: str) -> None:
        self._require_owner(actor_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM triage_ledger")

    def snapshot(self, *, actor_role: str) -> dict[str, str]:
        if actor_role not in self.access_roles:
            raise AuthorizationError("ledger state access denied")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_id, state FROM triage_ledger ORDER BY event_id"
            ).fetchall()
        return {row["event_id"]: row["state"] for row in rows}

    def purge_expired(self, *, actor_id: str, now: datetime) -> int:
        self._require_owner(actor_id)
        cutoff = now.astimezone(timezone.utc) - timedelta(days=self.retention_days)
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM triage_ledger WHERE updated_at < ?",
                (cutoff.isoformat().replace("+00:00", "Z"),),
            )
            return cursor.rowcount

    def close_and_delete(self, *, actor_id: str) -> None:
        self._require_owner(actor_id)
        Path(self.path).unlink(missing_ok=True)

    def _require_owner(self, actor_id: str) -> None:
        if actor_id != self.owner:
            raise AuthorizationError("only ledger owner may change durable state")


class _RunTrace:
    def __init__(
        self,
        *,
        telemetry: TelemetrySink,
        run_id: str,
        correlation_id: str,
        event_id: str,
        context: RequestContext,
    ) -> None:
        self.telemetry = telemetry
        self.run_id = run_id
        self.correlation_id = correlation_id
        self.event_id = event_id
        self.context = context
        self.state = "received"
        self.emit("transition", "received")

    def _event(self, kind: str, state: str, code: str, **details: Any) -> TelemetryEvent:
        return TelemetryEvent(
            sequence=0,
            run_id=self.run_id,
            correlation_id=self.correlation_id,
            event_id=self.event_id,
            requester_id=self.context.requester_id,
            operator_id=self.context.operator_id,
            kind=kind,
            state=state,
            code=code,
            timestamp=_utc_now_text(),
            policy_version=self.context.policy_version,
            **details,
        )

    def emit(self, kind: str, code: str, **details: Any) -> None:
        self.telemetry.emit(self._event(kind, self.state, code, **details))

    def transition(self, state: str, code: str = "ok") -> None:
        if state not in WORKFLOW_STATES:
            raise PolicyError(f"unknown state: {state}", run_id=self.run_id)
        if state not in _ALLOWED_TRANSITIONS[self.state]:
            raise PolicyError(
                f"illegal transition: {self.state} -> {state}", run_id=self.run_id
            )
        self.state = state
        self.emit("transition", code)


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _metadata(event: dict[str, Any]) -> dict[str, str]:
    names = ("id", "source", "reporter", "source_version")
    if any(not isinstance(event.get(name), str) or not event[name] for name in names):
        raise ValidationError("missing authorization metadata")
    return {name: event[name] for name in names}


_RFC3339 = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T"
    r"(?P<time>\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?)"
    r"(?P<zone>Z|[+-]\d{2}:\d{2})$"
)


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or _RFC3339.fullmatch(value) is None:
        raise ValidationError("received_at must be a strict RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("received_at must be a valid RFC3339 timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValidationError("received_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_event(event: dict[str, Any], *, evaluation_time: datetime) -> datetime:
    required = (
        "id",
        "received_at",
        "source",
        "source_version",
        "subject",
        "body",
        "reporter",
    )
    missing = [name for name in required if not isinstance(event.get(name), str) or not event[name]]
    if missing:
        raise ValidationError(f"missing or invalid fields: {', '.join(missing)}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", event["id"]):
        raise ValidationError("event id has an invalid format")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}", event["source_version"]):
        raise ValidationError("source_version has an invalid format")
    if len(event["subject"]) > MAX_TEXT_LENGTH or len(event["body"]) > MAX_TEXT_LENGTH:
        raise PolicyError("event text exceeds the configured limit")
    received = _parse_timestamp(event["received_at"])
    if evaluation_time.tzinfo is None:
        raise PolicyError("evaluation_time must be timezone-aware")
    if evaluation_time - received > MAX_EVENT_AGE:
        raise PolicyError("event is stale and requires deterministic exception routing")
    if received - evaluation_time > MAX_FUTURE_SKEW:
        raise PolicyError("event timestamp is too far in the future")
    return received


def _fingerprint(event: dict[str, Any]) -> str:
    """Hash exact validated source bytes; whitespace changes are content changes."""
    fields = (
        "received_at",
        "source",
        "source_version",
        "subject",
        "body",
        "reporter",
    )
    exact = json.dumps(
        [event[field] for field in fields],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(exact).hexdigest()


def _idempotency_key(event_id: str) -> str:
    return "triage:" + hashlib.sha256(event_id.encode()).hexdigest()


def _span(event: dict[str, Any], field: str, term: str) -> EvidenceSpan:
    text = event[field]
    match = re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
    if match is None:
        raise PolicyError("internal grounding span mismatch")
    matched_bytes = match.group(0).encode("utf-8")
    return EvidenceSpan(
        source=event["source"],
        source_version=event["source_version"],
        field=field,
        start=len(text[: match.start()].encode("utf-8")),
        end=len(text[: match.end()].encode("utf-8")),
        text_sha256=hashlib.sha256(matched_bytes).hexdigest(),
    )


def _route(
    event: dict[str, Any],
) -> tuple[str, tuple[str, ...], float, tuple[EvidenceSpan, ...], bool]:
    scored: list[tuple[int, int, str, tuple[tuple[str, str], ...]]] = []
    for priority, (route, words) in enumerate(ROUTES):
        hits: list[tuple[str, str]] = []
        for word in words:
            for field_name in ("subject", "body"):
                if re.search(rf"\b{re.escape(word)}\b", event[field_name], re.IGNORECASE):
                    hits.append((word, field_name))
                    break
        scored.append((len(hits), -priority, route, tuple(hits)))
    count, _, route, hits = max(scored)
    tied_routes = [item for item in scored if item[0] == count and count > 0]
    if count == 0:
        return "general-review", ("abstain:no_supported_route",), 0.0, (), True
    if len(tied_routes) > 1:
        return "general-review", ("abstain:conflicting_route_evidence",), 0.0, (), True
    spans = tuple(_span(event, field_name, word) for word, field_name in hits)
    confidence = min(0.55 + 0.12 * count, 0.91)
    return route, tuple(f"matched:{word}" for word, _ in hits), confidence, spans, False



def _validate_runtime_seconds(value: float, *, run_id: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PolicyError("maximum runtime must be numeric", run_id=run_id)
    seconds = float(value)
    if not math.isfinite(seconds):
        raise PolicyError("maximum runtime must be finite", run_id=run_id)
    if seconds <= 0:
        raise DeadlineExceededError("maximum runtime exceeded", run_id=run_id)
    if seconds > MAX_RUNTIME_SECONDS:
        raise PolicyError(
            f"maximum runtime cannot exceed {MAX_RUNTIME_SECONDS:g} seconds",
            run_id=run_id,
        )
    return seconds


def triage_one(
    event: dict[str, Any],
    *,
    context: RequestContext,
    authorization_policy: AuthorizationPolicy,
    ledger: DurableLedger,
    telemetry: TelemetrySink,
    kill_switch: KillSwitch,
    disposition_owner: str = "Anushrut Gupta",
    evaluation_time: datetime = DEFAULT_EVALUATION_TIME,
    max_runtime_seconds: float = MAX_RUNTIME_SECONDS,
    step_hook: Callable[[str], None] | None = None,
    _absolute_deadline: float | None = None,
) -> TriageResult:
    run_id = str(uuid4())
    correlation_id = str(uuid4())
    event_id = str(event.get("id", "unknown"))
    trace: _RunTrace | None = None
    claimed = False
    recovered = False
    recovery_started: float | None = None

    deadline = float("inf")
    switch_generation = kill_switch.generation()

    def fence(stage: str, *, step_started: float | None = None, step: str | None = None) -> None:
        if step_hook is not None:
            step_hook(stage)
        now = time.monotonic()
        if now > deadline:
            raise DeadlineExceededError("maximum runtime exceeded", run_id=run_id)
        if step_started is not None and step is not None:
            if now - step_started > STEP_TIMEOUT_SECONDS[step]:
                raise DeadlineExceededError(
                    f"{step} step timeout exceeded",
                    run_id=run_id,
                )
        if (
            recovery_started is not None
            and now - recovery_started > STEP_TIMEOUT_SECONDS["recover-run"]
        ):
            raise DeadlineExceededError(
                "recover-run step timeout exceeded",
                run_id=run_id,
            )
        kill_switch.check(
            run_id=run_id,
            expected_generation=switch_generation,
        )

    try:
        trace = _RunTrace(
            telemetry=telemetry,
            run_id=run_id,
            correlation_id=correlation_id,
            event_id=event_id,
            context=context,
        )
        runtime_seconds = _validate_runtime_seconds(max_runtime_seconds, run_id=run_id)
        local_deadline = time.monotonic() + runtime_seconds
        deadline = (
            local_deadline
            if _absolute_deadline is None
            else min(local_deadline, _absolute_deadline)
        )
        fence("received")

        step_started = time.monotonic()
        metadata = _metadata(event)
        authorization_policy.authorize(context, metadata)
        trace.emit("policy_decision", "authorized")
        fence("authorized", step_started=step_started, step="authorize-record")

        step_started = time.monotonic()
        _validate_event(event, evaluation_time=evaluation_time)
        trace.transition("validated")
        fence("validated", step_started=step_started, step="validate-event")

        step_started = time.monotonic()
        claim_deadline = min(
            deadline,
            step_started + STEP_TIMEOUT_SECONDS["claim-intent"],
        )
        mode, prior, recovered = ledger.claim(
            event_id=event["id"],
            fingerprint=_fingerprint(event),
            run_id=run_id,
            deadline=claim_deadline,
        )
        fence("claimed", step_started=step_started, step="claim-intent")
        if mode == "duplicate":
            assert prior is not None
            trace.emit(
                "claim",
                "duplicate",
                owner_run_id=prior.run_id,
                duplicate=True,
                terminal_state=prior.terminal_state,
            )
            trace.transition("planned", "exact_replay")
            trace.transition("executing", "duplicate_suppressed")
            trace.emit(
                "outcome",
                "original_outcome_reused",
                suggested_route=prior.suggested_route,
                outcome_status=prior.status,
                terminal_state=prior.terminal_state,
                reason_codes=prior.reason_codes,
                evidence_count=len(prior.evidence),
                confidence=prior.confidence,
                abstained=prior.abstained,
                sensitive_case=prior.sensitive_case,
                duplicate=True,
            )
            trace.transition("succeeded", "original_outcome_reused")
            return replace(prior, duplicate=True, run_id=run_id)

        claimed = True
        if recovered:
            recovery_started = time.monotonic()
        trace.emit("claim", "recovered" if recovered else "acquired", owner_run_id=run_id)
        if recovered:
            trace.emit("retry", "recovering_prior_failure", owner_run_id=run_id)

        trace.transition("planned")
        fence("planned")

        step_started = time.monotonic()
        trace.transition("executing")
        fence("executing")
        route, reasons, confidence, spans, abstained = _route(event)
        sensitive_hits: list[EvidenceSpan] = []
        for term in SENSITIVE_TERMS:
            for field_name in ("subject", "body"):
                if re.search(rf"\b{re.escape(term)}\b", event[field_name], re.IGNORECASE):
                    sensitive_hits.append(_span(event, field_name, term))
                    break
        sensitive = bool(sensitive_hits)
        if sensitive:
            route = "security"
            reasons = tuple(dict.fromkeys((*reasons, "sensitive_case_escalation")))
            confidence = max(confidence, 0.8)
            spans = tuple(dict.fromkeys((*spans, *sensitive_hits)))
            abstained = False
        fence("classified", step_started=step_started, step="plan-route")

        step_started = time.monotonic()
        facts = tuple(
            {
                "fact_id": f"fact-{index + 1}",
                "kind": "policy_keyword_match",
                "status": "extracted",
                "evidence_index": index,
            }
            for index, _ in enumerate(spans)
        )
        inference = {
            "kind": "route_suggestion",
            "status": "supported" if spans else "unsupported_abstention",
            "basis_fact_ids": [fact["fact_id"] for fact in facts],
            "human_must_decide": True,
        }
        resolutions = {
            "billing": "Have the named human review the referenced billing evidence.",
            "security": "Have the named human perform the sensitive-case security review.",
            "technical-support": "Have the named human review the referenced technical evidence.",
        }
        terminal_state = "reconciled" if recovered else "succeeded"
        result = TriageResult(
            event_id=event["id"],
            source_version=event["source_version"],
            status="draft",
            suggested_route=route,
            suggested_resolution=resolutions.get(route),
            reason_codes=reasons,
            evidence=spans,
            extracted_facts=facts,
            inference=inference,
            confidence=round(confidence, 2),
            requires_human_disposition=True,
            disposition_owner=disposition_owner,
            sensitive_case=sensitive,
            abstained=abstained,
            duplicate=False,
            idempotency_key=_idempotency_key(event["id"]),
            run_id=run_id,
            terminal_state=terminal_state,
        )
        trace.emit(
            "plan",
            "route_planned",
            owner_run_id=run_id,
            suggested_route=result.suggested_route,
            outcome_status=result.status,
            terminal_state=terminal_state,
            reason_codes=result.reason_codes,
            evidence_count=len(result.evidence),
            confidence=result.confidence,
            abstained=result.abstained,
            sensitive_case=result.sensitive_case,
            duplicate=False,
        )
        trace.emit("tool_inventory", "none")
        trace.emit("side_effect_inventory", "none")
        fence("recording", step_started=step_started, step="record-draft")

        ledger.complete(
            event["id"],
            result,
            run_id=run_id,
            terminal_state=terminal_state,
        )
        # This post-completion fence is intentional: a stop/deadline arriving while
        # SQLite completion is blocked converts the staged outcome to cancelled/failed.
        fence("completed", step_started=step_started, step="record-draft")
        # Validate terminal telemetry before publication, then publish the ledger
        # and expose its terminal events as one sink-locked operation. A failed ledger
        # commit exposes no success event; a telemetry failure publishes no result.
        terminal_events = (
            trace._event(
                "outcome",
                trace.state,
                "draft_recorded",
                owner_run_id=run_id,
                suggested_route=result.suggested_route,
                outcome_status=result.status,
                terminal_state=terminal_state,
                reason_codes=result.reason_codes,
                evidence_count=len(result.evidence),
                confidence=result.confidence,
                abstained=result.abstained,
                sensitive_case=result.sensitive_case,
                duplicate=False,
            ),
            trace._event("transition", "succeeded", "ok"),
        )
        if recovered:
            terminal_events = (
                *terminal_events,
                trace._event(
                    "transition",
                    "reconciled",
                    "recovery_verified",
                ),
            )
        fence("finalizing", step_started=step_started, step="record-draft")
        kill_switch.finalize_if_unchanged(
            run_id=run_id,
            expected_generation=switch_generation,
            finalize=lambda: telemetry.publish_with_terminal_events(
                terminal_events,
                publish=lambda: ledger.finalize(
                    event["id"],
                    run_id=run_id,
                    terminal_state=terminal_state,
                    deadline=deadline,
                    step_deadline=step_started
                    + STEP_TIMEOUT_SECONDS["record-draft"],
                ),
            ),
        )
        trace.state = terminal_state
        return result
    except TriageError as exc:
        if exc.run_id is None:
            exc.run_id = run_id
        terminal = "cancelled" if isinstance(exc, CancelledError) else "failed"
        if trace is not None:
            if trace.state not in {"succeeded", "failed", "cancelled", "reconciled"}:
                try:
                    trace.transition(terminal, exc.code)
                except TelemetryUnavailableError:
                    pass
            if claimed:
                ledger.abort(event_id, terminal, run_id=run_id)
        raise
    except Exception as exc:
        if trace is not None and trace.state not in {"failed", "cancelled", "reconciled"}:
            try:
                trace.transition("failed", "runtime_error")
            except TelemetryUnavailableError:
                pass
        if claimed:
            ledger.abort(event_id, "failed", run_id=run_id)
        raise PolicyError("runtime step failed safely", run_id=run_id) from exc


def triage_batch(
    events: list[dict[str, Any]],
    *,
    context: RequestContext,
    authorization_policy: AuthorizationPolicy,
    ledger: DurableLedger | None = None,
    telemetry: TelemetrySink | None = None,
    kill_switch: KillSwitch | None = None,
    evaluation_time: datetime = DEFAULT_EVALUATION_TIME,
    max_runtime_seconds: float = MAX_RUNTIME_SECONDS,
) -> list[dict[str, Any]]:
    active_ledger = ledger or DurableLedger()
    active_telemetry = telemetry or TelemetrySink()
    active_switch = kill_switch or KillSwitch(owner_id="Anushrut Gupta")
    batch_run_id = str(uuid4())
    batch_trace: _RunTrace | None = None

    try:
        runtime_seconds = _validate_runtime_seconds(
            max_runtime_seconds,
            run_id=batch_run_id,
        )
        batch_deadline = time.monotonic() + runtime_seconds
        if len(events) > MAX_ITEMS_PER_RUN:
            batch_trace = _RunTrace(
                telemetry=active_telemetry,
                run_id=batch_run_id,
                correlation_id=str(uuid4()),
                event_id="batch",
                context=context,
            )
            raise PolicyError(
                f"batch exceeds {MAX_ITEMS_PER_RUN} items",
                run_id=batch_run_id,
            )
    except TriageError as exc:
        if batch_trace is None:
            batch_trace = _RunTrace(
                telemetry=active_telemetry,
                run_id=batch_run_id,
                correlation_id=str(uuid4()),
                event_id="batch",
                context=context,
            )
        if batch_trace.state == "received":
            batch_trace.transition("failed", exc.code)
        raise

    # Validate sort keys through triage_one so malformed input receives a run id
    # and governed received -> failed telemetry instead of an untraced KeyError.
    sortable: list[tuple[datetime, str, dict[str, Any]]] = []
    for item in events:
        try:
            received = _parse_timestamp(item.get("received_at"))
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                raise ValidationError("event id is required for deterministic ordering")
        except TriageError:
            triage_one(
                item,
                context=context,
                authorization_policy=authorization_policy,
                ledger=active_ledger,
                telemetry=active_telemetry,
                kill_switch=active_switch,
                evaluation_time=evaluation_time,
                max_runtime_seconds=max_runtime_seconds,
                _absolute_deadline=batch_deadline,
            )
            raise AssertionError("unreachable")
        sortable.append((received, item_id, item))

    ordered = [item for _, _, item in sorted(sortable, key=lambda row: (row[0], row[1]))]
    results: list[dict[str, Any]] = []
    for event in ordered:
        results.append(
            triage_one(
                event,
                context=context,
                authorization_policy=authorization_policy,
                ledger=active_ledger,
                telemetry=active_telemetry,
                kill_switch=active_switch,
                evaluation_time=evaluation_time,
                max_runtime_seconds=max_runtime_seconds,
                _absolute_deadline=batch_deadline,
            ).to_dict()
        )
    return results
