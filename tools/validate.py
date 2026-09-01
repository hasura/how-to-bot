from __future__ import annotations

import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
import yaml

ROOT = Path(__file__).resolve().parents[1]
TUTORIALS = ROOT / "tutorials"
SCHEMAS = {
    "tutorial.yaml": ROOT / "schemas/tutorial.schema.json",
    "permissions.yaml": ROOT / "schemas/permissions.schema.json",
    "approvals.yaml": ROOT / "schemas/approvals.schema.json",
    "claims.yaml": ROOT / "schemas/claims.schema.json",
    "evaluation.yaml": ROOT / "schemas/evaluation.schema.json",
}
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
PLACEHOLDER_IDENTITIES = {
    "owner",
    "maintainer",
    "repository-steward",
    "tutorial-maintainer",
    "domain-owner",
    "domain-reviewer",
    "tutorial-domain-reviewer",
    "security-reviewer",
    "security-owner",
    "human-disposition-owner",
    "source-system-owner",
}
MATERIAL_CHANGE_TRIGGERS = {
    "permission",
    "policy",
    "runtime",
    "dependency",
    "model",
    "adapter",
    "incident",
}


def _validate_schema(path: Path, schema_path: Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"{path.relative_to(ROOT)}: missing")
        return {}
    data = yaml.safe_load(path.read_text())
    schema = json.loads(schema_path.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(map(str, error.path)) or "<root>"
        errors.append(f"{path.relative_to(ROOT)}:{location}: {error.message}")
    return data


def _is_placeholder(identity: object) -> bool:
    if not isinstance(identity, str) or not identity.strip():
        return True
    normalized = re.sub(r"\s+", "-", identity.strip().casefold())
    return normalized in PLACEHOLDER_IDENTITIES


def _validate_cross_file_contract(
    manifest: Path,
    tutorial: dict,
    documents: dict[str, dict],
    errors: list[str],
) -> None:
    tutorial_dir = manifest.parent
    relative_manifest = manifest.relative_to(ROOT)

    for label, relative in tutorial.get("files", {}).items():
        if not (tutorial_dir / relative).exists():
            errors.append(f"{relative_manifest}: files.{label} missing: {relative}")

    if tutorial.get("changelog") != tutorial.get("files", {}).get("changelog"):
        errors.append(f"{relative_manifest}: changelog and files.changelog must match")

    adapters = tutorial.get("adapters", [])
    tested_versions = tutorial.get("tested_versions", {})
    for adapter in adapters:
        adapter_path = tutorial_dir / "adapters" / adapter / "adapter.yaml"
        if not adapter_path.exists():
            errors.append(f"{relative_manifest}: adapter manifest missing: {adapter_path}")
            continue
        adapter_data = yaml.safe_load(adapter_path.read_text())
        expected_version = tested_versions.get(f"{adapter}-adapter")
        if adapter_data.get("version") != expected_version:
            errors.append(
                f"{relative_manifest}: {adapter} version does not match tested_versions"
            )
        if adapter_data.get("tutorial_id") != tutorial.get("id"):
            errors.append(f"{relative_manifest}: {adapter} tutorial_id mismatch")

    for name in ("maintainer", "domain_owner", "security_exception_owner"):
        identity = tutorial.get("lifecycle", {}).get(name)
        if _is_placeholder(identity):
            errors.append(f"{relative_manifest}: lifecycle.{name} must name an accountable identity")

    disposition_actors = [
        actor
        for actor in tutorial.get("actors", [])
        if actor.get("id") == "final-disposition-owner"
    ]
    if len(disposition_actors) != 1 or _is_placeholder(disposition_actors[0].get("identity")):
        errors.append(f"{relative_manifest}: exactly one named final-disposition-owner is required")

    states = set(tutorial.get("workflow", {}).get("states", []))
    if states != REQUIRED_STATES:
        errors.append(
            f"{relative_manifest}: workflow.states must equal {sorted(REQUIRED_STATES)}"
        )

    triggers = set(tutorial.get("lifecycle", {}).get("material_change_triggers", []))
    if triggers != MATERIAL_CHANGE_TRIGGERS:
        errors.append(
            f"{relative_manifest}: material_change_triggers must equal "
            f"{sorted(MATERIAL_CHANGE_TRIGGERS)}"
        )

    discovery = tutorial.get("discovery", {})
    ownership = tutorial.get("ownership", {})
    progression = tutorial.get("progression", {})
    roles = set(discovery.get("roles", []))
    users = set(tutorial.get("outcome", {}).get("users", []))
    if roles != users:
        errors.append(
            f"{relative_manifest}: discovery.roles must equal outcome.users"
        )
    if ownership.get("mode") == "COMPLETE":
        done_condition = ownership.get("healthy_or_done_condition", "").casefold()
        if not any(term in done_condition for term in ("done", "terminal", "outcome", "stop")):
            errors.append(
                f"{relative_manifest}: COMPLETE ownership must state a verifiable done condition"
            )
    expected_stages = {"try_it", "run_repeatedly", "operate_safely"}
    if set(progression) != expected_stages:
        errors.append(
            f"{relative_manifest}: progression must define exactly {sorted(expected_stages)}"
        )

    status = tutorial.get("status")
    retest_required = tutorial.get("lifecycle", {}).get("retest_required")
    retest_reason = tutorial.get("lifecycle", {}).get("retest_reason")
    if retest_required and status != "needs_retest":
        errors.append(f"{relative_manifest}: retest_required=true requires status=needs_retest")
    if status == "needs_retest" and (not retest_required or not retest_reason):
        errors.append(
            f"{relative_manifest}: needs_retest requires retest_required=true and a reason"
        )
    if not retest_required and retest_reason is not None:
        errors.append(f"{relative_manifest}: retest_reason must be null when no retest is required")

    if tutorial.get("risk", {}).get("tier") == "T4" and status not in {
        "withdrawn",
        "deprecated",
    }:
        errors.append(f"{relative_manifest}: T4 cannot be runnable or publishable")

    for document_name in ("permissions.yaml", "approvals.yaml", "claims.yaml", "evaluation.yaml"):
        document = documents.get(document_name, {})
        if document and document.get("tutorial_id") != tutorial.get("id"):
            errors.append(f"{relative_manifest}: {document_name} tutorial_id mismatch")

    evaluation = documents.get("evaluation.yaml", {})
    if tutorial.get("evaluation", {}).get("fixture_version") != evaluation.get("fixture_version"):
        errors.append(f"{relative_manifest}: evaluation fixture-version mismatch")
    if tutorial.get("tested_versions", {}).get("fixture-set") != evaluation.get("fixture_version"):
        errors.append(f"{relative_manifest}: tested fixture-set version mismatch")


def main() -> int:
    errors: list[str] = []
    manifests = sorted(TUTORIALS.glob("*/tutorial.yaml"))
    if not manifests:
        errors.append("no tutorial manifests found")

    for manifest in manifests:
        tutorial_dir = manifest.parent
        documents: dict[str, dict] = {}
        for name, schema_path in SCHEMAS.items():
            documents[name] = _validate_schema(tutorial_dir / name, schema_path, errors)
        tutorial = documents.get("tutorial.yaml", {})
        if tutorial:
            _validate_cross_file_contract(manifest, tutorial, documents, errors)

    if errors:
        print("\n".join(errors))
        return 1
    print(f"Validated {len(manifests)} tutorial(s) against {len(SCHEMAS)} schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())