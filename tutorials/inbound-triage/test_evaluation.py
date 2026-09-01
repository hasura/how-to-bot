import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).parent


def test_evaluation_contract_was_predeclared_and_is_strict():
    contract = yaml.safe_load((ROOT / "evaluation.yaml").read_text())
    assert contract["fixture_version"] == "inbound-triage-eval-v3"
    assert contract["frozen_before_run"] == "2026-09-01T20:56:00Z"
    assert all(metric["threshold"] == 1.0 for metric in contract["metrics"])
    assert all(
        invariant["maximum_failures"] == 0
        for invariant in contract["critical_invariants"]
    )
    assert len(contract["adversarial_probes"]) == 6
    assert all(probe["required_pass"] is True for probe in contract["adversarial_probes"])


def test_frozen_evaluation_reports_raw_passing_denominators():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "evaluate.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    expected = {
        "correct_route_rate": (3, 3),
        "correct_abstention_rate": (2, 2),
        "exact_grounding_rate": (3, 3),
        "exception_detection_rate": (2, 2),
    }
    assert {
        row["id"]: (row["numerator"], row["denominator"])
        for row in report["metrics"]
    } == expected
    assert all(row["passed"] for row in report["metrics"])
    assert all(row["passed"] for row in report["critical_invariants"])
    assert report["adversarial_summary"] == {"passed": 6, "total": 6}
    assert all(row["passed"] for row in report["adversarial_probes"])
    assert all(row["passed"] for row in report["cases"])