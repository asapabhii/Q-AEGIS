# Q-AEGIS SHIELD: PRODUCT REQUIREMENTS DOCUMENT

Version 1.0. This document defines what is being built and why, with measurable acceptance criteria per requirement. It does not define how, that is `SPEC.md`. It does not define who, that is `WORK_DIVISION.md`. Keep it that way, do not let implementation detail creep into this file or it stops being useful as a requirements reference.

---

## 1. Overview

Q-AEGIS Shield is a data governance platform that automatically classifies the sensitivity of a document, continuously evaluates the risk around it from multiple independent signals, and selects a matching strength of cryptographic protection in real time. Every decision the system makes is written to a permanent, independently verifiable record.

## 2. Problem Statement

Organizations today apply a single, uniform encryption policy to nearly all data they hold, regardless of how sensitive any individual piece of it actually is. This produces two concrete failures: computing and operational cost is wasted protecting low-value data at the same strength as high-value data, and genuinely sensitive data is frequently under-protected because nobody revisits the policy as risk changes. Separately, the cryptographic methods most systems depend on today have a known, finite lifespan against sufficiently advanced quantum computers, and adversaries are already capturing encrypted data now with the intention of decrypting it later once that capability exists. Existing tools address pieces of this (static encryption, static access control, separate compliance tooling) but none of them tie classification, continuous risk, cryptographic selection, and an immutable decision record into a single automated, auditable loop.

## 3. Goals

- G1: Automatically classify document sensitivity without requiring a human to pre-label every file.
- G2: Continuously reassess risk using signals beyond the document itself (user, device, network, behavior), not just once at upload.
- G3: Select cryptographic protection strength automatically, matched to current, continuously updated risk, not a static policy set once.
- G4: Produce a permanent, independently verifiable record of every decision the system makes, provable to a party that does not trust the team that built it.
- G5: Allow a deterministic, rule-based override of any AI recommendation, so a hard business rule can never be silently bypassed by a model.
- G6: Support the eventual, real (not simulated) migration of protected data to post-quantum-safe cryptography, prioritized by actual constraints rather than upgraded all at once.

## 4. Non-Goals

- NG1: A plugin marketplace for third-party or industry-specific agents. Not this phase.
- NG2: A quantitative incident-cost simulator (for example, projected ransomware recovery cost or downtime). Not built without a real actuarial model behind it, an unmodeled number is worse than no number.
- NG3: Live ingestion from third-party systems (Slack, GitHub, cloud storage providers, IoT devices, external identity providers). The architecture is designed to support this later; it is not wired this phase.
- NG4: Any production hosting, deployment, or public availability. This is a working prototype, not a shipped product, this phase.
- NG5: Hardware security module-backed key storage. Keys are environment-configured secrets this phase, see Section 7's non-functional security requirements for what that means in practice.

## 5. Target users

| Persona | Description | Primary need |
|---|---|---|
| Data Owner | Uploads documents, wants visibility into how their data was classified and protected | Trustworthy, exportable summary of what happened to a specific document |
| Security Analyst | Reviews low-confidence or flagged classifications | A fast, auditable way to override an AI decision with justification |
| Security Admin | Monitors risk across the whole document set, not one file at a time | A live, aggregate view of risk and protection status |
| Compliance Officer | Defines hard rules the AI cannot override, handles erasure requests | A rule authoring interface and a working erasure mechanism |
| Auditor | Must verify system integrity independently, does not take the team's word for it | A record that can be independently re-verified, not just displayed as "valid" |
| ML/Platform Engineer | Builds and maintains the agents and retrieval pipeline | Clear module boundaries and explainable agent outputs |

## 6. Functional requirements

Each requirement has an ID, a priority (P0 blocks release of that capability, P1 expected, P2 nice to have this phase), acceptance criteria, and a backlog reference for traceability. Full technical implementation detail for each is in the correspondingly numbered `SPEC.md` section, referenced per requirement.

### FR-1: Sensitivity Classification (P0, backlog PB-01, SPEC.md 5.2)
The system assigns a sensitivity label and a confidence score to every submitted document.
- Given a submitted document, the system returns a sensitivity label and a numeric confidence score.
- Given a confidence score below the defined threshold, the system defaults to the more sensitive label, never the less sensitive one.
- Every classification records which model version produced it.
- A document can be reclassified over time; prior classifications are never overwritten, only superseded by a new record.

### FR-2: Contextual Risk Scoring (P0, backlog PB-02, SPEC.md 5.3)
The system continuously computes a risk value from signals beyond document content.
- Risk recomputes on a defined schedule and immediately on defined trigger events (new device, after-hours access).
- Each risk computation records the specific signals that contributed to it.
- Risk scores are append-only; a new computation never overwrites a prior one.

