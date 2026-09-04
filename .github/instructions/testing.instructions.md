---
applyTo: "backend/tests/**,**/*test*.py"
---

- 70% coverage floor on new code, enforced in CI.
- Policy engine tests: one per rule type and per condition operator, not a single happy-path test, this module sits between an AI recommendation and a real security decision.
- Audit log tests: explicit tampered-entry and odd-count-of-leaves cases required, not just a clean-chain verification test.
- Integration test chaining the full decision path (classify to risk-score to trust-score to policy-gate to crypto-select to audit-log) is updated whenever a module's interface changes, not left stale.
- A pull request that changes a module's behavior without a corresponding test update is incomplete, flag it in review rather than merging it.
