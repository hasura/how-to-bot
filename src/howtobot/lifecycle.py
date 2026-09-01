"""Machine-testable tutorial lifecycle invalidation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MATERIAL_CHANGE_TYPES = {
    "permission",
    "policy",
    "runtime",
    "dependency",
    "model",
    "adapter",
    "incident",
}


def invalidate_for_material_change(
    manifest: dict[str, Any], *, change_type: str, changed_by: str
) -> dict[str, Any]:
    if change_type not in MATERIAL_CHANGE_TYPES:
        raise ValueError("change type is not material")
    if not changed_by.strip():
        raise ValueError("changed_by is required")
    updated = deepcopy(manifest)
    updated["status"] = "needs_retest"
    lifecycle = updated["lifecycle"]
    lifecycle["retest_required"] = True
    lifecycle["retest_reason"] = f"{change_type} change recorded by {changed_by}"
    return updated