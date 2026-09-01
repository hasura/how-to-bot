import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = ROOT / "tutorials" / "inbound-triage"


def test_all_fixtures_are_explicitly_synthetic():
    events = json.loads((TUTORIAL / "fixtures" / "events.json").read_text())
    assert events
    assert all(event["source"].startswith("synthetic") for event in events)
    assert all(event.get("reporter", "synthetic").startswith("synthetic") for event in events)


def test_pilot_has_no_side_effects_and_is_draft():
    manifest = yaml.safe_load((TUTORIAL / "tutorial.yaml").read_text())
    assert manifest["status"] == "draft"
    assert manifest["risk"]["tier"] == "T1"
    assert manifest["outcome"]["side_effects"] == []


def test_ci_runs_the_required_checks():
    ci = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
    for command in ("tools/validate.py", "tools/check_links.py", "tools/secret_scan.py", "ruff check", "pytest"):
        assert command in ci
