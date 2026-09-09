# Q-AEGIS SHIELD: TECHNICAL SPECIFICATION

Version 3.0. This document defines how the system is built: architecture, algorithms, data model, and concrete technical decisions. What is being built and why, along with acceptance criteria, lives in `PRD.md`. Who builds what lives in `WORK_DIVISION.md`. Do not duplicate content across these three files, cross-reference instead, a document that repeats another document is a document that will drift out of sync with it.

---

## 0. Repository bootstrap

The repository starts empty. First actions, in order:

```bash
mkdir qaegis-shield && cd qaegis-shield
git init
mkdir -p backend/app/{classifier,risk_engine,agents,trust_engine,policy,crypto,audit,scheduler,graph,rag,api}
mkdir -p backend/tests frontend/src infra docs .github/instructions
```

Place `README.md`, `PRD.md`, `SPEC.md` (this file), `WORK_DIVISION.md`, and `AGENTS.md` at the repository root. Place Copilot's scoped instruction files in `.github/instructions/` and the repository-wide Copilot pointer at `.github/copilot-instructions.md`. Commit all of these before writing any application code.

---

## 1. System architecture

```
Data/Event Sources -> Event Bus -> AI Sensitivity Classifier
    -> [5 parallel risk agents: security, compliance, contextual, quantum-readiness, sustainability]
    -> Trust Score computation (consensus function)
    -> Deterministic Policy Gate (can override the AI outright)
    -> Crypto-Agile Protection Engine (AES-256 / Hybrid / Full Post-Quantum)
    -> Tamper-Evident Audit Log (Merkle tree, append-only)
    -> Protected Data Store
```

Side modules feeding the Trust Score computation: Knowledge Graph (attack-path reasoning) and Agentic RAG (grounded Q&A). A Migration Scheduler runs alongside the Crypto Engine, ranking documents for post-quantum upgrade. Visual reference: `docs/architecture-diagram.svg`.

---

## 2. Technology decisions and their justification

### 2.1 Multi-agent orchestration: LangGraph

AutoGen is in maintenance mode as of 2026; Microsoft's own documentation redirects new users to Microsoft Agent Framework. LangGraph is the current production-appropriate choice: explicit state graph, durable execution, built-in checkpointing, and native human-in-the-loop support, all four of which this system genuinely needs (checkpointing so a single agent timeout doesn't corrupt an assessment, human-in-the-loop for the manual override workflow specifically). CrewAI is faster to prototype with but does not offer the same checkpointing guarantees an auditable pipeline requires. Build Sections 5.4 and 5.5 on LangGraph.

### 2.2 Policy engine: decided, OPA with Rego

**Decided 2026-09-05: OPA, evaluated in-process from a WebAssembly bundle. Full reasoning in `docs/decisions.md`; read that entry before starting 3.6.** The paragraph below is the original framing, kept because the decision went against it and the reasons why are worth having side by side.

Original framing: OPA's commercial backer Styra had its core team acquired by Apple in August 2025; OPA itself remains CNCF-governed and actively used, but its commercial tooling ecosystem is less settled than it was. Independent benchmarking has found OPA's Rego language error-prone and non-deterministic in practice, versus AWS Cedar being deterministic by design with formal validation. Since this system explicitly requires a deterministic policy gate (PRD.md FR-5), Cedar is the better-aligned default, but this decision should be made by whoever implements Section 3.6, against real constraints encountered (ecosystem maturity, AWS tooling dependency, team familiarity), not defaulted to silently.

Three corrections that came out of making the call, recorded here so this paragraph is not read at face value. The "independent benchmarking" is a Teleport engineering blog post, and Teleport ships Cedar-adjacent tooling, so it is not a neutral source; several of its Cedar results were predicted rather than measured. Cedar's proven determinism property is order-independence, which this system does not use, because `policy_rules.priority` requires priority-ordered first match. And Cedar is an authorization engine answering Allow or Deny about a principal and a resource, which is a different question from the one FR-5 asks.

### 2.3 Event bus: Redis Streams vs Kafka, decided at implementation time

Start with Redis Streams, simpler to operate for a small team, sufficient durability and consumer-group support for expected volume. Move to Kafka only if a concrete need for partitioned, multi-consumer-group scale actually appears, not preemptively.

### 2.4 Vector store: pgvector vs Qdrant, decided at implementation time

Start with pgvector, since PostgreSQL is already in the stack and expected vector volume is well under the scale where a dedicated vector database earns its operational cost. Move to Qdrant only when RAG query latency or filtered-search performance becomes a measured problem.

---

## 3. Component specifications

Each module maps to exactly one PRD.md functional requirement and one backend subpackage. Read the corresponding PRD requirement's acceptance criteria before implementing.

