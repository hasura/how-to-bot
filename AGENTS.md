# Instructions for AI contributors

1. Read `TUTORIAL_STANDARD.md`, `EVIDENCE_POLICY.md`, and the target tutorial manifests.
2. Never use real customer data unless explicit approval and repository-safe
   anonymization are documented. Prefer synthetic fixtures.
3. Do not weaken approval, authorization, idempotency, redaction, limits, or kill-switch
   behavior to make a test pass.
4. Do not claim “safe,” “reliable,” “portable,” or “production-ready” beyond recorded evidence.
5. Keep neutral workflow semantics separate from adapters.
6. Run all checks listed in the root README and report exact commands/results.
7. Never merge, publish, contact users, or mutate external systems without explicit authorization.
