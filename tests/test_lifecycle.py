import pytest
import yaml
from pathlib import Path

from howtobot.lifecycle import invalidate_for_material_change

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tutorials" / "inbound-triage" / "tutorial.yaml"


def test_material_change_forces_needs_retest():
    manifest = yaml.safe_load(MANIFEST.read_text())
    changed = invalidate_for_material_change(
        manifest, change_type="permission", changed_by="synthetic-maintainer"
    )
    assert changed["status"] == "needs_retest"
    assert changed["lifecycle"]["retest_required"] is True
    assert "permission" in changed["lifecycle"]["retest_reason"]


def test_nonmaterial_change_cannot_invalidate_contract():
    manifest = yaml.safe_load(MANIFEST.read_text())
    with pytest.raises(ValueError):
        invalidate_for_material_change(manifest, change_type="copy-edit", changed_by="reviewer")