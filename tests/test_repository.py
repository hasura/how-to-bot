import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / "tutorials" / "inbound-triage"
REQUIRED_STATES = {
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


def manifest():
    return yaml.safe_load((TUTORIAL / "tutorial.yaml").read_text())


def test_all_fixtures_are_explicitly_synthetic():
    for fixture_name in ("events.json", "evaluation.json"):
        payload = json.loads((TUTORIAL / "fixtures" / fixture_name).read_text())
        events = payload if fixture_name == "events.json" else [row["event"] for row in payload]
        assert events
        assert all(event["source"].startswith("synthetic") for event in events)
        assert all(event["reporter"].startswith("synthetic") for event in events)


def test_pilot_has_no_side_effects_and_is_draft():
    data = manifest()
    assert data["status"] == "needs_retest"
    assert data["risk"]["tier"] == "T1"
    assert data["outcome"]["side_effects"] == []
    assert data["risk"]["side_effects"] == []
    adapter = yaml.safe_load(
        (TUTORIAL / "adapters" / "local-python" / "adapter.yaml").read_text()
    )
    unsupported = " ".join(adapter["unsupported"])
    assert "external write" in unsupported
    source = (ROOT / "src" / "howtobot" / "inbound_triage.py").read_text()
    for forbidden in ("requests.", "httpx.", "urllib.request", "subprocess.", "socket."):
        assert forbidden not in source


def test_manifest_contract_is_fully_resolved():
    data = manifest()
    assert data["version"] == "0.4.0"
    assert data["changelog"] == data["files"]["changelog"]
    assert data["adapters"] == ["local-python"]
    assert data["tested_versions"]["local-python-adapter"] == "0.4.0"
    assert data["tested_versions"]["fixture-set"] == data["evaluation"]["fixture_version"]
    assert data["lifecycle"]["maintainer"] == "Anushrut Gupta"
    assert data["lifecycle"]["domain_owner"] == "Anushrut Gupta"
    assert data["lifecycle"]["security_exception_owner"] == "Anushrut Gupta"
    assert data["lifecycle"]["issue_path"].startswith("https://github.com/hasura/how-to-bot/")
    assert data["lifecycle"]["security_report_path"].endswith("/security/advisories/new")
    assert data["lifecycle"]["retest_required"] is True
    assert data["lifecycle"]["retest_reason"]


def test_outcome_contract_traces_to_tests():
    outcome = manifest()["outcome"]
    for field in (
        "job",
        "users",
        "non_goals",
        "preconditions",
        "inputs",
        "outputs",
        "side_effects",
        "success_criteria",
        "unacceptable_outcomes",
        "assumptions",
        "affected_parties",
        "limitations",
    ):
        assert field in outcome
    tests = "\n".join(
        path.read_text() for path in TUTORIAL.glob("test_*.py")
    )
    for durable_behavior in (
        "authorization",
        "stale",
        "conflict",
        "abstain",
        "sensitive",
        "deadline",
        "kill_switch",
        "reconstruct",
    ):
        assert durable_behavior in tests


def test_actor_and_data_flow_contract_is_complete():
    data = manifest()
    actor_kinds = {actor["kind"] for actor in data["actors"]}
    assert {
        "requester",
        "operator",
        "approver",
        "data_owner",
        "affected_party",
        "tool",
        "destination",
    } <= actor_kinds
    assert next(
        actor["identity"]
        for actor in data["actors"]
        if actor["id"] == "final-disposition-owner"
    ) == "Anushrut Gupta"
    flow = data["data_flow"]
    for field in (
        "assets",
        "classifications",
        "untrusted_inputs",
        "tools",
        "destination",
        "boundaries",
    ):
        assert flow[field]


def test_each_step_contract_is_complete():
    data = manifest()
    fields = {
        "id",
        "input_schema",
        "output_schema",
        "preconditions",
        "postconditions",
        "invariants",
        "timeout_seconds",
        "error_classes",
        "exit_conditions",
    }
    assert len(data["workflow"]["steps"]) == 6
    assert all(set(step) == fields for step in data["workflow"]["steps"])
    assert set(data["workflow"]["states"]) == REQUIRED_STATES


def test_remediation_covers_every_failed_row_with_tests():
    remediation = yaml.safe_load((TUTORIAL / "remediation.yaml").read_text())
    expected = {
        "SCH-01", "SCH-02", "SCH-04", "EVD-01", "EVD-02", "STA-01",
        "STA-02", "STA-03", "FUN-01", "FUN-03", "REP-02", "OBS-01",
        "FAIL-01", "FAIL-02", "KILL-01", "PLT-02", "MNT-01", "MNT-02",
    }
    assert remediation["rubric_changed"] is False
    assert set(remediation["failed_rows"]) == expected
    assert all(row["changes"] and row["tests"] for row in remediation["failed_rows"].values())
    assert len(remediation["third_review_attacks"]) == 8
    assert all(
        row["change"] and row["tests"]
        for row in remediation["third_review_attacks"].values()
    )


def test_ci_runs_the_complete_gate():
    ci = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
    for command in (
        "tools/validate.py",
        "tools/check_links.py",
        "tools/secret_scan.py",
        "ruff check",
        "pytest -vv",
        "inbound-triage/evaluate.py",
        "inbound-triage/run.py",
    ):
        assert command in ci
    # Generated-site freshness is exercised transitively by pytest through
    # tests/test_site.py; keeping it there avoids a workflow-file mutation for
    # integrations that can write repository content but not Actions workflows.
    assert (ROOT / "tests" / "test_site.py").exists()
    assert 'version: "0.12.8"' in ci
    assert "uv python install 3.14.4" in ci


def test_discovery_ownership_and_progression_contract():
    data = manifest()
    assert set(data["discovery"]) == {"roles", "playbooks", "patterns"}
    assert all(data["discovery"].values())
    assert data["ownership"]["mode"] in {"MAINTAIN", "COMPLETE"}
    for field in (
        "responsibility",
        "owned_object",
        "healthy_or_done_condition",
        "verification_evidence",
        "stop_approval_escalation_boundary",
    ):
        assert data["ownership"][field]
    assert list(data["progression"]) == [
        "try_it",
        "run_repeatedly",
        "operate_safely",
    ]
    for stage in data["progression"].values():
        assert set(stage) == {"goal", "actions", "exit_condition"}
        assert stage["goal"] and stage["actions"] and stage["exit_condition"]