### 3.1 Ingestion / Event Bus
Decouples "an event occurred" from "a module needs to process it." A document upload publishes `document.uploaded` with `{document_id, uploaded_by, storage_path}`. Every downstream module subscribes independently rather than being called directly. Validate event schema on both publish and consume.

### 3.2 Sensitivity Classifier
Implements PRD FR-1. Build order: a rule/keyword-based stub with a confidence heuristic first, the real ML model (Scikit-learn to start) only once a labelled dataset exists (see PRD Section 9's dependency note). Confidence below the defined threshold defaults to the more sensitive label, this behavior is load-bearing for the system's entire security posture and must have its own explicit test, not just happy-path coverage. API contract: `POST /classify` accepts a document reference, returns `{sensitivity_label, confidence, model_version, is_defaulted}`. Every classification record includes the model version that produced it.

### 3.3 Contextual Risk Engine
Implements PRD FR-2. Recomputes on a defined schedule and on trigger events (new device login, after-hours access), not once at upload. Writes to `risk_scores`, with a `context_snapshot` jsonb column since the signal set will grow over time without requiring schema migrations for each new signal.

v1 is caller-triggered via `POST /api/v1/risk-scores`; scheduled recomputes and the event bus are later work (the Redis Streams vs Kafka choice in 2.3 stays open until then). The v1 snapshot is a closed five-field set (`actor_user_id`, `device_id`, `device_is_new`, `accessed_at`, `after_hours`); `risk_value` is this engine's own score, not the five-agent aggregate (`trust_scores.consensus_value`).

### 3.4 Multi-Agent Risk Assessment
Implements PRD FR-3. Five agents (security, compliance, contextual, quantum-readiness, sustainability) as parallel LangGraph nodes, not sequential calls. Each agent writes one row to `agent_outputs` including a `rationale` field, not only a numeric score, this is what powers the risk breakdown shown in the document summary report (PRD FR-16).

### 3.5 Trust Score Computation
Implements PRD FR-4. The consensus function combining the five agent outputs must be explicit, documented, and versioned, either a weighted average with published weights or a small explainable aggregator, never an opaque model call producing a number with no traceable reasoning. `trust_scores` is append-only; every row references the exact `agent_outputs` rows that produced it. If this function is ever replaced by a learned model, it inherits the same fail-safe defaulting rule as 3.2: ambiguity resolves toward less trust, never more.

v1 ships `POST /api/v1/trust-scores` (security analyst, security admin). The function is an equal-weight mean over exactly the five `AgentType` values; a partial set is 422. The five scores are caller-asserted until 3.4 exists to produce them. See `docs/decisions.md`.

### 3.6 Policy Engine
Implements PRD FR-5. Engine is OPA with Rego per Section 2.2. `policy_decisions.rule_id` is nullable, "no rule fired, AI recommendation stood" is the common case and must be modeled as such, not worked around with a placeholder rule. Testing requirement: one test per rule type and per condition operator (see `AGENTS.md`), this module sits directly between an AI recommendation and a real security decision.

Four constraints the 2.2 decision commits this module to:

- **Rules are data, not policy source.** `policy_rules.condition_expr` holds a serialised condition tree from FR-13's rule builder. One fixed, reviewed Rego module interprets those trees, passed in as input alongside the active rule set. Never generate Rego text from a stored rule, that is code generation from user input inside the security gate.
- **Evaluation is in-process.** Compile the Rego module to a WebAssembly bundle and evaluate it in the FastAPI process. No OPA sidecar and no network call, because the decision and its `audit_log` entry commit in one Postgres transaction and nothing in that transaction should depend on a socket.
- **Determinism is enforced by the build, not by review.** Ship a capabilities file listing only the built-ins the interpreter needs, and run `opa check --capabilities` in CI. A policy referencing anything outside it fails to compile. Note that `opa eval` does not honour capabilities for parsing, so the gate has to be `opa check`, and note that compiling to WebAssembly does not remove the network built-ins by itself, since availability depends on what the host runtime implements. The capabilities file is the control.
- **Priority-ordered first match.** `policy_rules.priority` is ascending, unique among active rules, and the first matching rule wins and is the single value written to `policy_decisions.rule_id`. Evaluating all matches and merging them is not equivalent and is not what FR-5 asks for.

v1 ships `POST /api/v1/policy-rules` (compliance officer) and `POST /api/v1/policy-decisions` (compliance officer, security admin). The condition language and evaluation input are closed; combinator depth is capped at 8 because Rego cannot recurse. See `docs/decisions.md`.

### 3.7 Crypto-Agile Protection Engine
Implements PRD FR-6. Three profiles:
- **AES-256**: AES-256-GCM, classical baseline.
- **Hybrid**: `X25519MLKEM768` exactly, the named group already deployed in production TLS 1.3 by Chrome, Edge, and Cloudflare. Classical X25519 ECDH and ML-KEM-768 run in parallel and combine into one shared secret, so security holds even if only one of the two algorithms is ever broken. This defends against "harvest now, decrypt later" today while hedging against either algorithm individually failing, which is why this system defaults to hybrid rather than jumping straight to full post-quantum everywhere.
- **Full post-quantum**: ML-KEM-1024 (NIST security level 5) for key encapsulation, ML-DSA-87 for signatures, via `liboqs-python`.
Full parameter tables: Section 6. Security caveat, state this plainly anywhere this module's guarantees are described: liboqs is not independently audited, and OQS-OpenSSL is explicitly documented as development and interop-testing only, not production-supported. Every protection selection references the specific `trust_score_id` that drove it.

v1 ships `POST /api/v1/crypto-profiles` (security analyst, security admin). The body is a `trust_score_id` only; `profile_type` is computed from the stored `consensus_value`. A prior `policy_decisions` row for the same document is required (FR-6); the endpoint does not re-evaluate the gate and does not refuse persist because `final_decision` is `deny`. Selector thresholds remain uncalibrated placeholders. This endpoint does not encrypt or decrypt bytes. See `docs/decisions.md`.

### 3.8 Tamper-Evident Audit Log
Implements PRD FR-7. `build()` and `verify()` are pure functions with no side effects; verification must be independently re-runnable by a party that does not trust a stored "valid" flag. Enforce append-only behavior at the database level with a Postgres trigger rejecting UPDATE and DELETE on `audit_log`, do not rely on application-code discipline alone for a guarantee this central.

### 3.9 Crypto-Shredding
Implements PRD FR-8. Destroys the document's encryption key, not the audit log entry referencing it, the log entry proves the erasure request happened and when, the underlying data becomes permanently unreadable once its key is gone. Key destruction must be genuinely irreversible past the confirmation step, no soft-delete, no undo window.

### 3.10 Migration Scheduler
Implements PRD FR-9. Qiskit for a QAOA formulation of the prioritization problem, benchmarked against classical baselines (greedy allocation, simulated annealing) on the identical constraint set. No comparative claim about this module's effectiveness is made anywhere until that benchmark exists and shows it, per PRD FR-9's acceptance criteria and Risk R3.

### 3.11 Knowledge Graph
Implements PRD FR-10. Neo4j, deliberately kept separate from the relational schema (Section 5), since multi-hop relationship queries at depth are a poor fit for SQL joins and forcing them into the relational schema would misrepresent how this module is actually queried in practice.

### 3.12 Agentic RAG
Implements PRD FR-11. Pipeline of four distinct LangGraph nodes: Planner, Retriever, Reasoner, Verifier, not one prompt attempting all four responsibilities at once. Vector store per Section 2.4.

### 3.13 Frontend
Implements PRD FR-12 through FR-16. Six screens, each with a field-level specification and validation rules already documented in the system design reference (classification request, manual override, policy rule builder, risk dashboard, audit viewer, summary report). React/Next.js, TypeScript, Tailwind. Build directly against the existing field specs, they are implementation-ready.

---

## 4. Testing strategy

pytest, backend, 70% coverage floor on new code, enforced in CI. Integration test chaining the full decision path (classify to risk-score to trust-score to policy-gate to crypto-select to audit-log), updated whenever a module's interface changes, not left stale. Per-module testing requirements beyond the floor: Section 3's individual module entries and `AGENTS.md`.

## 5. Data model

Twelve core PostgreSQL tables: `users`, `documents`, `classification_metadata`, `manual_overrides`, `risk_scores`, `agent_outputs`, `trust_scores`, `policy_rules`, `policy_decisions`, `crypto_profiles`, `migration_schedule`, `audit_log`. The column-level data dictionary and the relationships between these tables live in `docs/data-dictionary.md`, which is the source of truth: this specification does not redefine the schema, it references it, and a column changes there in the same pull request as the migration that changes it. Earlier revisions of this section pointed at an external system design reference document that was never in this repository, so no one implementing a model could open it; that document is now cited as prior art inside `docs/data-dictionary.md`, with every deliberate departure from it listed and reasoned. Design principles worth restating here because they affect every module above: `classification_metadata`, `risk_scores`, `trust_scores`, and `crypto_profiles` are append-only history tables, never updated in place, a document's protection lifecycle only means something if past decisions are never silently overwritten. Neo4j (3.11) and the vector store (3.12) are deliberately excluded from the relational schema, they are separate, purpose-built stores, forcing a graph or similarity-search problem into relational tables would misrepresent how they're actually queried.

## 6. Encryption parameter reference

**ML-KEM (FIPS 203)**, key encapsulation, replaces Diffie-Hellman/ECDH:

| Parameter set | NIST security level | Approx. classical equivalent | Public key | Ciphertext | Shared secret |
|---|---|---|---|---|---|
| ML-KEM-512 | 1 | AES-128 | 800 bytes | 768 bytes | 32 bytes |
| ML-KEM-768 (hybrid default) | 3 | AES-192 | 1,184 bytes | 1,088 bytes | 32 bytes |
| ML-KEM-1024 (full PQC default) | 5 | AES-256 | 1,568 bytes | 1,568 bytes | 32 bytes |

**ML-DSA (FIPS 204)**, digital signatures, replaces RSA/ECDSA signing:

| Parameter set | NIST security level | Public key | Signature |
|---|---|---|---|
| ML-DSA-44 | 2 | ~1,312 bytes | ~2,420 bytes |
| ML-DSA-65 | 3 | 1,952 bytes | 3,309 bytes |
| ML-DSA-87 (full PQC default) | 5 | larger still | larger still |

ML-DSA's signing algorithm uses randomized, hedged signing with a rejection-sampling loop, meaning variable execution time by design, this resists fault-injection attacks that exploit deterministic signing. Do not attempt to make it constant-time without understanding what security property that would remove.

**SLH-DSA (FIPS 205)**: hash-based signatures, different mathematical assumptions than ML-KEM/ML-DSA, a hedge in case lattice-based assumptions are ever weakened. Significantly slower with much larger signatures. Use only for long-lived artifacts (root certificates), not as this system's general-purpose signature scheme.

**AES-256-GCM**: classical baseline, authenticated encryption, well understood, used for the AES-256 protection tier.

**Library**: `liboqs-python` for ML-KEM and ML-DSA. Pin the exact version in `requirements.txt`; re-run the full crypto test suite after any version bump, this library's API has changed before (the old Kyber implementation being dropped in favor of ML-KEM is a recent example). Never use the retired names CRYSTALS-Kyber or CRYSTALS-Dilithium in new code, comments, or documentation.

**Key management this phase**: environment-configured secrets, not a hardware security module, see PRD Non-Goal NG5. Document this plainly as a current limitation rather than implying hardware-backed protection that does not exist.

## 7. Build order

Status markers below describe what is actually merged to `main`, not what was planned. Update them in the pull request that lands the work, never ahead of it.

1. Repository scaffolding, environments, classifier stub, core audit log functions, initial CI. Complete.
2. **Current phase**: the data model (Section 5) as SQLAlchemy models plus Alembic migrations, the crypto-selector stub (3.7), and CI hardening with a coverage gate and branch protection. CI hardening, branch protection, the data model, and the crypto-selector stub are complete. The stub maps a trust score to a profile; it does not persist and does not take a ``trust_score_id`` until Phase 3.
3. Contextual risk engine (3.3), policy engine (3.6), replace the crypto-selector stub with real trust-score-driven selection (3.5 into 3.7). The Section 5 tables now exist, so risk scores, trust scores, and policy decisions have somewhere to persist. The policy engine decision (2.2) is made and logged, so 3.6 is unblocked. 3.3's scoring function and `POST /api/v1/risk-scores` are complete; recomputes are still caller-triggered, not scheduled, and no event bus is wired. 3.6's in-process WASM evaluator, `POST /api/v1/policy-rules`, and `POST /api/v1/policy-decisions` are complete. 3.5's equal-weight consensus and `POST /api/v1/trust-scores` are complete; the five agent scores are still caller-supplied until 3.4. 3.7 persist is complete: `POST /api/v1/crypto-profiles` writes a `crypto_profiles` row from a `trust_score_id` after a policy decision exists for that document. Selector thresholds are still uncalibrated placeholders. This endpoint does not encrypt bytes. Policy still takes `trust_score` as a caller-asserted fact.
4. Crypto-shredding (3.9), agentic RAG (3.12), knowledge graph (3.11).
5. Full LangGraph multi-agent orchestration (3.4), migration scheduler with real baseline benchmark (3.10).
6. Full evaluation against PRD Section 8's success metrics.

## 8. Environment setup

```bash
# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install fastapi uvicorn pydantic sqlalchemy alembic redis langgraph liboqs-python qiskit neo4j pgvector pytest black flake8 pytest-cov pip-audit

# frontend
cd frontend
npx create-next-app@latest . --typescript --tailwind --app

# infra
cd infra
# docker-compose.yml: postgres, redis, neo4j
```
