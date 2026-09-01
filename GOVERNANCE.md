# Governance

## Roles

- **Repository steward:** maintains structure, validation, releases, and lifecycle state.
- **Tutorial maintainer:** owns correctness and review cadence for one tutorial.
- **Domain reviewer:** checks that the workflow matches the real job and boundaries.
- **Reproducibility reviewer:** reruns instructions from a clean environment.
- **Security/reliability reviewer:** required for T3 and available for escalations.

No author may self-certify independent reproduction. Reviewers may block publication
when evidence does not support a claim, controls are weaker than documented, or data
provenance is unclear.

## Decisions

Normative standard changes require a pull request, impact notes, migration guidance,
and steward plus reviewer approval. Tutorial publication follows its tier-specific
gates. Security fixes may be embargoed until a safe release is available.

## Maintenance

Review cadence: annually for T0–T1, every six months for T2, quarterly for T3, and
immediately after material incidents, permission changes, or platform/model changes.
Stale tutorials must be marked `deprecated` or `withdrawn`; they must not silently
retain a `published` status.
