import json
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site" / "dist"


def test_site_build_is_deterministic_and_current():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_site.py"), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_site_builds_from_manifest_without_external_dependencies():
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "dist"
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "build_site.py"),
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        index = (output / "index.html").read_text()
        tutorial = (output / "tutorials" / "inbound-triage.html").read_text()
        manifest = yaml.safe_load(
            (ROOT / "tutorials" / "inbound-triage" / "tutorial.yaml").read_text()
        )
        assert manifest["title"] in index and manifest["title"] in tutorial
        assert "Role" in index and "Playbook" in index and "Pattern" in index
        assert "Try it" in tutorial
        assert "Run it repeatedly" in tutorial
        assert "Operate it safely" in tutorial
        assert manifest["ownership"]["mode"] in tutorial
        assert "https://" not in (output / "styles.css").read_text()
        assert "<script src=" not in index


def test_catalog_json_is_a_machine_readable_projection():
    catalog = json.loads((DIST / "catalog.json").read_text())
    assert len(catalog) == 1
    tutorial = catalog[0]
    assert tutorial["id"] == "inbound-triage"
    assert tutorial["ownership"]["mode"] == "COMPLETE"
    assert tutorial["discovery"]["roles"]
    assert tutorial["discovery"]["playbooks"]
    assert tutorial["discovery"]["patterns"]