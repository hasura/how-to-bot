# Evidence policy

Every material claim has a stable ID, exact text, source, date, scope, procedure,
limitations, working evidence references, and exactly one frozen label:

- **vendor_claim** — stated by a vendor; not independently confirmed.
- **documented** — supported by an authoritative specification or repository contract.
- **anecdotal** — a dated observation without a representative denominator.
- **demonstrated** — reproduced by a repeatable test for the exact stated version.
- **recurring** — repeatedly observed under a declared cadence and operating envelope.
- **measured** — supported by a representative denominator, method, and uncertainty.

No alternative label may appear in a claim manifest. In particular, the earlier
SOURCE/VERIFIED/OBSERVED/HYPOTHESIS vocabulary is retired.

Evidence strength still matters inside each label:

1. Assertion alone is insufficient.
2. Source-backed documentation supports principles, not runtime success.
3. Exact-version demonstration requires repeatable tests and raw results.
4. Independent reproduction must be performed by a non-author in a clean environment.
5. Operational measurement requires privacy-safe, representative longitudinal evidence.

Minimums: adapter compatibility requires `demonstrated`; T2+ compatibility additionally
requires independent reproduction. Reliability, safety, portability, and
production-ready claims require independent failure evidence plus an explicit operating
envelope; production claims additionally require representative operational measurement.
Automated checks never prove absence of unknown risk.

Claim wording must not exceed its evidence. A vendor source cannot prove a tutorial ran;
a synthetic demonstration cannot establish production accuracy; aggregate performance
cannot offset a failed critical privacy, authorization, approval, side-effect, recovery,
or stop invariant.