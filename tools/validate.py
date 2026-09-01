from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import yaml

ROOT = Path(__file__).resolve().parents[1]
TUTORIALS = ROOT / "tutorials"
SCHEMAS = {
    "tutorial.yaml": ROOT / "schemas/tutorial.schema.json",
    "permissions.yaml": ROOT / "schemas/permissions.schema.json",
    "approvals.yaml": ROOT / "schemas/approvals.schema.json",
    "claims.yaml": ROOT / "schemas/claims.schema.json",
}


def main() -> int:
    errors = []
    manifests = sorted(TUTORIALS.glob("*/tutorial.yaml"))
    if not manifests:
        errors.append("no tutorial manifests found")
    for manifest in manifests:
        tutorial_dir = manifest.parent
        tutorial = yaml.safe_load(manifest.read_text())
        for name, schema_path in SCHEMAS.items():
            path = tutorial_dir / name
            if not path.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing")
                continue
            data = yaml.safe_load(path.read_text())
            schema = json.loads(schema_path.read_text())
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
                loc = ".".join(map(str, error.path)) or "<root>"
                errors.append(f"{path.relative_to(ROOT)}:{loc}: {error.message}")
        for label, relative in tutorial.get("files", {}).items():
            if not (tutorial_dir / relative).exists():
                errors.append(f"{manifest.relative_to(ROOT)}: files.{label} missing: {relative}")
        states = set(tutorial.get("workflow", {}).get("states", []))
        required = {"received", "validated", "planned", "executing", "succeeded", "failed", "cancelled"}
        if not required.issubset(states):
            errors.append(f"{manifest.relative_to(ROOT)}: missing required states {sorted(required-states)}")
        if tutorial.get("risk", {}).get("tier") == "T4" and tutorial.get("status") not in {
            "withdrawn", "deprecated"
        }:
            errors.append(f"{manifest.relative_to(ROOT)}: T4 cannot be runnable/publishable")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Validated {len(manifests)} tutorial(s) against {len(SCHEMAS)} schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
