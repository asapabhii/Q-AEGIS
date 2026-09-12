# Q-AEGIS Shield: Master Implementation Roadmap

> **Target Audience:** AI Coding Agents & Human Developers
> **Scope:** This roadmap tracks the active and remaining implementation tasks for **Udhav** and **Sukhmani**. (Abhinav's work is excluded from this document per `WORK_DIVISION.md`).
> **Goal:** Provide highly structured, AI-friendly task breakdowns with embedded XML prompts, context references, and verification checkpoints.
> Design prerequisite: before designing any screen, layout, component, animation, interaction, or user-facing copy, read both `frontend/agentDocs/uiDesignSkill.md` and `frontend/agentDocs/designDoc.md`. Review the planned work against those documents before writing code. This requirement applies to every frontend design task in Phases 1–5, even where a task prompt lists additional references.

---

## 📊 Module Ownership & Actual Status

*Status is based on the actual codebase state as of Phase 4.*

### Udhav (Backend: Policy, Crypto, Audit, Scheduler)
| Module | SPEC.md Section | PRD Requirement | Status |
|--------|-----------------|-----------------|--------|
| Policy Engine | 3.6 | FR-5 | ✅ Complete |
| Crypto Engine | 3.7 | FR-6 | ✅ Complete |
| Audit Log | 3.8 | FR-7 | ✅ Complete |
| Crypto-Shredding | 3.9 | FR-8 | ✅ Complete |
| Migration Scheduler | 3.10 | FR-9 | ❌ Not Started |

### Sukhmani (Frontend, Testing, Documentation)
| Module | SPEC.md Section | PRD Requirement | Status |
|--------|-----------------|-----------------|--------|
| Sensitivity Classifier | 3.2 | FR-1 | ✅ Complete |
| Quantum Upload UI | 3.13 | FR-12 | ✅ Complete |
| Risk Dashboard UI | 3.13 | FR-14 | ✅ Complete |
| Override Console UI | 3.13 | FR-12 | ✅ Complete |
| Rule Studio UI | 3.13 | FR-13 | ✅ Complete |
| Audit Viewer UI | 3.13 | FR-15 | ❌ Not Started |
| Summary Report UI | 3.13 | FR-16 | ❌ Not Started |
| Cross-Module Tests | 4 | N/A | ❌ Not Started |

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
| **Product Requirements** | `PRD.md` | System requirements, functional requirements (FR-01 to FR-18), and acceptance criteria. |
| **Agent Standing Orders** | `AGENTS.md` | Security and version control standing orders, ownership rules, and coding standards. |
| **Work Division** | `WORK_DIVISION.md` | Module ownership and sprint distribution. |

---

## 🎯 Active Tasks & AI Agent Prompts

### [UDHAV] Task 1: Migration Scheduler Implementation
**Target Files:** `backend/app/scheduler/prioritizer.py`, `backend/tests/test_scheduler.py`
**Dependencies:** Crypto profiles and data model (Phase 2 complete)

<task_prompt>
<role>You are Udhav, an expert backend Python engineer specializing in optimization algorithms and quantum computing simulations.</role>
<objective>Implement the Migration Scheduler (SPEC.md 3.10, PRD FR-9) to rank documents for post-quantum cryptographic upgrade.</objective>
<context>
The organization has a budget constraint on how many documents it can upgrade to full post-quantum (ML-KEM-1024) encryption. We must prioritize documents based on sensitivity, trust score, and access frequency.
</context>
<instructions>
1. Create `backend/app/scheduler/prioritizer.py`.
2. Implement three algorithms for comparison:
   - `greedy_baseline()`: Classical heuristic sorting.
   - `simulated_annealing_baseline()`: Metropolis-Hastings combinatorial optimization.
   - `qaoa_prioritize()`: A QAOA formulation using `qiskit` with a quantum ansatz statevector simulation.
3. Create `benchmark_all_methods()` to compare their outputs against the same constraint set (budget/bytes).
4. Create `backend/tests/test_scheduler.py` and write tests guaranteeing 70%+ coverage.
</instructions>
<verification>
- Run `pytest --cov=app --cov-fail-under=70`
- Ensure no external API calls are made during the Qiskit simulation (it must run in-process).
</verification>
</task_prompt>

**GitHub PR Checkpoint:** Requires Udhav's review before merge.

---

### [SUKHMANI] Task 2: Frontend Redesign - Screens 5 & 6
**Target Files:** `frontend/src/app/audit/[document_id]/page.tsx`, `frontend/src/app/documents/[id]/summary/page.tsx`
**Dependencies:** `globals.css` Design System, D3.js

<task_prompt>
<role>You are Sukhmani, an elite UI/UX frontend engineer specializing in React, Tailwind, and D3.js data visualizations.</role>
<objective>Redesign the remaining two frontend screens to strictly adhere to the "Quantum Futurism" aesthetic defined in FRONTEND_REDESIGN_COMPLETE.md.</objective>
<context>
The Audit Viewer and Document Summary screens are functionally complete but visually generic. They must be upgraded to match the deep-space glass-morphism aesthetic.
</context>
<instructions>
1. Modify `frontend/src/app/audit/[document_id]/page.tsx`:
   - Replace the vertical list with a D3.js blockchain-style visual chain.
   - Add verification cascade animations and hover glow effects.
2. Modify `frontend/src/app/documents/[id]/summary/page.tsx`:
   - Reuse the existing `TrustScoreConstellation` and `EncryptionTierBar` components.
   - Design a chronological event timeline.
3. Strictly use the existing color palette (violet-cyan spectrum, space blacks) and typography (Space Grotesk). No generic SaaS styling.
</instructions>
<verification>
- Run `npm run lint` and visually inspect the screens locally via `npm run dev`.
</verification>
</task_prompt>

---

### [SUKHMANI] Task 3: Cross-Module Integration Tests
**Target Files:** `backend/tests/test_integration_chain.py`, `frontend/src/**/*.test.tsx`
**Dependencies:** All backend modules (Phase 1-4) complete.

<task_prompt>
<role>You are Sukhmani, the QA lead responsible for full-system integrity and test authorship.</role>
<objective>Write a master integration test proving a document successfully traverses every single backend module, plus write Vitest components for the frontend.</objective>
<context>
Sukhmani owns cross-module testing. A document's lifecycle is meaningless if it cannot flow from classification all the way to a cryptographic audit entry.
</context>
<instructions>
1. Create `backend/tests/test_integration_chain.py`.
2. Write a single pytest suite that executes the full pipeline sequentially:
   - Classification -> Risk Score -> Trust Score -> Policy Gate -> Crypto Profile Selection -> Crypto Shredding.
3. Assert that the Audit Log contains exactly one valid entry for *each* decision, and the `prev_hash` chain is perfectly contiguous.
4. For the frontend, write Vitest tests in `frontend/src/` for critical UI components using `fireEvent.change`.
</instructions>
<verification>
- Run `pytest --cov=app --cov-fail-under=70` and ensure coverage does not drop.
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
*Last Updated: 2026-09-12*
*Aligns with Phase 4/5 of SPEC.md*