### FR-3: Multi-Agent Risk Assessment (P0, backlog PB-02/PB-03 inputs, SPEC.md 5.4)
Five independent agents (security, compliance, contextual risk, quantum-readiness, sustainability) each score a given situation.
- All five agents execute in parallel for a given assessment, not sequentially.
- Each agent's output includes both a numeric score and a human-readable rationale.
- A single agent's failure or timeout does not silently corrupt or block the overall assessment; the failure is recorded and visible.

### FR-4: Trust Score Computation (P0, backlog PB-02/PB-03, SPEC.md 5.5)
The system combines the five agent outputs into one continuously updated trust score via an explicit, explainable consensus function.
- The consensus function's method (weights or aggregation logic) is documented and versioned, not an opaque black-box output.
- Every trust score computation references the exact agent outputs that produced it.
- Trust scores are append-only.

### FR-5: Policy Override Gate (P0, backlog PB-03, SPEC.md 5.6)
A deterministic rule layer can override any AI-generated recommendation.
- A compliance-authored rule, when its condition matches, produces the defined action regardless of what the AI recommended.
- The system records whether a given decision was overridden by a rule, and which rule, for every decision.
- The common case, no rule fires and the AI recommendation stands, is a normal, correctly modeled outcome, not a workaround.

### FR-6: Crypto-Agile Protection Selection (P0, backlog PB-04, SPEC.md 5.7)
The system selects one of three protection profiles (AES-256, hybrid, full post-quantum) based on the current trust score, after the policy gate.
- Every protection selection references the specific trust score that drove it.
- Profile selection is re-evaluated when the underlying trust score changes materially, not fixed permanently at first classification.

### FR-7: Tamper-Evident Audit Logging (P0, backlog PB-05, SPEC.md 5.8)
Every decision made anywhere in the pipeline (classification, risk score, agent output, trust score, policy decision, protection selection) is written to a permanent, chained, independently verifiable log.
- A verification operation can be run by a party independent of the system's operators and will detect any alteration to any prior entry.
- The log is structurally append-only; no code path can update or delete an existing entry.

### FR-8: Crypto-Shredding / Erasure (P1, backlog PB-06, SPEC.md 5.9)
A data owner's right-to-erasure request results in the underlying document becoming permanently unreadable, without deleting the audit trail that proves the request was made and honored.
- Erasure destroys the document's specific encryption key, not the audit log entries referencing it.
- Key destruction is irreversible once confirmed, no recovery path exists past that point.

### FR-9: Migration Prioritization (P1, backlog PB-07, SPEC.md 5.10)
The system ranks which protected documents should be upgraded to full post-quantum protection first, under a defined budget or time constraint.
- The ranking method is measured against at least one simpler baseline method on the same constraint set before any claim is made about its quality.
- Ranking output includes the specific constraint values used to produce it (not just the resulting order).

### FR-10: Knowledge Graph Reasoning (P2, backlog PB-09, SPEC.md 5.11)
The system can surface multi-hop relationships (employee, repository, vendor, cloud asset) relevant to an attack path that would not be visible from a single event in isolation.

### FR-11: Agentic Retrieval / Q&A (P2, backlog PB-08, SPEC.md 5.12)
A user can ask a natural-language question about a security event and receive an answer grounded in and verified against actual system records, not an unverified generated response.

### FR-12: Manual Override Workflow (P0, backlog PB-11, SPEC.md 5.13, Input Screen 2)
A Security Analyst can override an AI classification through a dedicated screen.
- Submission requires a justification of at least 20 characters.
- Submission requires explicit confirmation that the action will be permanently logged.
- The submit action is disabled until that confirmation is given.

### FR-13: Policy Rule Authoring (P0, backlog PB-12, SPEC.md 5.13, Input Screen 3)
A Compliance Officer can author a new override rule through a dedicated screen.
- A rule requires a unique name and at least one condition before it can be saved.
- A "test rule" action evaluates the rule against recent historical decisions without applying its action, before the rule goes live.

### FR-14: Risk Dashboard (P0, backlog PB-13, SPEC.md 5.13, Output Screen 1)
A Security Admin can view an aggregate, near-real-time view of risk and protection status across all monitored documents.

### FR-15: Audit Viewer (P0, backlog PB-14, SPEC.md 5.13, Output Screen 2)
An Auditor can view the full chained decision history for a specific document and independently trigger a full-chain verification.

### FR-16: Document Summary Report (P1, backlog PB-15, SPEC.md 5.13, Output Screen 3)
A Data Owner or Security Admin can generate an exportable (PDF and CSV) summary of a specific document's classification, protection, and risk breakdown.

