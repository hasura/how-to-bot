"""Deterministic, side-effect-free inbound-triage reference implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any

MAX_ITEMS_PER_RUN = 25
MAX_TEXT_LENGTH = 4_000
REQUIRED_SCOPE = "inbound_events:read"

ROUTES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("breach", "credential", "phishing", "security", "vulnerability")),
    ("billing", ("billing", "charge", "invoice", "payment", "refund")),
    ("technical-support", ("bug", "error", "failed", "outage", "support")),
)
SENSITIVE_TERMS = ("credential", "password", "secret", "ssn", "social security", "breach")


class TriageError(Exception):
    """Base class with a stable machine-readable error code."""

    code = "unknown"


class ValidationError(TriageError):
    code = "validation"


class AuthorizationError(TriageError):
    code = "authorization"


class PolicyError(TriageError):
    code = "policy"


class CancelledError(TriageError):
    code = "cancelled"


@dataclass(frozen=True)
class TriageResult:
    event_id: str
    status: str
    suggested_route: str
    reason_codes: tuple[str, ...]
    citations: tuple[str, ...]
    confidence: float
    requires_human_disposition: bool
    sensitive_case: bool
    duplicate: bool
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("reason_codes", "citations"):
            result[key] = list(result[key])
        return result


class InMemoryLedger:
    """Example replay ledger. A durable adapter must replace this for real events."""

    def __init__(self) -> None:
        self._results: dict[str, TriageResult] = {}

    def get(self, key: str) -> TriageResult | None:
        return self._results.get(key)

    def record(self, key: str, result: TriageResult) -> None:
        self._results[key] = result


def _validate_event(event: dict[str, Any]) -> None:
    required = ("id", "received_at", "source", "subject", "body")
    missing = [name for name in required if not isinstance(event.get(name), str) or not event[name]]
    if missing:
        raise ValidationError(f"missing or invalid fields: {', '.join(missing)}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", event["id"]):
        raise ValidationError("event id has an invalid format")
    if len(event["subject"]) > MAX_TEXT_LENGTH or len(event["body"]) > MAX_TEXT_LENGTH:
        raise PolicyError("event text exceeds the configured limit")


def _idempotency_key(event: dict[str, Any]) -> str:
    semantic = "\x1f".join(
        event[field].strip() for field in ("id", "received_at", "source", "subject", "body")
    )
    return "triage:" + hashlib.sha256(semantic.encode()).hexdigest()


def _route(event: dict[str, Any]) -> tuple[str, tuple[str, ...], float]:
    # Source content is treated only as data. It cannot add tools, permissions, or rules.
    text = f"{event['subject']} {event['body']}".casefold()
    scored: list[tuple[int, int, str, tuple[str, ...]]] = []
    for priority, (route, words) in enumerate(ROUTES):
        hits = tuple(word for word in words if re.search(rf"\b{re.escape(word)}\b", text))
        scored.append((len(hits), -priority, route, hits))
    count, _, route, hits = max(scored)
    if count == 0:
        return "general-review", ("no_known_route_match",), 0.35
    confidence = min(0.55 + 0.12 * count, 0.91)
    return route, tuple(f"matched:{word}" for word in hits), confidence


def triage_one(
    event: dict[str, Any],
    *,
    granted_scopes: set[str],
    ledger: InMemoryLedger,
    kill_switch: bool = False,
) -> TriageResult:
    if kill_switch:
        raise CancelledError("kill switch is active")
    if REQUIRED_SCOPE not in granted_scopes:
        raise AuthorizationError(f"missing required scope: {REQUIRED_SCOPE}")
    if granted_scopes - {REQUIRED_SCOPE}:
        raise AuthorizationError("unexpected broader scope; fail closed")
    _validate_event(event)

    key = _idempotency_key(event)
    prior = ledger.get(key)
    if prior is not None:
        return TriageResult(**{**asdict(prior), "duplicate": True})

    route, reasons, confidence = _route(event)
    text = f"{event['subject']} {event['body']}".casefold()
    sensitive = any(term in text for term in SENSITIVE_TERMS)
    if sensitive:
        route = "security"
        reasons = tuple(dict.fromkeys((*reasons, "sensitive_case_escalation")))
        confidence = max(confidence, 0.8)

    result = TriageResult(
        event_id=event["id"],
        status="draft",
        suggested_route=route,
        reason_codes=reasons,
        citations=("event.subject", "event.body"),
        confidence=round(confidence, 2),
        requires_human_disposition=True,
        sensitive_case=sensitive,
        duplicate=False,
        idempotency_key=key,
    )
    ledger.record(key, result)
    return result


def triage_batch(
    events: list[dict[str, Any]],
    *,
    granted_scopes: set[str],
    ledger: InMemoryLedger | None = None,
    kill_switch: bool = False,
) -> list[dict[str, Any]]:
    if len(events) > MAX_ITEMS_PER_RUN:
        raise PolicyError(f"batch exceeds {MAX_ITEMS_PER_RUN} items")
    active_ledger = ledger or InMemoryLedger()
    return [
        triage_one(
            event,
            granted_scopes=granted_scopes,
            ledger=active_ledger,
            kill_switch=kill_switch,
        ).to_dict()
        for event in events
    ]
