# Governance

## Accountable owners for the Gate 2 pilot

- **Repository steward, tutorial maintainer, domain owner, disposition owner, and
  security-exception owner:** Anushrut Gupta.
- **Reliability/reproducibility reviewer:** independent reviewer bot
  `372780cd-861e-43a3-8b37-939b82cfa693`.

These identities apply to the current single-pilot Gate 2 scope. Future tutorials must
name their own accountable people; role placeholders do not satisfy the schema.

No author may self-certify independent reproduction. The reviewer may block merge or
publication when evidence does not support a claim, controls are weaker than documented,
or provenance is unclear.

## Decisions

Normative standard changes require a pull request, impact notes, migration guidance,
and steward plus independent-review approval. The frozen Gate 2 rubric may not be
weakened to make an implementation pass. Security fixes may be privately coordinated
until a safe patch exists.

## Maintenance and invalidation

Review cadence is annual for T0–T1, six-monthly for T2, quarterly for T3, and immediate
after material incidents or permission, policy, runtime, dependency, model, or adapter
changes.

Every material change invokes the lifecycle invalidation rule in
`src/howtobot/lifecycle.py`: status becomes `needs_retest`, `retest_required` becomes
true, and unsupported claims remain blocked until the complete gate and required
independent review pass again. Validator cross-file checks reject inconsistent status.

Issues: <https://github.com/hasura/how-to-bot/issues>. Sensitive vulnerabilities:
<https://github.com/hasura/how-to-bot/security/advisories/new>.

Stale or broken material must not remain current. Mark it `needs_retest` immediately,
then either restore evidence, migrate with a documented replacement, deprecate it, or
withdraw it. Record every state/version change in the tutorial changelog.