---

## 7. Non-functional requirements

**Security**: full requirements live in `AGENTS.md`'s security section and are enforced there and in CI; this PRD does not duplicate them, it only asserts that every functional requirement above is subject to them without exception.

**Performance**: classification and risk scoring for a single document complete within a few seconds under normal load, this is a target for the prototype, not a contractually validated SLA. No functional requirement above is exempt from server-side validation regardless of latency pressure.

**Reliability**: a single agent (FR-3) or module failure degrades gracefully and is visibly recorded, it does not silently corrupt a downstream decision.

**Auditability**: every functional requirement that produces a decision (FR-1, FR-2, FR-4, FR-5, FR-6) must be traceable end to end through FR-7's audit log. A decision with no corresponding audit entry is a defect, not an edge case.

**Compliance-adjacent**: FR-8 exists specifically to satisfy right-to-erasure obligations (GDPR Article 17, India's DPDP Act) without breaking FR-7's immutability guarantee. Both requirements must hold simultaneously, neither is allowed to silently override the other.

## 8. Success metrics

- Classification accuracy and confidence calibration, measured against a held-out labelled set once FR-1's real model exists (the rule-based stub is not evaluated against this metric, it is not the target implementation).
- Audit log verification correctly detects 100% of injected tampering in test scenarios (FR-7), zero tolerance for false negatives on this specific metric.
- Policy override gate (FR-5) correctly applies the defined action for 100% of authored rule test cases, this module has zero acceptable failure rate given what it gates.
- Migration prioritization (FR-9) shows a measurable, reproducible difference against its classical baseline before any comparative claim is made anywhere.

## 9. Assumptions and dependencies

- A labelled dataset for FR-1's real model does not exist yet and is a dependency, not an assumption already satisfied, do not build the real model against synthetic or assumed labels.
- FR-10 and FR-11 depend on FR-4 and FR-7 being stable first, they are sequenced later in the build order for that reason (see `SPEC.md` Section 9).
- All personas in Section 5 are assumed to be internal to the organization deploying this system this phase; no external/public-facing access model is in scope.

## 10. Risks

- **R1**: the classifier's fail-safe default (FR-1) could be weakened or removed during a future refactor without anyone noticing, since it produces no visible error, only a quieter failure mode (under-flagging real sensitive content less often than intended). Mitigate with an explicit test case asserting the default-toward-sensitive behavior, not just a functional test of the happy path.
- **R2**: the policy gate (FR-5) is the single highest-consequence module in the system; a logic error here has a materially worse outcome than a similar error elsewhere. Mitigate with the per-rule-type test coverage requirement in `AGENTS.md`.
- **R3**: FR-9's migration prioritization risks being asserted as effective without the baseline comparison actually being run. Mitigate by treating the comparison as part of the requirement itself (see FR-9's acceptance criteria), not a follow-up task.

## 11. Release phases

Maps directly to `SPEC.md` Section 7's build order. Phase 1 (current): repo scaffolding, FR-1's stub, FR-7's core log functions, initial CI. Phase 2: crypto-selector stub, CI hardening with coverage gate and branch protection. Phase 3: FR-2, FR-5, and real trust-score-driven FR-6 (replacing the stub). Phase 4: FR-8, FR-11, FR-10. Phase 5: full FR-3 orchestration, FR-9. Phase 6: full evaluation against Section 8's success metrics.

## 12. Requirements traceability

| FR | Backlog ID | SPEC.md section | Primary owner |
|---|---|---|---|
| FR-1 | PB-01 | 5.2 | Sukhmani |
| FR-2 | PB-02 | 5.3 | Abhinav |
| FR-3 | PB-02/PB-03 | 5.4 | Abhinav |
| FR-4 | PB-02/PB-03 | 5.5 | Abhinav |
| FR-5 | PB-03 | 5.6 | Udhav |
| FR-6 | PB-04 | 5.7 | Udhav |
| FR-7 | PB-05 | 5.8 | Udhav |
| FR-8 | PB-06 | 5.9 | Udhav |
| FR-9 | PB-07 | 5.10 | Udhav |
| FR-10 | PB-09 | 5.11 | Abhinav |
| FR-11 | PB-08 | 5.12 | Abhinav |
| FR-12 | PB-11 | 5.13 | Sukhmani |
| FR-13 | PB-12 | 5.13 | Sukhmani |
| FR-14 | PB-13 | 5.13 | Sukhmani |
| FR-15 | PB-14 | 5.13 | Sukhmani |
| FR-16 | PB-15 | 5.13 | Sukhmani |
