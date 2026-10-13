# Q-AEGIS Shield: Master Implementation Roadmap

> **Target Audience:** AI Coding Agents & Human Developers
> **Scope:** This roadmap tracks the active and remaining implementation tasks for **Udhav**, **Sukhmani**, and **Abhinav**.
> **Goal:** Provide highly structured, AI-friendly task breakdowns with embedded XML prompts, context references, and verification checkpoints.
> Design prerequisite: before designing any screen, layout, component, animation, interaction, or user-facing copy, read both `frontend/agentDocs/uiDesignSkill.md` and `frontend/agentDocs/designDoc.md`. Review the planned work against those documents before writing code. This requirement applies to every frontend design task in Phases 1–5, even where a task prompt lists additional references.

---

## 📊 Module Ownership & Actual Status

*Verified against code and merged PRs on 2026-09-15. "main" means merged to `origin/main`; "PR #24" means present only on `feature/phase4-crypto-scheduler`, the sole open PR.*

### Abhinav (Backend: Agents, Graph, RAG, Ingestion)
| Module | SPEC.md Section | PRD Requirement | Status |
|--------|-----------------|-----------------|--------|
| Ingestion / Event Bus | 3.1 | FR-2 (Partial) | ✅ Complete on main (Redis Streams, `qaegis:events`, outbox + consumer group, PR #25) |
| Contextual Risk API | 3.3 | FR-2 | ✅ Complete on main (caller-triggered + scheduled recompute + triggers, PR #25) |
| Multi-Agent Orchestration | 3.4 | FR-3 | ✅ Complete on main (LangGraph 5 parallel nodes, timeout fail-safe, `POST /assessments`, PR #25) |
| Trust Score Computation | 3.5 | FR-4 | ✅ Complete on main (versioned weighted consensus; weights calibrated to NIST/ISO policy weights — security+compliance co-lead 0.250/0.250/0.200/0.175/0.125, `trust-weighted-mean-1.0.0`, decisions.md 2026-09-23) |
| Knowledge Graph | 3.11 | FR-10 | 🟡 Mostly done on main (Neo4j attack paths, Bolt TLS, PR #28) — graph is populated by a synthetic **demo seed only**; no live event-bus sync, see "Needs to Be Connected" |
| Agentic RAG | 3.12 | FR-11 | ✅ Pipeline complete on main (4-node Planner→Retriever→Reasoner→Verifier on pgvector, PR #28); real fastembed embeddings shipped — `BAAI/bge-large-en-v1.5`, `vector(1024)` + HNSW cosine index (uncommitted on `feat/real-embeddings-fastembed`), replacing the earlier `stub-hash-v1` |
| Data model & migrations (§5) | 5 | all | ✅ Complete on main (12 tables, append-only triggers, PR #25 and follow-ups) |
| CI/CD, JWT/auth, TLS | — | — | ✅ Complete on main (coverage gate, branch protection, PR #27: JWT login, upload, SSE, local TLS) |

### Udhav (Backend: Policy, Crypto, Audit, Scheduler)
| Module | SPEC.md Section | PRD Requirement | Status |
|--------|-----------------|-----------------|--------|
| Policy Engine | 3.6 | FR-5 | ✅ Complete on main (OPA WASM in-process, capabilities gate in CI, per-operator tests) |
| Crypto Engine Profile Selection | 3.7 | FR-6 | ✅ Complete on main (trust-driven persist, PR #14; bands calibrated via #30 — see open conflict below) |
| Crypto Engine Byte Encryption | 3.7 | FR-6 | ✅ Complete on main (AES-256-GCM + X25519MLKEM768 + ML-KEM-1024/ML-DSA-87 via liboqs, fail-closed, PR #25) |
| Audit Log | 3.8 | FR-7 | ✅ Complete on main (Merkle build/verify, DB trigger, tampered + odd-leaves tests) |
| Crypto-Shredding | 3.9 | FR-8 | ✅ Complete on main (`POST /shred`, key destruction, audit preserved, PR #26) |
| Migration Scheduler | 3.10 | FR-9 | ✅ Complete on main (QAOA + greedy/annealing baselines on identical constraints, PR #26) |
| API error boundary | — | — | 🟡 In PR #24 only (global sanitized 500/422 handlers, `app/api/errors.py`, not yet merged) |

### Sukhmani (Frontend, Testing, Documentation)
| Module | SPEC.md Section | PRD Requirement | Status |
|--------|-----------------|-----------------|--------|
| Sensitivity Classifier Stub | 3.2 | FR-1 | ✅ Complete (keyword stub + one-step fail-safe escalation, explicit default test) |
| Sensitivity Classifier ML Model | 3.2 | FR-1 | ✅ Shipped (interim) — a calibrated linear SVM trained on a broad, public multi-genre corpus ships as `backend/artifacts/classifier/multigenre-hashing-svm-1.0.0.joblib` (streaming HashingVectorizer→TF-IDF→SGD, three ML tiers PUBLIC/CONFIDENTIAL/RESTRICTED; accuracy 0.886, macro F1 0.880); runtime engine `model_classifier.py` loads it when `CLASSIFIER_MODEL_PATH` is set, with the keyword rules and the high-precision content detectors (`detectors.py`) as escalation-only overrides and the low-confidence fail-safe preserved (decisions.md 2026-09-24). The earlier single-domain cables artifact is superseded and retained only for provenance. Retrain on gated FOIArchive pending Abhinav's HF terms acceptance |
| Upload / Classify UI | 3.13 | FR-1 screen | ✅ Complete (redesign on main; RoleContext refinements in PR #24) |
| Audit Viewer + Summary Redesign (Task 2) | 3.13 | FR-15/FR-16 | 🟡 Redesigned screens (`audit/[document_id]`, `documents/[id]/summary`, D3AuditChain, MetricCard, GSAP reveal) exist **in PR #24 only**; main has functional but unredesigned versions |
| Risk Dashboard UI | 3.13 | FR-14 | ✅ Complete on main (PR #22; SSE live updates via #27) |
| Override Console UI | 3.13 | FR-12 | ✅ Complete on main (PR #20, #16) |
| Rule Studio UI | 3.13 | FR-13 | ✅ Complete on main (PR #21, #17) |
| Audit Viewer UI | 3.13 | FR-15 | ✅ Complete on main (PR #19; D3 chain + verify cascade) |
| Summary Report UI | 3.13 | FR-16 | ✅ Complete on main (PR #26: export + shred trigger wired to `POST /shred`) |
| Frontend Crypto-Shredding | 3.9 | FR-8 | ✅ Complete (`shredDocument` client + data_owner-gated double-confirm UI) |
| Cross-Module Tests | 4 | N/A | ✅ Backend chain suite green; frontend 160/160 vitest green; backend coverage 86.68% |

## 🔗 Integration Status (verified 2026-09-15)

How the three workstreams fit together, and the one open conflict blocking PR #24.

**Merged to `main` (PRs #13–#22, #25–#28, #30).** End-to-end chain proven live against compose on 2026-09-15: register → classify → risk-scores → trust-scores → policy-decisions → crypto-profiles → audit verify (`is_valid: true`, roots match). Frontend↔backend contract verified: 28/30 routes wired, role header + JWT paths match, Decimal-as-string shapes aligned in `lib/api/types.ts`, CORS origins cover local dev. Backend pytest green at 86.68% coverage; frontend 160/160 vitest green with the 70% gate.

**In PR #24 only (open, textually MERGEABLE).** API error boundary (`errors.py` — the sanitized 500/422 handlers go live on `main` only when this merges), frontend Audit Viewer + Document Summary redesign (`audit/[document_id]/page.tsx`, `documents/[id]/summary/page.tsx`, D3 chain visual, MetricCard, useGsapReveal), RoleContext refinements + test hardening, `evaluator.rego`, mock-data contract alignment.

**✅ Resolved — PR #24 vs #30 calibration clash.** The concern was that PR #24 as
written silently reverted #30's calibration (crypto bands back to 0.4/0.8,
recommendation bands back to deny-0.300/MFA-0.800, `after_hours` back to
caller-required, `training.py` + `docs/classifier-dataset.md` deleted, the
2026-09-15 decision entries removed). Current `main`/working-tree state keeps
#30's calibration as the in-force contract: crypto selector bands are 0.50/0.85
(`trust-crypto-policy-bands-1.0.0`, `backend/app/crypto/selector.py`),
recommendation bands 0.250/0.500/0.750, `after_hours` is server-derived from
`org_timezone`, and the calibration decision entries stand in `docs/decisions.md`
(2026-09-15), joined by the 2026-09-23 trust-weight calibration
(`trust-weighted-mean-1.0.0`). The calibration is the source of truth; any branch
reintroducing the placeholder cut-points is the regression, not the baseline.

**Remaining gaps (in priority order).** Interim classifier model now ships — a
calibrated linear SVM over a broad, public multi-genre corpus
(`multigenre-hashing-svm-1.0.0.joblib`, decisions.md 2026-09-24), superseding the
earlier single-domain cables artifact; the gated FOIArchive retrain and the §8
held-out accuracy metric are what remain there. Real RAG embeddings shipped
(fastembed `BAAI/bge-large-en-v1.5`, 1024-dim, replacing the non-semantic
`stub-hash-v1`). The five scoring agents have been deepened past the earlier
`{label, risk, device_is_new, after_hours}` collapse: each now reads a distinct
subset of an immutable per-access `AccessFeatures` bundle (device/actor/document
history, role, payload), so SECURITY and CONTEXTUAL are no longer restatements of
the risk engine (scorer versions `*-det-2.0.0`; consensus weights and
`trust-weighted-mean-1.0.0` unchanged; decisions.md 2026-09-26). They remain
reviewable deterministic rules by design; the real LLM path is live and
key-gated on `AGENT_LLM_API_KEY`. Still open: measured latency/evaluation
artifacts for §8 metrics. Known hardening notes, unchanged: `AUTH_DEV_HEADER_BYPASS=true` pinned in compose (local-dev choice, CI unaffected); Neo4j Browser `:7474` plaintext loopback; no `frontend` service in compose so `NEXT_PUBLIC_API_URL` must be set manually (documented in `.env.example`).

## 🔌 Needs to Be Connected (wiring gaps, verified 2026-09-15)

Built but not yet joined to the rest of the system. Each item is small-to-medium wiring work, not a new module.

| # | What | Currently | Missing link | Owner |
|---|------|-----------|--------------|-------|
| 1 | PR #24 merge | Open PR carrying error boundary + frontend redesign | Calibration clash resolved (#30's bands + decision entries are the in-force baseline, see the ✅ note above); any merge must keep the 0.50/0.85 crypto bands, 0.250/0.500/0.750 recommendation bands, derived `after_hours`, and the calibration decision entries | Udhav + Abhinav |
| 2 | Neo4j graph population | `app/graph/seed.py` upserts a fixed synthetic demo topology | Subscribe to the Redis Streams bus (Task 6 output) so real users/documents/access events flow into Neo4j continuously; seed stays as demo fallback | Abhinav |
| 3 | RAG semantic retrieval | ✅ Real fastembed embeddings shipped (`BAAI/bge-large-en-v1.5`, `vector(1024)` + HNSW cosine index) behind the same `embed_text` interface, replacing `stub-hash-v1` | Done on `feat/real-embeddings-fastembed`; deterministic-hash embedder retained for hermetic tests only | Abhinav |
| 4 | Classifier ML model | ✅ Interim trained SVM ships (`multigenre-hashing-svm-1.0.0.joblib`, broad public multi-genre corpus), loaded by `model_classifier.py` when `CLASSIFIER_MODEL_PATH` is set; keyword + content-detector escalation-only overrides and the low-confidence fail-safe preserved | Retrain on gated FOIArchive once Abhinav accepts HF terms; interim artifact retired the day that lands | Abhinav |
| 5 | `errors.py` activation | Sanitized 500/422 global handlers live only on the #24 branch | Goes live automatically once #24 merges cleanly with #30 preserved | Udhav |
| 6 | Frontend service in compose | No `frontend` service in `infra/docker-compose.yml`; `NEXT_PUBLIC_API_URL` set by hand | Add a frontend service (or document-run script) so `docker compose up` is genuinely full-stack | Sukhmani |
| 7 | Dedicated end-to-end chain test | Chain covered piecewise across `test_api.py` flows, `test_audit_chain.py`, `test_api_persistence.py` | One `test_integration_chain.py` asserting full pipeline + contiguous `prev_hash` chain in a single run (Task 3 as specified) | Sukhmani |

---

## Master Technical Documentation & Reference Library

All AI agents and developers implementing tasks in this roadmap must consult the following canonical external and internal references before writing code.

### 1. Motion & Animation (GSAP)
| Technology / Topic | Official Documentation Link | Purpose & Architectural Usage |
|---|---|---|
| **GSAP Core API** | [GSAP Docs v3](https://gsap.com/docs/v3/) | High-performance animation primitives (`gsap.to()`, `gsap.fromTo()`, `gsap.timeline()`, `gsap.set()`). Used for clinical UI entrance and metric changes. |
| **GSAP in React & Next.js** | [GSAP React Guide](https://gsap.com/resources/React/) | Official framework best practices, handling `"use client"` hydration boundaries, and preventing SSR animation flicker. |
| **GSAP useGSAP Hook** | [useGSAP Hook Documentation](https://gsap.com/docs/v3/Plugins/useGSAP/) | Scoped animations, automatic context disposal, memory leak prevention, and safe DOM cleanup on React component unmount. |
| **GSAP Easing Cheat Sheet** | [GSAP Eases Visualizer](https://gsap.com/docs/v3/Eases/) | Pre-configured timing functions (`power2.out`, `expo.out`, `circ.out`). Essential for sharp, mechanical, military-grade UI transitions without bouncy/playful curves. |
| **GSAP Ticker** | [GSAP Ticker Documentation](https://gsap.com/docs/v3/GSAP/gsap.ticker/) | Centralized `requestAnimationFrame` heartbeat for synchronizing live threat feeds and high-frequency telemetry counters. |

### 2. UI Design System, Styling & Icons
| Technology / Topic | Official Documentation Link | Purpose & Architectural Usage |
|---|---|---|
| **Tailwind CSS v4** | [Tailwind CSS Docs](https://tailwindcss.com/docs) | Modern `@theme` configuration, utility classes, hairline borders (`0.5px`), and CSS variables. |
| **Tailwind Animations** | [Tailwind CSS Animation Docs](https://tailwindcss.com/docs/animation) | Custom keyframe definitions, opacity reveals, and transition-timing utilities. |
| **Lucide Icons** | [Lucide React Icon Directory](https://lucide.dev/icons/) | Searchable SVG icon library for cybersecurity tokens (`Shield`, `Cpu`, `Lock`, `Key`, `Terminal`, `Activity`, `Fingerprint`, `AlertTriangle`). |
| **Lucide React Package** | [Lucide React Guide](https://lucide.dev/guide/packages/lucide-react) | Tree-shaking, props (`size`, `strokeWidth={1.5}`), and color inheritance for technical badges. |

### 3. Frontend Framework & Architecture
| Technology / Topic | Official Documentation Link | Purpose & Architectural Usage |
|---|---|---|
| **Next.js App Router** | [Next.js App Router Documentation](https://nextjs.org/docs/app) | Layouts, sub-routes, route handlers, error boundaries, and dynamic routing (`[id]`, `[document_id]`). |
| **Server & Client Components** | [Next.js Composition Patterns](https://nextjs.org/docs/app/building-your-application/rendering/composition-patterns) | Architectural boundary rules: ensuring `"use client"` is applied only to interactive components using GSAP or hooks. |
| **Next.js Google Fonts** | [Next.js Font Optimization](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) | Zero layout shift font loading for `Inter` (sans) and `JetBrains Mono` (mono). |
| **TypeScript 5+** | [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html) & [Utility Types](https://www.typescriptlang.org/docs/handbook/utility-types.html) | Strict typing, Discriminated Unions, `Readonly<T>`, and schema validation contracts. |

### 4. Cryptography, Security & Policy Standards
| Technology / Topic | Official Documentation Link | Purpose & Architectural Usage |
|---|---|---|
| **NIST Post-Quantum Cryptography** | [NIST PQC Standards](https://csrc.nist.gov/projects/post-quantum-cryptography) | FIPS 203 (ML-KEM, key encapsulation) and FIPS 204 (ML-DSA, digital signatures). |
| **Open Quantum Safe (liboqs)** | [liboqs C Library](https://openquantumsafe.org/) & [liboqs-python](https://github.com/open-quantum-safe/liboqs-python) | Post-quantum cryptographic algorithms in Python (ML-KEM-1024, ML-DSA-87). *Must state in docstrings that liboqs is not independently audited.* |
| **Hybrid Key Exchange** | [IETF X25519MLKEM768 Draft](https://datatracker.ietf.org/doc/draft-kwiatkowski-tls-ecdhe-mlkem/) | TLS 1.3 hybrid classical + post-quantum key agreement specification. |
| **Open Policy Agent (OPA) / Rego** | [OPA Documentation](https://www.openpolicyagent.org/docs/latest/) | Declarative policy language, deterministic rule evaluation, and WASM in-process runtime. |

### 5. Backend, Database & Test Engineering
| Technology / Topic | Official Documentation Link | Purpose & Architectural Usage |
|---|---|---|
| **FastAPI** | [FastAPI Documentation](https://fastapi.tiangolo.com/) | High-performance async Python backend, routing, OpenAPI schema generation, and dependency injection. |
| **Pydantic v2** | [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/) | Strict data parsing, type validation, and serialization across API boundaries. |
| **SQLAlchemy 2.0 Async** | [SQLAlchemy Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) | Asynchronous Postgres ORM session management and queries. |
| **Pytest & Pytest-Cov** | [Pytest Docs](https://docs.pytest.org/en/stable/) / [Pytest-Cov](https://pytest-cov.readthedocs.io/) | Automated testing enforcing the mandatory 70% coverage floor. |
| **Vitest** | [Vitest Documentation](https://vitest.dev/guide/) | Fast unit and component test runner for React and jsdom. |

### 6. Repository Canonical Design Documents (Internal Source of Truth)
| Document | File Path | Focus Area |
|---|---|---|
| **Frontend UI Design Skill** | `frontend/agentDocs/uiDesignSkill.md` | Front-end development skill instructions, forbidden patterns (no shimmers, no purple/AI tropes), accessibility, and component standards. |
| **Frontend Design Doc** | `frontend/agentDocs/designDoc.md` | Detailed color palette, typography tokens, clinical cybersecurity aesthetic, micro-interactions, layout principles. |
| **Data Dictionary** | `docs/data-dictionary.md` | Source of truth for database schema, columns, types, constraints, and enums. |
| **Technical Specification** | `SPEC.md` | Architecture blueprint covering all 13 modules. |
| **Product Requirements** | `PRD.md` | System requirements, functional requirements (FR-1 to FR-16), and acceptance criteria. |
| **Agent Standing Orders** | `AGENTS.md` | Security and version control standing orders, ownership rules, and coding standards. |
| **Work Division** | `WORK_DIVISION.md` | Module ownership and sprint distribution. |

---

## 🎯 Active Tasks & AI Agent Prompts

*Status per task verified 2026-09-15. Task prompts retained below as history.*

### [UDHAV] Task 1: Migration Scheduler Implementation — ✅ DONE (PR #26 merged)
**Target Files:** `backend/app/scheduler/prioritizer.py`, `backend/tests/test_scheduler.py`
**Dependencies:** Crypto profiles and data model (Phase 2 complete)

<task_prompt>
<system_constraints>
- **Role:** You are Udhav, Lead Backend Engineer for Q-AEGIS Shield. You possess elite-level expertise in quantum computing algorithms, combinatorics, and high-performance Python optimization.
- **Rules of Engagement:** Adhere strictly to `AGENTS.md`. Do not commit credentials. All code must pass `black` and `flake8` linting automatically. 
</system_constraints>
<objective>
Implement the Migration Prioritization Scheduler (SPEC.md 3.10, PRD FR-9) to rank encrypted documents for Post-Quantum Cryptography (PQC) upgrades under a strict budget constraint.
</objective>
<context>
Post-quantum migration cannot happen overnight due to performance and bandwidth constraints. We must mathematically determine which documents are upgraded to ML-KEM-1024 first. The decision relies on three axes: document sensitivity, current Trust Score, and access frequency. 
</context>
<execution_steps>
1. **Initialize Module:** Scaffold `backend/app/scheduler/prioritizer.py`.
2. **Classical Baselines:** Implement two classical optimization approaches:
   - `greedy_baseline(docs, budget)`: Sort strictly by sensitivity/trust ratio.
   - `simulated_annealing_baseline(docs, budget)`: A Metropolis-Hastings probabilistic approach for better combinatorial bin-packing.
3. **Quantum Formulation (QAOA):** Implement `qaoa_prioritize(docs, budget)` using the `qiskit` library. Map the document prioritization constraints to a Quadratic Unconstrained Binary Optimization (QUBO) problem, then solve it using an in-process statevector simulator.
4. **Benchmarking:** Create a `benchmark_methods()` function that generates a synthetic dataset of 1,000 documents and evaluates all three algorithms on execution time and knapsack value.
5. **Testing:** Create `backend/tests/test_scheduler.py` ensuring the quantum statevector does not make external network calls (must remain in-process) and achieves >70% coverage.
</execution_steps>
<negative_constraints>
- DO NOT assert that QAOA is superior until the benchmark explicitly proves it against the simulated annealing baseline.
- DO NOT use external Qiskit cloud providers; local statevector simulation only.
</negative_constraints>
<verification>
- CI Check: `pytest --cov=app --cov-fail-under=70 backend/tests/test_scheduler.py`
</verification>
</task_prompt>

**GitHub PR Checkpoint:** Requires Udhav's review before merge.

---

### [UDHAV] Task 1.5: Crypto-Agile Byte Encryption — ✅ DONE (PR #25 merged)
**Target Files:** `backend/app/crypto/engine.py`
**Dependencies:** Crypto profiles (Phase 3 complete)

<task_prompt>
<system_constraints>
- **Role:** You are Udhav, Principal Cryptography Engineer. 
- **Rules of Engagement:** You are operating in a highly sensitive security context. DO NOT invent cryptographic primitives. Rely entirely on standardized `liboqs-python` and the built-in `cryptography` libraries.
</system_constraints>
<objective>
Execute the Crypto-Agile Protection Engine (SPEC.md 3.7, PRD FR-6) to physically encrypt and decrypt document payload bytes using the selected profile tier.
</objective>
<context>
The current system successfully determines and persists whether a document needs AES-256, Hybrid, or Post-Quantum protection based on the Trust Score. However, it lacks the actual byte-mangling execution layer. We need to implement the encryption runners.
</context>
<execution_steps>
1. **Target:** Open `backend/app/crypto/engine.py`.
2. **Implement AES-256-GCM (Tier 1):** Use `cryptography.hazmat.primitives.ciphers.aead.AESGCM`. Ensure authenticated encryption (AEAD) is correctly wired.
3. **Implement Hybrid Encryption (Tier 2):** Implement the `X25519MLKEM768` draft specification. Perform classical X25519 ECDH in parallel with ML-KEM-768. XOR or KDF the two shared secrets together into the final symmetric payload key.
4. **Implement Post-Quantum (Tier 3):** Implement ML-KEM-1024 for Key Encapsulation (KEM) and ML-DSA-87 for Digital Signatures using `liboqs-python`. 
5. **Documentation Mandate:** You MUST explicitly state in the docstrings of `engine.py` that `liboqs` is heavily experimental, not FIPS-certified for production yet, and lacks independent auditing. 
</execution_steps>
<negative_constraints>
- DO NOT use deprecated algorithms (e.g., CRYSTALS-Kyber or CRYSTALS-Dilithium). Always refer to them as ML-KEM and ML-DSA.
- DO NOT attempt to make the ML-DSA signature rejection-sampling loop constant-time. It is variable-time by design to resist fault injection.
</negative_constraints>
<verification>
- Ensure correct ciphertext size mappings per SPEC.md Section 6.
- Run `pytest backend/tests/test_crypto.py`.
</verification>
</task_prompt>

---

### [UDHAV] Task 1.6: Crypto-Shredding / Erasure Implementation — ✅ DONE (PR #26 merged)
**Target Files:** `backend/app/crypto/shredder.py`
**Dependencies:** Audit Log (Phase 2 complete), Crypto Encryption (Task 1.5)

<task_prompt>
<system_constraints>
- **Role:** You are Udhav, Data Compliance & Integrity Architect.
- **Rules of Engagement:** `AGENTS.md` strictly dictates that the `audit_log` table is append-only and enforced by a PostgreSQL trigger. DO NOT attempt to write `UPDATE` or `DELETE` statements against the audit table under any circumstances.
</system_constraints>
<objective>
Implement Crypto-Shredding (SPEC.md 3.9, PRD FR-8) to support irreversible right-to-erasure obligations (GDPR Article 17) without compromising the immutable blockchain audit trail.
</objective>
<context>
When a user exercises their Right to Erasure, deleting the record from the database violates our tamper-evident Merkle tree requirement. To satisfy both legal and cryptographic constraints, we "shred" the data by permanently destroying the specific encryption key that protects the payload, rendering the ciphertext irreversibly unreadable while keeping the audit evidence intact.
</context>
<execution_steps>
1. **Target:** Open `backend/app/crypto/shredder.py`.
2. **API Endpoint:** Implement `POST /api/v1/documents/{id}/shred`. Ensure it verifies caller identity (Role: `data_owner` or `compliance_officer`).
3. **Key Destruction:** Implement logic to overwrite the document's symmetric key in the KMS/environment-store with cryptographically secure random bytes before unlinking it, ensuring no recovery path exists.
4. **Audit Logging:** Append a new entry to `audit_log` with the action `KEY_SHREDDED`. Ensure the `prev_hash` correctly points to the last action on the document.
</execution_steps>
<negative_constraints>
- DO NOT use soft-delete flags (e.g., `is_deleted = True`) on the document table.
- DO NOT implement an "undo window". Key destruction must be instantaneous and irreversible upon confirmation.
</negative_constraints>
<verification>
- Write a Pytest integration test that: (1) Encrypts a document, (2) Shreds the key, (3) Attempts to decrypt the document and asserts an explicit `DecryptionFailureError`.
</verification>
</task_prompt>

---

### [SUKHMANI] Task 2: Frontend Redesign - Screens 5 & 6 — 🟡 PARTIAL (redesigned screens exist in PR #24 only, not merged)
**Target Files:** `frontend/src/app/audit/[document_id]/page.tsx`, `frontend/src/app/documents/[id]/summary/page.tsx`
**Dependencies:** `globals.css` Design System, D3.js

<task_prompt>
<system_constraints>
- **Role:** You are Sukhmani, Elite UI/UX Frontend Architect.
- **Rules of Engagement:** Before writing a single line of React, you MUST read `frontend/agentDocs/uiDesignSkill.md` and `frontend/agentDocs/designDoc.md`. No exceptions.
</system_constraints>
<objective>
Redesign the functionally complete Audit Viewer and Document Summary screens (FR-15, FR-16) to strictly adhere to the "Quantum Futurism" aesthetic.
</objective>
<context>
The data logic works, but the UI is generic. The Q-AEGIS Shield platform requires a clinical, military-grade, deep-space glass-morphism aesthetic. Information density must be high, and micro-interactions must feel sharp and deliberate.
</context>
<execution_steps>
1. **Audit Viewer Refactor (`app/audit/[document_id]/page.tsx`):**
   - Strip out the current vertical generic list.
   - Implement a D3.js or SVG-based vertical blockchain-style visual chain to represent the Merkle tree.
   - Use `useGSAP` to orchestrate a "verification cascade" animation (nodes glowing sequentially from top to bottom) when the Auditor clicks the "Verify Chain" button.
2. **Document Summary Refactor (`app/documents/[id]/summary/page.tsx`):**
   - Integrate the existing `TrustScoreConstellation` and `EncryptionTierBar` components.
   - Build a highly dense, printable layout displaying the 5 Agent risk rationales in a grid using a hairline (`0.5px`) border aesthetic.
3. **Styling & Motion:**
   - Use Lucide React icons with `strokeWidth={1.5}`. 
   - Apply GSAP easing `power2.out` for all transitions. NO bouncy/playful animations.
   - Use only the predefined color variables (violet-cyan spectrum, deep space blacks) from `globals.css`.
</execution_steps>
<negative_constraints>
- DO NOT use generic SaaS styling (no soft drop shadows, no bubbly rounded corners).
- DO NOT use Tailwind's default `animate-pulse` or shimmer effects. Use precise GSAP timelines.
</negative_constraints>
<verification>
- Run `npm run lint`.
- Verify the GSAP animations do not cause SSR hydration mismatch errors.
</verification>
</task_prompt>

---

### [SUKHMANI] Task 2.5: Frontend Crypto-Shredding Wire-up — ✅ DONE (PR #26 merged; redesigned version in PR #24)
**Target Files:** `frontend/src/lib/api/client.ts`, `frontend/src/app/documents/[id]/summary/page.tsx`
**Dependencies:** Backend Crypto-Shredding (Task 1.6 complete)

<task_prompt>
<system_constraints>
- **Role:** You are Sukhmani, Elite UI/UX Frontend Architect.
- **Rules of Engagement:** Do not implement inline `fetch()` calls in components. All backend calls must route strictly through the centralized `client.ts` layer.
</system_constraints>
<objective>
Wire up the Crypto-Shredding endpoint (PRD FR-8) to the frontend client and implement the UI trigger in the Document Summary screen.
</objective>
<context>
The backend API for irreversible key destruction (`POST /api/v1/crypto-shredding`) is fully operational. However, the frontend currently has no way to trigger this GDPR Right to Erasure event. We must expose this capability to the `data_owner` through a secure, high-friction UI interaction to prevent accidental key shredding.
</context>
<execution_steps>
1. **API Client Update (`client.ts`):**
   - Export a new async function `shredDocumentKey(documentId: string, role: UserRole)`.
   - Wrap the `POST /api/v1/crypto-shredding` endpoint. The body requires `{"document_id": documentId}`.
2. **UI Implementation (`summary/page.tsx`):**
   - Add a high-visibility, high-friction "Shred Encryption Key" button.
   - Restrict this button so it is only visible when the user's role is `data_owner`.
   - Implement a double-confirmation state (e.g., clicking it changes it to "Confirm Irreversible Shred" before executing).
   - On success, redirect the user back to the dashboard or update the document status UI to explicitly show `ARCHIVED` / Shredded.
</execution_steps>
<negative_constraints>
- DO NOT use generic or soft language like "Delete Document". Use clinical terms like "Shred Encryption Key" to accurately reflect the cryptographic reality.
- DO NOT allow anyone except the `data_owner` to see or click this button.
</negative_constraints>
<verification>
- Run `npm test` to ensure existing Vitest coverage doesn't drop.
- Ensure the button renders properly under the "Quantum Futurism" aesthetic constraints (e.g., using `var(--status-fail)` red/magenta for destructive actions).
</verification>
</task_prompt>

---

### [SUKHMANI] Task 3: Cross-Module Integration Tests — 🟡 PARTIAL (chain covered piecewise; dedicated single-run suite missing, see Needs to Be Connected #7)
**Target Files:** `backend/tests/test_integration_chain.py`, `frontend/src/**/*.test.tsx`
**Dependencies:** All backend modules (Phase 1-4) complete.

<task_prompt>
<system_constraints>
- **Role:** You are Sukhmani, Lead QA and Automation Engineer.
- **Rules of Engagement:** You hold final accountability for full-system integrity. You must enforce the 70% coverage floor mandated by `AGENTS.md`.
</system_constraints>
<objective>
Author the master cross-module integration suite to mathematically prove that a document successfully traverses every single backend module without data corruption or audit gaps.
</objective>
<context>
The individual modules (Classification, Policy, Crypto) have unit tests, but the lifecycle of a document is meaningless if it cannot flow continuously from upload to cryptographic protection. We must prove the entire state machine works.
</context>
<execution_steps>
1. **Backend Integration (`backend/tests/test_integration_chain.py`):**
   - Write a single, massive pytest suite that executes the pipeline synchronously:
     `Register -> Classify -> Risk Score -> Trust Score -> Policy Gate -> Crypto Profile Selection -> Crypto Shredding`.
   - **Crucial Assertion:** Query the `audit_log` at the end of the test. Assert that there is exactly one valid entry for *every single action*, and that the `prev_hash` pointers form a perfectly contiguous cryptographic chain back to the Genesis hash.
2. **Frontend UI Tests (`frontend/src/**/*.test.tsx`):**
   - Write Vitest + React Testing Library tests for the new Audit Viewer and Document Summary components.
   - Mock the API responses in `client.ts`.
   - Use `userEvent` (not `fireEvent`) to simulate an Auditor clicking the "Verify Chain" button.
</execution_steps>
<negative_constraints>
- DO NOT write mock-heavy tests for the backend integration. Use the real SQLAlchemy SQLite in-memory test database and let the actual Postgres triggers (or their SQLite equivalents) fire.
</negative_constraints>
<verification>
- Run `pytest --cov=app --cov-fail-under=70`.
- Run `npm test -- --coverage`.
</verification>
</task_prompt>

---

### [SUKHMANI] Task 4: Sensitivity Classification ML Model — ✅ SHIPPED (interim; trained on public-domain WikiLeaks cables, gated-FOIArchive retrain pending — decisions.md 2026-09-24)
**Target Files:** `backend/app/classifier/model.py`, `backend/tests/test_classifier.py`
**Dependencies:** Labeled Dataset (PRD NG9)

<task_prompt>
<system_constraints>
- **Role:** You are Sukhmani, Lead Machine Learning Engineer.
- **Rules of Engagement:** Do not implement the model until the labeled dataset is confirmed available (PRD NG9). 
</system_constraints>
<objective>
Replace the current rule-based classification stub with a real Scikit-learn ML model (SPEC.md 3.2, PRD FR-1) and implement the critical fail-safe heuristic.
</objective>
<context>
The current classifier uses a static stub. We now have a labeled dataset to train a probabilistic model (e.g., Logistic Regression or SVM via `scikit-learn`). The most critical security feature of this module is the confidence threshold fail-safe: ambiguity must ALWAYS resolve toward higher protection.
</context>
<execution_steps>
1. **Model Pipeline (`backend/app/classifier/model.py`):**
   - Ingest the labeled dataset. Build a TF-IDF or simple embedding-based feature extractor.
   - Train a Scikit-learn model that outputs both a predicted class and a `predict_proba` probability distribution.
2. **Fail-Safe Implementation:**
   - Define a `CONFIDENCE_THRESHOLD` (e.g., 0.85).
   - If the top prediction's probability is below the threshold, the system MUST override the prediction and default to the most restrictive/sensitive label in the dataset.
3. **Database Telemetry:**
   - Update the API route so that the generated `classification_metadata` row records the exact model version, the raw confidence score, and a boolean `is_defaulted` flag.
</execution_steps>
<negative_constraints>
- DO NOT deploy deep learning / heavy PyTorch models. Stick to Scikit-learn for latency and memory efficiency during this phase.
- NEVER allow a low-confidence prediction to pass through un-flagged. The fail-safe is load-bearing for the system's security posture.
</negative_constraints>
<verification>
- `backend/tests/test_classifier.py`: Write an explicit, hardcoded test case that forces a 50/50 probability array into the model and asserts that the final output defaults to the `RESTRICTED` (highest) label.
</verification>
</task_prompt>

---

### [ABHINAV] Task 5: Multi-Agent Risk Orchestration — ✅ DONE (PR #25 merged; implemented as `backend/app/agents/graph.py`)
**Target Files:** `backend/app/agents/orchestrator.py`
**Dependencies:** LangGraph, Trust Score Computation (Phase 3 complete)

<task_prompt>
<system_constraints>
- **Role:** You are Abhinav, Lead AI & Platform Engineer.
- **Rules of Engagement:** Rely strictly on `langgraph`. Do not use `autogen` or `crewai` (SPEC.md 2.1).
</system_constraints>
<objective>
Implement the Multi-Agent Risk Assessment pipeline (SPEC.md 3.4, PRD FR-3) orchestrating five independent agents to feed the Trust Score.
</objective>
<context>
The Trust Engine currently receives mocked caller-asserted inputs. We need to replace this with real intelligence. The assessment consists of 5 parallel agents (Security, Compliance, Contextual, Quantum-Readiness, Sustainability). 
</context>
<execution_steps>
1. **Initialize StateGraph:** Create a LangGraph `StateGraph` in `backend/app/agents/orchestrator.py`.
2. **Define Nodes:** Implement a node for each of the 5 agents.
3. **Parallel Execution:** Wire the graph so the 5 nodes execute concurrently, not sequentially.
4. **Checkpointing & Persistence:** Implement durable execution with built-in checkpointing so a single agent timeout does not corrupt the entire assessment.
5. **Output Structure:** Ensure each agent outputs both a numeric `score` and a human-readable `rationale` to `agent_outputs`.
</execution_steps>
<negative_constraints>
- DO NOT use an opaque LLM prompt to compute the final aggregate number. The agents only output their individual rationales and scores; the mathematical Trust Engine (3.5) handles the consensus.
</negative_constraints>
<verification>
- Write a test `backend/tests/test_agents.py` proving parallel execution and resilient checkpointing on a simulated node failure.
</verification>
</task_prompt>

---

### [ABHINAV] Task 6: Event Bus & Async Ingestion — ✅ DONE (PR #25 merged)
**Target Files:** `backend/app/api/events.py`, `infra/docker-compose.yml`
**Dependencies:** Redis (already running)

<task_prompt>
<system_constraints>
- **Role:** You are Abhinav, Lead Platform Engineer.
- **Rules of Engagement:** Do not introduce Kafka unless explicitly justified. Use Redis Streams (SPEC.md 2.3).
</system_constraints>
<objective>
Implement the Event Bus (SPEC.md 3.1) and wire the Contextual Risk Engine (SPEC.md 3.3) for async recomputes.
</objective>
<context>
Currently, risk scores are triggered directly by synchronous API calls. To achieve continuous re-assessment, we need to decouple "an event occurred" from "recalculate risk".
</context>
<execution_steps>
1. **Event Bus:** Wire `Redis Streams` to handle `document.uploaded` and `user.activity` events.
2. **Publishers:** Update `documents.py` to publish an event on successful registration.
3. **Consumers:** Build a consumer group in the Contextual Risk engine to listen to the stream and trigger background risk recomputes.
4. **Schema Validation:** Enforce Pydantic validation on both publish and consume operations.
</execution_steps>
<negative_constraints>
- DO NOT use basic Redis Pub/Sub; it lacks durability. Use Redis Streams and Consumer Groups.
</negative_constraints>
<verification>
- Verify that publishing to the stream correctly triggers a new row in the `risk_scores` table asynchronously.
</verification>
</task_prompt>

---

### [ABHINAV] Task 7: Agentic RAG Pipeline — 🟡 PARTIAL (pipeline done, PR #28; embeddings still `stub-hash-v1`, see Needs to Be Connected #3)
**Target Files:** `backend/app/rag/pipeline.py`
**Dependencies:** `pgvector`

<task_prompt>
<system_constraints>
- **Role:** You are Abhinav, Lead AI & Data Engineer.
- **Rules of Engagement:** Do not introduce Qdrant yet. Stick to `pgvector` (SPEC.md 2.4).
</system_constraints>
<objective>
Build the Agentic Retrieval / Q&A pipeline (SPEC.md 3.12, PRD FR-11) for grounded security event querying.
</objective>
<context>
Users need to ask natural-language questions about security events and receive answers grounded strictly in system records, verified by a multi-step LLM pipeline to eliminate hallucinations.
</context>
<execution_steps>
1. **Vector Store:** Implement document/event embedding storage using `pgvector`.
2. **LangGraph Pipeline:** Build a 4-node StateGraph:
   - **Planner:** Translates user query into a search strategy.
   - **Retriever:** Queries `pgvector` and PostgreSQL.
   - **Reasoner:** Synthesizes the retrieved data.
   - **Verifier:** Double-checks the synthesized answer against the retrieved records to ensure zero hallucination.
</execution_steps>
<negative_constraints>
- DO NOT use a single "mega-prompt" to do everything. You must implement the 4 distinct LangGraph nodes as specified.
</negative_constraints>
<verification>
- Run CI checks ensuring no external memory dependencies outside of Postgres.
</verification>
</task_prompt>

---

### [ABHINAV] Task 8: Knowledge Graph Integration — 🟡 PARTIAL (query engine done, PR #28; event-bus sync missing, see Needs to Be Connected #2)
**Target Files:** `backend/app/graph/neo4j_client.py`
**Dependencies:** Neo4j (already running)

<task_prompt>
<system_constraints>
- **Role:** You are Abhinav, Lead Platform Engineer.
- **Rules of Engagement:** `AGENTS.md` restricts adding Neo4j config variables in `.env` without the `QAEGIS_` prefix to prevent container crash loops.
</system_constraints>
<objective>
Implement the Neo4j Knowledge Graph (SPEC.md 3.11, PRD FR-10) to map multi-hop attack paths.
</objective>
<context>
Relational databases fail at multi-hop queries. We need a graph to link employees, devices, repositories, and documents to surface non-obvious attack vectors (e.g. Employee -> Uses Device -> Has Vulnerability -> Accesses Document).
</context>
<execution_steps>
1. **Connection Pooling:** Implement an async Neo4j driver connection.
2. **Event Sync:** Subscribe to the Redis Event Bus (Task 6) to ingest entities (users, documents) and edges (accessed, uploaded) into the graph continuously.
3. **Query Engine:** Write Cypher queries for the top 3 attack-path heuristics (e.g., restricted document accessed by a user connected to a compromised device).
</execution_steps>
<negative_constraints>
- DO NOT force graph relationships into the PostgreSQL relational schema. Neo4j is purpose-built for this; keep it fully decoupled.
</negative_constraints>
<verification>
- Execute a test Cypher query and assert correct node mapping.
</verification>
</task_prompt>

---

## 🚨 Critical Guidelines (Must Follow)

### 1. Security Rules (from AGENTS.md)
- **NEVER** write a secret, API key, or credential into code or committed config.
- **NEVER** rely on frontend UI hiding as access control. API endpoints must check caller identity (`users.role`) server-side.
- **NEVER** write `UPDATE` or `DELETE` against the `audit_log` table. It is strictly append-only.
- **ALWAYS** state clearly in docstrings that `liboqs` is not independently audited. Do not claim FIPS-certified guarantees the library doesn't back up.

### 2. Testing & Code Quality
- **70% coverage floor** on new backend code is enforced in CI, not advisory.
- The policy engine (3.6) requires one test per rule type and per condition operator.
- The audit log (3.8) requires explicit tampered-entry and odd-count-of-leaves test cases.

### 3. Git Workflow
- **NEVER** run `git commit`, `git push`, or `gh pr merge` autonomously.
- Always present the exact commands for a human to review and execute themselves.
- PRs touching `crypto/`, `policy/`, or `audit/` require Udhav's review.

---
*Last Updated: 2026-09-24 (classifier interim model, real fastembed RAG embeddings, calibrated trust weights, and the resolved #24/#30 calibration clash reconciled against code and `docs/decisions.md`; underlying status tables and task prompts otherwise verified 2026-09-15 and retained as history)*
*Aligns with Phase 4/5 of SPEC.md*
