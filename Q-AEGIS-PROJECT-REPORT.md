Q-AEGIS SHIELD
A QUANTUM-AWARE, RISK-ADAPTIVE DATA GOVERNANCE AND CRYPTOGRAPHIC PROTECTION PLATFORM WITH TAMPER-EVIDENT AUDITING

A Project Report

Submitted in partial fulfilment of the requirements for the award of the degree of
Bachelor / Master of Computer Science

Department of Computer Science
CHRIST (Deemed to be University)


FORMATTING NOTE (delete before submission)
This document is deliberately written in plain text so it pastes cleanly into a word processor. There is no Markdown styling. Headings are written as plain numbered lines, apply your own heading styles. Tables are pipe-delimited ("|"), in a word processor use Convert Text to Table with "|" as the separator and then delete the dashed rule line under each header. Every figure is supplied as Mermaid source between BEGIN MERMAID and END MERMAID markers, paste each block into https://mermaid.live (or the Mermaid Chart plugin) to render and export the figure as PNG or SVG.


PROJECT TEAM AND WORK DIVISION

The project was executed by a three-member team. Ownership is by module, with a single final integration and merge authority to keep the pipeline coherent.

Member | Role | Modules and Responsibilities Owned
------ | ---- | ----------------------------------
Abhinav (Lead) | Project lead, architect, integration and merge authority | Repository setup, CI/CD pipeline and branch protection; the complete data model and persistence layer (all tables, SQLAlchemy models, Alembic migrations, database-level append-only enforcement); Contextual Risk Engine (FR-2); Multi-Agent Risk Assessment orchestration in LangGraph (FR-3); Trust Score consensus computation (FR-4); Knowledge Graph attack-path reasoning (FR-10); Agentic RAG pipeline (FR-11); event bus and vector-store technology decisions; final review and merge authority on all pull requests.
Udhav | Security and cryptography engineer | Deterministic Policy Override Gate on OPA/Rego (FR-5); Crypto-Agile Protection Engine (FR-6); Tamper-Evident Merkle Audit Log and post-quantum signed checkpoints (FR-7); Crypto-Shredding / erasure (FR-8); Migration Scheduler with QAOA and classical baselines (FR-9); required reviewer on all changes to the crypto, policy and audit modules.
Sukhmani | ML, frontend and quality engineer | Sensitivity Classifier and its training corpus and detectors (FR-1); the complete Next.js frontend, all operator screens (FR-12 through FR-16); documentation synchronisation across PRD, SPEC and API docs; test authorship across all modules; backlog maintenance.

Pull-request rule of record: any change touching the crypto, policy or audit modules requires Udhav's review before merge; every change ships with its test update in the same pull request; Abhinav holds final merge authority on the main branch.

ABSTRACT

Organisations today encrypt almost all data at a single uniform strength regardless of its true sensitivity, which simultaneously wastes computation protecting low-value data and under-protects genuinely sensitive data because no one revisits the policy as risk changes; meanwhile adversaries are already harvesting encrypted traffic to decrypt once quantum computers mature. Q-AEGIS Shield is a data governance platform that closes this gap by binding five stages into one automated, auditable loop. A fail-safe machine-learning classifier assigns a sensitivity label to every document; a contextual engine continuously scores risk from actor, device and time signals; five independent agents (security, compliance, contextual, quantum-readiness, sustainability) score the situation in parallel and are combined by a versioned consensus function into a Trust Score; a deterministic OPA/Rego policy gate can override the artificial-intelligence recommendation; and a crypto-agile engine selects AES-256, a hybrid post-quantum scheme, or full post-quantum protection accordingly. Every decision is written to an append-only, Merkle-chained audit log that is independently verifiable and anchored by post-quantum signatures. The prototype is complete end to end, passes 1,040 automated tests at 85.47 percent coverage of the served runtime, and demonstrates that risk-adaptive, quantum-aware, tamper-evident data protection is practical.

LIST OF TABLES

Table 2.1 — Target user personas
Table 2.2 — Comparison of existing approaches
Table 2.3 — Literature and standards reviewed
Table 2.4 — Feasibility summary
Table 2.5 — Functional requirements
Table 2.6 — Non-functional requirements
Table 2.7 — Software requirements
Table 2.8 — Hardware requirements
Table 3.1 — Backend module design
Table 3.2 — Database tables overview
Table 3.3 — Enumerated types
Table 3.4 to Table 3.20 — Data dictionary, one table per entity
Table 3.21 — Screens, routes and primary roles
Table 3.22 — Role-based access control matrix
Table 4.1 — Development environment components
Table 4.2 — Technologies and tools used
Table 4.3 — Trust Score consensus weights
Table 4.4 — Trust-to-crypto selector bands
Table 4.5 — ML-KEM-1024 parameters (FIPS 203)
Table 4.6 — ML-DSA-87 parameters (FIPS 204)
Table 4.7 — REST API endpoint catalogue
Table 4.8 — Key database migrations
Table 4.9 — Screenshot placeholders
Table 5.1 — Test suite composition
Table 5.2 — Representative test cases and results
Table 6.1 — Outcomes against the stated goals


LIST OF FIGURES

Figure 3.1 — System architecture and processing pipeline (block diagram)
Figure 3.2 — Module and component dependency diagram
Figure 3.3 — Entity-Relationship diagram
Figure 3.4 — Data Flow Diagram, Level 0 (context diagram)
Figure 3.5 — Data Flow Diagram, Level 1 (major processes)
Figure 3.6 — Sequence diagram of the end-to-end assessment pipeline
Figure 3.7 — User interface navigation map
Figure 4.1 — Deployment and container topology
Figure 5.1 — Test distribution across the automated suite

ABBREVIATIONS

Abbreviation | Expansion
------------ | ---------
AES | Advanced Encryption Standard
API | Application Programming Interface
CI/CD | Continuous Integration / Continuous Delivery
CRUD | Create, Read, Update, Delete
DEK | Data Encryption Key
DFD | Data Flow Diagram
DLQ | Dead-Letter Queue
DPDP | Digital Personal Data Protection (Act, India)
ECDH | Elliptic-Curve Diffie-Hellman
ER | Entity-Relationship
FIPS | Federal Information Processing Standards
FR | Functional Requirement
GCM | Galois/Counter Mode
GDPR | General Data Protection Regulation
HNSW | Hierarchical Navigable Small World (vector index)
HSM | Hardware Security Module
JWT | JSON Web Token
KEM | Key Encapsulation Mechanism
LLM | Large Language Model
ML | Machine Learning
ML-DSA | Module-Lattice Digital Signature Algorithm (FIPS 204)
ML-KEM | Module-Lattice Key Encapsulation Mechanism (FIPS 203)
MFA | Multi-Factor Authentication
NIST | National Institute of Standards and Technology
OPA | Open Policy Agent
PQC | Post-Quantum Cryptography
QAOA | Quantum Approximate Optimization Algorithm
RAG | Retrieval-Augmented Generation
RBAC | Role-Based Access Control
REST | Representational State Transfer
RFC | Request For Comments
SGD | Stochastic Gradient Descent
SLH-DSA | Stateless Hash-based Digital Signature Algorithm (FIPS 205)
SSE | Server-Sent Events
STH | Signed Tree Head
SVM | Support Vector Machine
TLS | Transport Layer Security
UUID | Universally Unique Identifier
WASM | WebAssembly

CHAPTER 1 — INTRODUCTION

1.1 Introduction / Overview of the System

Q-AEGIS Shield is a data governance platform that automatically classifies the sensitivity of a document, continuously evaluates the risk surrounding it from several independent signals, and selects a matching strength of cryptographic protection in real time. Every decision the system makes is written to a permanent, independently verifiable record.

The central idea of the system is not any single algorithm or library but the bound pipeline that ties them together. When a document enters the system, a fail-safe machine-learning classifier assigns it a sensitivity label and a calibrated confidence. A contextual risk engine then derives a continuous risk value from the surrounding situation, who is acting, from which device, at what time. Five independent scoring agents, covering security, compliance, contextual risk, quantum-readiness and sustainability, evaluate the situation in parallel and each produce both a numeric score and a human-readable rationale. A versioned consensus function combines those five outputs into a single Trust Score. That Trust Score is then passed through a deterministic policy gate authored by compliance officers, which is able to override the artificial-intelligence recommendation outright. The resulting decision drives a crypto-agile protection engine that encrypts the document under one of three profiles: a classical AES-256 baseline, a hybrid classical-plus-post-quantum scheme, or full post-quantum cryptography. Finally, every step in that chain is committed to an append-only, Merkle-chained audit log that any auditor can re-verify independently, and whose roots are anchored on demand, at auditor request, by post-quantum digital signatures.

Alongside the main pipeline, three supporting modules deepen the platform's reasoning: a Neo4j knowledge graph that surfaces multi-hop attack paths across employees, repositories, vendors and cloud assets; an agentic retrieval-augmented question-answering pipeline that answers analyst questions strictly grounded in real system records and refuses when it cannot ground its answer; and a migration scheduler that ranks which encrypted documents should be upgraded to post-quantum protection first, using a quantum optimisation formulation benchmarked against classical baselines.

The platform is delivered as a browser-based operator console backed by a secured web service, and is used by seven distinct operator roles, from data owners through security analysts, security administrators, compliance officers, auditors, chief information security officers, and platform engineers.

1.2 Problem Statement

Organisations today apply a single, uniform encryption policy to nearly all the data they hold, regardless of how sensitive any individual piece of it actually is. This produces two concrete failures at once. First, computing and operational cost is wasted protecting low-value data at the same strength as high-value data. Second, and more seriously, genuinely sensitive data is frequently under-protected, because no one revisits the protection policy as the risk around that data changes over time.

Separately, the cryptographic methods most systems depend on today, principally RSA and elliptic-curve schemes, have a known and finite lifespan against a sufficiently advanced quantum computer. Adversaries are already capturing encrypted data now with the explicit intention of decrypting it later, once that capability exists, an attack pattern known as harvest-now-decrypt-later.

Existing tools address individual pieces of this problem, static encryption at rest, static access control, and separate compliance tooling, but none of them tie sensitivity classification, continuous risk evaluation, cryptographic selection, and an immutable decision record into a single automated and auditable loop. The absence of that loop is the problem this project addresses.

1.3 Objectives of the Project

The project is guided by six objectives, each of which is realised by a concrete module and is independently verifiable.

Objective 1: Automatically classify document sensitivity without requiring a human to pre-label every file, while guaranteeing that any uncertainty in the classifier resolves toward more protection, never less.

Objective 2: Continuously reassess risk using signals beyond the document itself, the acting user, the device, the time of access, and behaviour, rather than scoring risk only once at upload.

Objective 3: Select cryptographic protection strength automatically, matched to the current and continuously updated risk, rather than to a static policy fixed once at ingestion.

Objective 4: Produce a permanent, independently verifiable record of every decision the system makes, one that can be proved correct to a party who does not trust the team that built the system.

Objective 5: Allow a deterministic, rule-based override of any artificial-intelligence recommendation, so that a hard business or regulatory rule can never be silently bypassed by a model.

Objective 6: Support the eventual real, and not merely simulated, migration of protected data to post-quantum-safe cryptography, prioritised by actual operational constraints rather than upgraded all at once.

1.4 Scope of the Project

In scope for this phase is a complete, working prototype covering the full decision pipeline end to end: sensitivity classification, contextual risk scoring, five-agent parallel assessment, trust consensus, deterministic policy gating, crypto-agile encryption across the three profiles, crypto-shredding for the right to erasure, tamper-evident auditing with post-quantum-signed checkpoints, migration prioritisation, knowledge-graph attack-path reasoning, agentic grounded question answering, and a full operator console of screens covering classification, override, policy authoring, the risk dashboard, the audit viewer, and exportable document summaries. All access is role-based and enforced by the server, and all service-to-service traffic runs over Transport Layer Security.

Out of scope for this phase, and explicitly deferred, are: a plugin marketplace for third-party or industry-specific agents; a quantitative incident-cost simulator, which would require a real actuarial model to be meaningful; live ingestion from third-party systems such as Slack, code hosting, cloud storage or identity providers, though the architecture is designed to accept them later; any public production hosting or deployment; and hardware-security-module-backed key storage, keys in this phase are environment-configured secrets. These boundaries are recorded so that the platform is not represented as offering guarantees it does not yet make.

1.5 Significance of the Project

The significance of Q-AEGIS Shield lies in demonstrating that four capabilities usually delivered by separate, disconnected products, classification, continuous risk, cryptographic selection, and immutable audit, can be fused into one automated loop in which each stage feeds the next and the whole chain is provable after the fact. Three properties make the platform notable. It is risk-adaptive: protection strength tracks live risk rather than a policy set once. It is quantum-aware: it defends against harvest-now-decrypt-later attacks today through hybrid and full post-quantum cryptography, and it plans a prioritised migration path. And it is independently auditable: an external auditor can re-verify the entire decision history without trusting the operator, because verification is a pure recomputation over stored evidence, not a stored yes-or-no flag. Together these make the system a credible reference design for regulated environments, banking, healthcare, and government, where the cost of both over- and under-protection is high and where accountability must survive scrutiny.

CHAPTER 2 — SYSTEM ANALYSIS

2.1 Existing System

Data protection in most organisations today is assembled from several independent tools that were never designed to inform one another. Encryption at rest is typically applied uniformly by the storage layer or the database, using a single classical algorithm and a single key policy for all data. Access control is handled separately, usually as static role-based or attribute-based permissions that are reviewed infrequently. Data classification, where it exists at all, is often a manual tagging exercise performed once at creation and rarely revisited. Compliance and audit tooling is a further separate layer, frequently reduced to application logs that the operator itself writes and can, in principle, alter. Cryptographic agility is largely absent: migrating from classical to post-quantum algorithms is treated as a distant, all-at-once infrastructure project rather than a prioritised, ongoing activity.

The following table contrasts the prevailing approaches with what an integrated loop requires.

Table 2.2 — Comparison of existing approaches

Capability | Typical existing approach | Gap
---------- | ------------------------- | ---
Sensitivity classification | Manual tagging at creation, rarely revisited | No automation, no fail-safe, drifts out of date
Risk evaluation | One-time at ingestion, document-only | Ignores actor, device, time and behaviour; never recomputed
Encryption strength | Single uniform algorithm for all data | Over-protects trivia, under-protects sensitive data
Policy override | Buried in application code or absent | No deterministic, auditable rule layer above the model
Post-quantum readiness | Not addressed, or an all-at-once future project | No hybrid defence today, no prioritised migration
Audit and accountability | Operator-written logs, mutable | Not independently verifiable, tamper detection weak
Integration | Separate disconnected products | No single loop from classification to protection to proof

2.1.1 Limitations of the Existing System

The limitations that follow directly from this fragmented arrangement are concrete. Uniform encryption wastes computation on low-value data while leaving high-value data no better protected. Because risk is scored once and never revisited, a document whose surrounding risk rises, a new device, an after-hours access, a compromised account, retains whatever protection it was given at birth. Manual classification does not scale and is inconsistent between people. Because policy rules are embedded in code rather than expressed as reviewable data, a business or regulatory rule can be silently bypassed by a model or a code change with no visible failure. There is no defence at all against harvest-now-decrypt-later attacks, because classical algorithms are used exclusively and no migration is planned. Finally, when the audit trail is written and held by the same operator whose actions it records, it cannot satisfy an auditor who does not already trust that operator, which is exactly the auditor whose trust matters.

2.2 Proposed System

The proposed system, Q-AEGIS Shield, replaces this fragmented arrangement with a single automated and auditable loop. Each stage of the loop consumes the output of the previous stage, and every stage writes an immutable record of its decision. The pipeline is: fail-safe sensitivity classification, then continuous contextual risk scoring, then five parallel scoring agents, then a versioned trust consensus, then a deterministic policy gate that can override the artificial intelligence, then crypto-agile protection selection and encryption, then an append-only Merkle audit entry. Supporting the loop are the knowledge-graph attack-path module, the agentic grounded question-answering module, and the post-quantum migration scheduler.

The system is designed for seven internal operator roles. Their needs shaped the screen and access design.

Table 2.1 — Target user personas

Persona | Description | Primary need
------- | ----------- | ------------
Data Owner | Uploads documents and wants visibility into how their data was classified and protected | A trustworthy, exportable summary of what happened to a specific document
Security Analyst | Reviews low-confidence or flagged classifications | A fast, auditable way to override an artificial-intelligence decision with a justification
Security Admin | Monitors risk across the whole document set, not one file at a time | A live, aggregate view of risk and protection status
Compliance Officer | Defines hard rules the artificial intelligence cannot override, and handles erasure requests | A rule-authoring interface and a working erasure mechanism
Auditor | Must verify system integrity independently and does not take the operator's word for it | A record that can be re-verified independently, not merely displayed as valid
CISO | Needs a portfolio-level view of posture and quantum-migration progress | Aggregate posture, trend and migration-readiness reporting
ML / Platform Engineer | Builds and maintains the agents and the retrieval pipeline | Clear module boundaries and explainable agent outputs

2.2.1 Benefits of the Proposed System

Because classification, risk, trust, policy, protection and proof are bound into one loop, every protection decision is grounded in the current state of the data and its surroundings rather than a policy set once and forgotten. Protection strength is matched to risk, so computation is spent where it matters and sensitive data is not left under-protected. Every ambiguous case resolves toward more protection, never less, both in the classifier and in the trust engine, so the failure mode is conservative by construction. The deterministic policy gate sits above the artificial intelligence and can override it, which means a hard business or regulatory rule can never be silently defeated by a model. Post-quantum protection is available today through the hybrid and full profiles, and migration is prioritised rather than deferred, so harvest-now-decrypt-later exposure is actively reduced. The audit trail is append-only, Merkle-chained and anchored with post-quantum signatures, so any alteration to any past entry is detectable by a party who does not trust the operator. Finally, the erasure mechanism honours a right-to-erasure request by destroying the document's key while preserving the audit record that proves the request was made and honoured, so privacy and accountability hold simultaneously.

2.3 Literature Review

The design draws on established standards and peer-reviewed work rather than on novel cryptographic primitives; the novelty is the bound pipeline that combines them. The following sources were the primary references.

Table 2.3 — Literature and standards reviewed

Ref | Source | Relevance to Q-AEGIS
--- | ------ | --------------------
[1] | NIST FIPS 203, Module-Lattice-Based Key-Encapsulation Mechanism (ML-KEM), 2024 | Basis for the ML-KEM-1024 key encapsulation in the full post-quantum profile
[2] | NIST FIPS 204, Module-Lattice-Based Digital Signature Standard (ML-DSA), 2024 | Basis for ML-DSA-87 signing of audit checkpoints
[3] | NIST FIPS 205, Stateless Hash-Based Digital Signature Standard (SLH-DSA), 2024 | Reviewed as a signature alternative; ML-DSA chosen for size and speed
[4] | Laurie, Langley, Kasper, RFC 6962, Certificate Transparency, 2013 | Merkle tree, inclusion and consistency proof model adopted for the audit log
[5] | Merkle, A Digitized Signature and Public Key Cryptosystem, 1979 | Foundational hash-tree construction underpinning the audit chain
[6] | Farrell et al., X25519MLKEM768 hybrid key exchange for TLS 1.3 (IETF) | Exact named group used for the hybrid protection profile
[7] | Barker, NIST SP 800-57, Recommendation for Key Management | Key-lifecycle and crypto-agility guidance informing the selector
[8] | Farshim et al. and the harvest-now-decrypt-later threat literature | Motivation for post-quantum protection of long-lived data
[9] | Open Policy Agent and the Rego policy language documentation | Deterministic first-match policy gate compiled to WebAssembly
[10] | Farhi, Goldstone, Gutmann, A Quantum Approximate Optimization Algorithm, 2014 | QAOA formulation for the migration-prioritisation ranker
[11] | Lewis et al., Retrieval-Augmented Generation, 2020 | Grounded question-answering with a verifier refusal step
[12] | GDPR Article 17 (Right to erasure) and India's DPDP Act 2023 | Legal basis for the crypto-shredding erasure requirement
[13] | Reimers and Gurevych, Sentence-BERT, 2019 | Sentence-embedding basis for the retrieval store (BAAI bge-large-en-v1.5)
[14] | Pedregosa et al., scikit-learn: Machine Learning in Python, 2011 | Classifier training and calibration toolkit

2.4 Feasibility Study

The project was assessed across the four standard feasibility dimensions before build. In every dimension the conclusion was that a working, patent-credible prototype was achievable within the constraints of a small three-person build on commodity hardware, subject to the stated non-goals.

Table 2.4 — Feasibility summary

Dimension | Assessment | Conclusion
--------- | ---------- | ----------
Technical | All cryptographic primitives are standardised and available in open libraries (liboqs, cryptography); orchestration, retrieval and graph tooling are mature | Feasible; no unproven primitive is on the critical path
Economic | Built entirely on open-source components and commodity hardware; no per-seat licences | Feasible at zero external licensing cost
Operational | Runs as a local Docker stack; operator roles map to a small, well-understood screen set | Feasible for an internal prototype; production hosting is out of scope
Legal / compliance | Erasure design satisfies GDPR Article 17 and the India DPDP Act without breaking audit immutability | Feasible; the two obligations are reconciled by crypto-shredding
Schedule | Delivered in six sequenced phases against a defined build order | Feasible; all six phases completed

2.5 Functional Requirements

Sixteen functional requirements define the system's behaviour. Each has a priority (P0 blocks release of that capability, P1 expected, P2 nice to have this phase) and is traceable to a specification section.

Table 2.5 — Functional requirements

ID | Requirement | Priority | Summary of acceptance
-- | ----------- | -------- | ---------------------
FR-1 | Sensitivity Classification | P0 | Returns a label and confidence; low confidence defaults to the more sensitive label; records model version; reclassification supersedes, never overwrites
FR-2 | Contextual Risk Scoring | P0 | Recomputes on schedule and on trigger events; records contributing signals; append-only
FR-3 | Multi-Agent Risk Assessment | P0 | Five agents run in parallel; each returns a score and rationale; a single agent failure is recorded and does not corrupt the assessment
FR-4 | Trust Score Computation | P0 | Combines the five agent outputs via a documented, versioned consensus function; references exact inputs; append-only
FR-5 | Policy Override Gate | P0 | A matching compliance rule produces its action regardless of the artificial-intelligence recommendation; records whether and which rule overrode; no match is a first-class outcome
FR-6 | Crypto-Agile Protection Selection | P0 | Selects one of three profiles from the current trust score after the policy gate; references the driving trust score; re-evaluates on material change
FR-7 | Tamper-Evident Audit Logging | P0 | Every decision is written to a chained, append-only, independently verifiable log; any alteration is detectable
FR-8 | Crypto-Shredding / Erasure | P1 | Destroys the document's key, not the audit entries; key destruction is irreversible
FR-9 | Migration Prioritisation | P1 | Ranks documents for post-quantum upgrade under a budget constraint; measured against a simpler baseline; records the constraint values used
FR-10 | Knowledge Graph Reasoning | P2 | Surfaces multi-hop relationships relevant to an attack path not visible from a single event
FR-11 | Agentic Retrieval / Q&A | P2 | Answers a natural-language question grounded in and verified against actual records; refuses if ungrounded
FR-12 | Manual Override Workflow | P0 | Analyst overrides a classification; requires a 20-character justification and an explicit logging confirmation; submit disabled until confirmed
FR-13 | Policy Rule Authoring | P0 | Compliance Officer authors a rule; requires a unique name and one condition; a test action evaluates against recent decisions without applying
FR-14 | Risk Dashboard | P0 | Security Admin views an aggregate, near-real-time view of risk and protection across all documents
FR-15 | Audit Viewer | P0 | Auditor views the full chained history for a document and independently triggers full-chain verification
FR-16 | Document Summary Report | P1 | Data Owner or Admin generates an exportable (PDF and CSV) summary of a document's classification, protection and risk

2.6 Non-Functional Requirements

Table 2.6 — Non-functional requirements

Category | Requirement
-------- | -----------
Security | Server-side identity and role check on every endpoint; TLS in transit everywhere including local services; no secret in code or committed config; append-only audit enforced at the database, not only in code; crypto fails closed
Performance | Classification and risk scoring for a single document complete within a few seconds under normal load; no requirement is exempt from server-side validation under latency pressure
Reliability | A single agent or module failure degrades gracefully and is recorded visibly; it does not silently corrupt a downstream decision
Auditability | Every decision-producing requirement (FR-1, FR-2, FR-4, FR-5, FR-6) is traceable end to end through the FR-7 audit log; a decision with no audit entry is a defect
Compliance | FR-8 satisfies right-to-erasure obligations without breaking FR-7 immutability; both hold simultaneously
Maintainability | Each backend subpackage maps to exactly one specification module; module boundaries are structural, not cosmetic
Testability | Seventy percent coverage floor enforced in continuous integration; policy engine requires one test per rule type and operator; audit requires tamper and odd-leaf cases

2.7 Software Requirements

Table 2.7 — Software requirements

Layer | Component | Version
----- | --------- | -------
Language (backend) | Python (application and production image) | 3.13
Language (host tooling) | Python (developer host) | 3.10
Web framework | FastAPI | 0.141.1
Data validation | Pydantic and pydantic-settings | 2.13.5
ORM and migrations | SQLAlchemy / Alembic | 2.0.52 / 1.19.2
Database driver | psycopg (binary) | 3.3.5
Database | PostgreSQL with pgvector | pg17 / 0.4.1
Cache and event stream | Redis | 7
Graph database | Neo4j Community | 5
Agent orchestration | LangGraph | 0.6.11
Language-model client | anthropic | 1.8.0
Classical crypto | cryptography | 45.0.7
Post-quantum crypto | liboqs-python (liboqs 0.16.0) | 0.16.0
Quantum optimisation | Qiskit | 1.4.3
Embeddings | fastembed (BAAI bge-large-en-v1.5) | current pinned
Policy engine | opa-wasmtime (Rego compiled to WebAssembly) | 0.1.1
Auth | PyJWT / bcrypt | 2.10.1 / 4.3.0
Document extraction | pypdf / python-docx | 6.0.0 / 1.2.0
Frontend framework | Next.js (App Router, Turbopack) | 16.3.4
Frontend runtime | React / TypeScript | 19.2.8 / 5
Styling | Tailwind CSS | v4
Testing | pytest / pytest-cov / vitest | 9.1.1 / 7.1.0 / 3.2
Lint and format | black / flake8 | 26.5.1 / 7.3.0
Containerisation | Docker and Docker Compose | current

2.8 Hardware Requirements

The prototype targets a single developer workstation; no specialised hardware is required, and no hardware security module is used this phase (keys are environment-configured secrets).

Table 2.8 — Hardware requirements

Resource | Minimum | Recommended
-------- | ------- | -----------
CPU | 4 cores, x86-64 | 8 cores or more
Memory | 8 GB RAM | 16 GB RAM or more
Storage | 20 GB free (images, database, embeddings) | 40 GB SSD
GPU | Not required | Not required (embeddings run on CPU)
Network | Localhost only for the prototype | Localhost only for the prototype
Special | None (no HSM this phase) | None

CHAPTER 3 — SYSTEM DESIGN

3.1 System Architecture / Block Diagram

Q-AEGIS Shield is a three-tier system: a Next.js operator front end, a FastAPI application backend organised into single-responsibility modules, and a data tier of PostgreSQL (with pgvector), Redis Streams and Neo4j. The defining structure is the bound decision pipeline inside the backend: the output of each stage is the input of the next, and every stage emits an immutable audit record. Figure 3.1 shows the whole system; the shaded spine is the pipeline.

Figure 3.1 — System architecture and bound pipeline (paste the block below into https://mermaid.live)

BEGIN MERMAID
flowchart TB
    subgraph Client["Operator front end (Next.js, role-filtered)"]
        UI["16 role-scoped screens\nclassify, dashboard, agents, ask,\naudit, rules, override, migration, summary"]
    end

    subgraph API["FastAPI backend (/api/v1, JWT + role check)"]
        direction TB
        CLS["1. Classifier (FR-1)\nfail-safe, model + keyword escalation"]
        RISK["2. Risk Engine (FR-2)\ncontextual snapshot, scheduled + triggered"]
        AGENTS["3. Five Agents (FR-3)\nsecurity, compliance, contextual,\nquantum, sustainability (parallel)"]
        TRUST["4. Trust Engine (FR-4)\nversioned weighted consensus"]
        POLICY["5. Policy Gate (FR-5)\nOPA/Rego first-match, can override AI"]
        CRYPTO["6. Crypto Selector + Encrypt (FR-6)\nAES-256 / hybrid / full PQ, fail-closed"]
        AUDIT["7. Audit Log (FR-7)\nappend-only, Merkle-chained, PQ-signed"]
    end

    subgraph Side["Supporting modules"]
        SHRED["Crypto-shredding (FR-8)"]
        MIG["Migration scheduler (FR-9)\nQAOA vs baselines"]
        GRAPH["Knowledge graph (FR-10)\nNeo4j multi-hop"]
        RAG["Agentic RAG (FR-11)\nPlanner-Retriever-Reasoner-Verifier"]
    end

    subgraph Data["Data tier (TLS in transit)"]
        PG[("PostgreSQL + pgvector")]
        REDIS[("Redis Streams + outbox relay")]
        NEO[("Neo4j")]
    end

    UI --> API
    CLS --> RISK --> AGENTS --> TRUST --> POLICY --> CRYPTO --> AUDIT
    CRYPTO --> SHRED
    CRYPTO --> MIG
    AGENTS -. signals .-> GRAPH
    UI --> RAG
    RAG --> PG
    GRAPH --> NEO
    AUDIT --> PG
    API --> PG
    API --> REDIS
    RISK -. events .-> REDIS
END MERMAID

The front end never enforces access control on its own; it hides screens for usability, but every request is checked server-side against the caller's role. The pipeline stages communicate through the database and through a durable transactional outbox: a stage writes its result and an outbox row in one transaction, and a relay process drains the outbox to Redis Streams, so no event is lost if the message broker is briefly unavailable.

3.2 Module Design

Each backend subpackage maps to exactly one specification module; the separation is structural and is not merged for convenience. Table 3.1 lists the modules and their responsibilities, and Figure 3.2 shows their dependencies.

Table 3.1 — Backend module design

Module (package) | Responsibility | Key output
---------------- | -------------- | ----------
classifier | Assign sensitivity label and confidence; fail-safe upward | classification_metadata row
risk_engine | Build contextual snapshot; compute risk on schedule and triggers | risk_scores row
agents | Run five scoring agents in parallel via LangGraph, fail-safe on timeout | agent_outputs rows
trust_engine | Combine agent outputs via versioned weighted consensus | trust_scores row
policy | Evaluate first-match OPA/Rego rules; override AI or defer to it | policy_decisions row
crypto | Select profile from trust; encrypt fail-closed; manage keys | crypto_profiles + ciphertext
audit | Build append-only Merkle chain; sign checkpoints with ML-DSA-87 | audit_log + audit_checkpoints
scheduler | Rank documents for post-quantum migration (QAOA + baselines) | migration_schedule rows
graph | Multi-hop attack-path queries over Neo4j | attack-path result sets
rag | Grounded question answering with verifier refusal | grounded answer or refusal
audit (shred path) | Destroy a document key irreversibly, keep audit trail | key-destruction record
event_bus | Durable outbox, relay to Redis Streams, dead-letter queue | delivered domain events
api | HTTP routing, authentication, role checks, validation | REST responses
auth | JWT issue and verify; role resolution | authenticated principal

Figure 3.2 — Module dependency graph (paste into https://mermaid.live)

BEGIN MERMAID
flowchart LR
    api --> auth
    api --> classifier
    api --> risk_engine
    api --> trust_engine
    api --> policy
    api --> crypto
    api --> audit
    api --> scheduler
    api --> graph
    api --> rag
    classifier --> audit
    risk_engine --> agents
    risk_engine --> event_bus
    agents --> trust_engine
    trust_engine --> policy
    policy --> crypto
    crypto --> audit
    scheduler --> crypto
    event_bus --> risk_engine
    rag --> audit
    audit --> crypto
END MERMAID

The single most consequential module is the policy gate: it is the only place where a deterministic rule can override an artificial-intelligence recommendation, so a logic error there has a materially worse outcome than an error elsewhere. It is therefore required to have one test per rule type and per condition operator, not a single happy-path test.

3.3 Database Design

The relational store is PostgreSQL with the pgvector extension. Primary keys are server-generated UUIDs (a sequential integer would leak the total document count from a single id and cannot be written concurrently by several modules without contention). All timestamps are timestamptz, never naive. Every foreign key is indexed, because nearly every real query is "get everything for document X". Enums are native Postgres enum types; a new value is added by migration, not by writing an unconstrained string. jsonb is used in exactly three columns (risk_scores.context_snapshot, policy_rules.condition_expr, audit_log.payload); the rest of the schema is strongly typed on purpose.

3.3.1 Tables

There are twelve core domain tables plus the ciphertext store, the two audit-anchoring evidence tables, the transactional outbox, and the pgvector retrieval table. Table 3.2 lists them.

Table 3.2 — Database tables overview

Table | Purpose | Append-only
----- | ------- | -----------
users | Operator accounts, role, bcrypt password hash | No
documents | Document registry and current lifecycle status | No (status is a pointer)
classification_metadata | One row per classification run (FR-1) | UPDATE-rejected
manual_overrides | Analyst relabel actions with justification (FR-12) | No
risk_scores | One row per contextual risk recomputation (FR-2) | UPDATE-rejected
agent_outputs | Five rows per assessment, one per agent (FR-3) | No
trust_scores | One row per consensus recomputation (FR-4) | UPDATE-rejected
policy_rules | Compliance-authored override rules (FR-13) | No
policy_decisions | One row per gate evaluation, override flag (FR-5) | No
crypto_profiles | One row per protection selection (FR-6) | UPDATE-rejected
document_ciphertexts | Encrypted bytes + wrapped DEK (FR-6, FR-8) | No
migration_schedule | Post-quantum upgrade ranking (FR-9) | No
audit_log | One chained row per decision (FR-7) | UPDATE/DELETE/TRUNCATE-rejected
audit_signing_keys | ML-DSA-87 keypairs signing checkpoints (FR-7) | UPDATE/DELETE/TRUNCATE-rejected
audit_checkpoints | Signed Tree Heads over document chains (FR-7) | UPDATE/DELETE/TRUNCATE-rejected
event_outbox | Durable transactional outbox to Redis Streams | No (relay mutates status)
rag_chunks | Chunk text + vector(1024) embeddings (FR-11) | No

Append-only enforcement is at the database level, not by application convention. A plpgsql function qaegis_reject_append_only_write raises SQLSTATE 23001 (restrict_violation) from triggers named trg_{table}_no_{operation}. The four history tables block UPDATE only; the three audit-evidence tables block UPDATE, DELETE and TRUNCATE absolutely. TRUNCATE needs its own statement-level trigger because TRUNCATE does not fire row-level triggers. The honest limit is that a database superuser can drop a trigger; this stops every application path and every accidental migration, which is what it is for, and it is not claimed as a defence against a superuser.

Table 3.3 — Enumerated types

Enum | Values
---- | ------
user_role | data_owner, security_analyst, security_admin, compliance_officer, auditor, ciso, engineer
document_status | registered, uploaded, classified, protected, archived
sensitivity_label | PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
agent_type | security, compliance, contextual, quantum, sustainability
policy_action | allow, deny, require_mfa, force_pqc
crypto_profile_type | aes256, hybrid, post_quantum
migration_status | pending, in_progress, done

3.3.2 Data Dictionary

The column-level definition of each table follows. Types are Postgres types; "Null" states whether the column is nullable.

Table 3.4 — users

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no | Generated server-side, never client-supplied
name | varchar(120) | no |
email | varchar(255) unique | no | Login identity
role | user_role | no | One of the seven operator roles
password_hash | varchar(255) | yes | bcrypt hash for local JWT login; never plaintext
created_at | timestamptz | no | Defaults to now()

Table 3.5 — documents

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
uploaded_by | uuid FK to users.id | no | ON DELETE RESTRICT
filename | varchar(255) | no | Original filename, not the storage key
storage_path | varchar(500) | yes | Object-storage key; null until a file is stored
uploaded_at | timestamptz | no | Defaults to now()
current_status | document_status | no | The one mutable status pointer; every move is preserved in history

Table 3.6 — classification_metadata (append-only)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
sensitivity_label | sensitivity_label | no | The label acted on, after fail-safe escalation
confidence_score | numeric(5,4) | no | 0.0000 to 1.0000, CHECK enforced
model_version | varchar(30) | no | Which model produced the classification
is_defaulted | boolean | no | True when confidence fell below threshold and the fail-safe applied
classified_at | timestamptz | no | Indexed, defaults to now()

Table 3.7 — manual_overrides

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
overridden_by | uuid FK to users.id | no | Indexed
original_label | sensitivity_label | no | Snapshot of the label before the override
new_label | sensitivity_label | no | CHECK enforces it differs from original_label
justification | text | no | CHECK enforces at least 20 characters (FR-12)
overridden_at | timestamptz | no | Stamped under a per-document row lock so latest-order follows insert time

Table 3.8 — risk_scores (append-only)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
risk_value | numeric(5,4) | no | The contextual engine's own score, not the five-agent aggregate
model_version | varchar(30) | no | Formula that produced risk_value; bumped when any weight changes
context_snapshot | jsonb | no | Closed set: actor_user_id, device_id, device_is_new, accessed_at, after_hours (server-derived when omitted)
computed_at | timestamptz | no | Indexed; dashboard queries filter by recency

Table 3.9 — agent_outputs

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
risk_score_id | uuid FK to risk_scores.id | no | Indexed; five rows expected per risk score
agent_type | agent_type | no | security, compliance, contextual, quantum, sustainability
score | numeric(4,3) | no | 0.000 to 1.000, CHECK enforced
rationale | text | no | Human-readable, surfaced in the summary report

Unique on (risk_score_id, agent_type): one output per agent per assessment. The trust engine refuses to compute from anything other than exactly these five types; a partial set is a 422, not a silently short mean.

Table 3.10 — trust_scores (append-only)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
risk_score_id | uuid FK to risk_scores.id | no | Indexed; the assessment whose agent_outputs produced this score
consensus_value | numeric(4,3) | no | 0.000 to 1.000, CHECK enforced
consensus_version | varchar(30) | no | Version of the consensus function; current trust-weighted-mean-1.0.0
computed_at | timestamptz | no | Indexed, defaults to now()

Table 3.11 — policy_rules

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
rule_name | varchar(150) unique | no |
condition_expr | jsonb | no | Closed tree: combinators all/any/not, leaf ops eq/neq/gt/gte/lt/lte/in, fields sensitivity_label/risk_value/trust_score/ai_recommendation, max depth 8
action | policy_action | no | allow, deny, require_mfa, force_pqc
priority | int | no | CHECK positive; lower value evaluated first
active | boolean | no | Defaults true; unique partial index on priority where active is true
created_by | uuid FK to users.id | no | Indexed
created_at | timestamptz | no | Defaults to now()

Table 3.12 — policy_decisions

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
rule_id | uuid FK to policy_rules.id | yes | Null when no rule fired and the AI recommendation stood
ai_recommendation | policy_action | no | What the AI proposed before the gate
final_decision | policy_action | no | What the system acted on
overridden | boolean | no | CHECK: true exactly when final_decision differs from ai_recommendation
decided_at | timestamptz | no | Defaults to now()

Table 3.13 — crypto_profiles (append-only)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
trust_score_id | uuid FK to trust_scores.id | no | Indexed; the specific trust score that drove this choice
profile_type | crypto_profile_type | no | aes256, hybrid, post_quantum
selected_at | timestamptz | no | Indexed, defaults to now()

Table 3.14 — document_ciphertexts

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
crypto_profile_id | uuid FK to crypto_profiles.id | no | Indexed; the profile selection that drove this encryption
ciphertext | bytea | no | AES-256-GCM encrypted document bytes
nonce | bytea | no | Nonce for ciphertext
wrapped_dek | bytea | no | DEK and profile secrets wrapped under CRYPTO_MASTER_KEY
kem_ciphertext | bytea | yes | Null for aes256; hybrid/post-quantum KEM or signature envelope
algorithm | varchar(80) | no | For example AES-256-GCM, X25519MLKEM768+AES-256-GCM
created_at | timestamptz | no | Indexed, defaults to now()

Crypto-shredding (FR-8) overwrites or deletes wrapped_dek; the ciphertext may remain as proof that data existed, while becoming permanently undecryptable.

Table 3.15 — migration_schedule

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | no | Indexed
priority_rank | int | no | CHECK positive; scheduler output
scheduled_upgrade_date | date | yes | Null until scheduled
status | migration_status | no | pending, in_progress, done
constraint_snapshot | jsonb | no | The constraint values that produced this rank (FR-9)

Table 3.16 — audit_log (append-only against UPDATE, DELETE, TRUNCATE)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | yes | Null for events with no document (e.g. a rule being created)
actor_id | uuid FK to users.id | yes | The acting user; null for a system-raised event
event_type | varchar(60) | no | For example classification_completed, manual_override, crypto_profile_selected
payload | jsonb | no | The canonical event body that payload_hash is the hash of
payload_hash | char(64) | no | SHA-256 of the canonical serialisation of payload
prev_hash | char(64) | yes | payload_hash of the preceding row in the same chain; null on genesis
merkle_root_at_time | char(64) | no | Merkle root over the chain as of this row
frontier | jsonb | no | Merkle frontier as of this row, for O(log n) incremental appends
created_at | timestamptz | no | Indexed, defaults to now()

Chains are per document. Unique on (document_id, prev_hash) with NULLS NOT DISTINCT makes forks structurally impossible: two rows claiming the same predecessor is exactly a fork, and the null-distinct rule extends that to genesis so a chain cannot have two beginnings. The payload is stored (not just its hash) precisely so an auditor who does not trust the operator can confirm each hash matches the actual event data; verification recomputes the root from stored payloads and reads neither the frontier nor merkle_root_at_time back.

Table 3.17 — audit_signing_keys (append-only against UPDATE, DELETE, TRUNCATE)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
algorithm | varchar(32) | no | Signature algorithm, e.g. ML-DSA-87
public_key | text | no | Public key in the clear (hex), so an auditor can pin it out-of-band
wrapped_secret_key | bytea | no | Secret key wrapped under CRYPTO_MASTER_KEY, never stored in the clear
created_at | timestamptz | no | Indexed; active key is the latest row, so rotation is an INSERT

Table 3.18 — audit_checkpoints (append-only against UPDATE, DELETE, TRUNCATE)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | yes | ON DELETE RESTRICT; null for a checkpoint over the system chain
signing_key_id | uuid FK to audit_signing_keys.id | no | The key whose signature is stored here
tree_size | int | no | Number of leaves the signed root commits to
merkle_root | char(64) | no | Hex SHA-256 Merkle root at tree_size
signature | text | no | ML-DSA-87 signature over (tree_size, merkle_root, signed_at, document_id), domain qaegis-audit-sth-v1
signed_at | timestamptz | no | Indexed; part of the signed input
created_at | timestamptz | no | Defaults to now()

Table 3.19 — event_outbox (not append-only; the relay mutates status)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
event_type | varchar(60) | no | Same vocabulary as audit_log.event_type
payload | jsonb | no | The event body relayed to the stream
occurred_at | timestamptz | no | When the domain event happened
status | varchar(16) | no | CHECK IN (pending, sent, dead); the relay mutates this
attempts | int | no | CHECK >= 0; retry counter
next_attempt_at | timestamptz | no | Backoff schedule; hot relay query is a partial index on (next_attempt_at, created_at) where status = pending
last_error | text | yes | Last delivery error, for the dead-letter path
stream_id | varchar(64) | yes | Redis Streams id assigned on successful publish
published_at | timestamptz | yes | When the row reached the stream
created_at | timestamptz | no | Indexed, defaults to now()

Table 3.20 — rag_chunks (pgvector retrieval store)

Column | Type | Null | Notes
------ | ---- | ---- | -----
id | uuid PK | no |
document_id | uuid FK to documents.id | yes | ON DELETE CASCADE; nullable for non-document sources
source_type | varchar(80) | no | inventory, audit, etc.
source_id | varchar(120) | yes | Optional origin key
content | text | no | Chunk body
embedding | vector(1024) | no | Real fastembed width; default model BAAI/bge-large-en-v1.5
embedding_model | varchar(80) | no | Always names the embedder
metadata | jsonb | no | Defaults to {}
created_at | timestamptz | no | Defaults to now()

The stored vector width must match the configured embedding dimension; an HNSW cosine index backs similarity search. This table implements the vector-store decision and is deliberately not one of the twelve core domain tables; it must not substitute for Neo4j path queries.

3.4 Entity-Relationship Diagram

Figure 3.3 shows the relational entity model. Users and documents are the roots; each history table hangs off documents as a growing list rather than a single current row, which is why none carries a "current" flag. The optional side of a relationship (a nullable foreign key) is drawn with the circle marker.

Figure 3.3 — Entity-relationship diagram (paste into https://mermaid.live)

BEGIN MERMAID
erDiagram
    users ||--o{ documents : uploads
    users ||--o{ manual_overrides : performs
    users ||--o{ policy_rules : authors
    users |o--o{ audit_log : acts_in

    documents ||--o{ classification_metadata : classified_as
    documents ||--o{ manual_overrides : relabelled_by
    documents ||--o{ risk_scores : scored_by
    documents ||--o{ trust_scores : trusted_at
    documents ||--o{ policy_decisions : gated_by
    documents ||--o{ crypto_profiles : protected_by
    documents ||--o{ document_ciphertexts : stores
    documents ||--o{ migration_schedule : queued_in
    documents |o--o{ audit_log : recorded_in
    documents |o--o{ audit_checkpoints : anchored_by

    risk_scores ||--o{ agent_outputs : aggregates
    risk_scores ||--o{ trust_scores : consensus_over
    trust_scores ||--o{ crypto_profiles : drives
    crypto_profiles ||--o{ document_ciphertexts : encrypts_with
    policy_rules |o--o{ policy_decisions : matched_by
    audit_signing_keys ||--o{ audit_checkpoints : signs
END MERMAID

3.5 Data Flow Diagram

The context-level (level 0) diagram shows the system as a single process between the operator roles and the persistent stores. The level-1 diagram decomposes that process into the seven pipeline stages and the supporting modules.

Figure 3.4 — Data flow diagram, level 0 (context) (paste into https://mermaid.live)

BEGIN MERMAID
flowchart LR
    DO(["Data Owner"]) -->|upload document| SYS(("Q-AEGIS Shield"))
    SA(["Security Analyst"]) -->|override classification| SYS
    CO(["Compliance Officer"]) -->|author rule / erasure request| SYS
    AD(["Security Admin"]) -->|monitor risk| SYS
    AU(["Auditor"]) -->|verify chain| SYS
    SYS -->|classification, protection, proof| DO
    SYS -->|dashboards, answers| AD
    SYS -->|verification result| AU
    SYS <-->|read / write| DB[("PostgreSQL + pgvector")]
    SYS <-->|events| RS[("Redis Streams")]
    SYS <-->|attack paths| NEO[("Neo4j")]
END MERMAID

Figure 3.5 — Data flow diagram, level 1 (paste into https://mermaid.live)

BEGIN MERMAID
flowchart TB
    UP["Upload / register"] --> P1["1. Classify (fail-safe)"]
    P1 --> D1[("classification_metadata")]
    P1 --> P2["2. Score contextual risk"]
    P2 --> D2[("risk_scores")]
    P2 --> P3["3. Run five agents (parallel)"]
    P3 --> D3[("agent_outputs")]
    P3 --> P4["4. Compute trust consensus"]
    P4 --> D4[("trust_scores")]
    P4 --> P5["5. Evaluate policy gate"]
    P5 --> D5[("policy_decisions")]
    P5 --> P6["6. Select profile + encrypt"]
    P6 --> D6[("crypto_profiles / document_ciphertexts")]
    P1 & P2 & P4 & P5 & P6 --> P7["7. Append audit entry"]
    P7 --> D7[("audit_log / audit_checkpoints")]
    ASK["Ask a question"] --> R1["RAG: plan-retrieve-reason-verify"]
    R1 --> D8[("rag_chunks")]
    R1 -->|refuse if ungrounded| ANS["Grounded answer"]
END MERMAID

Figure 3.6 shows the runtime sequence of a single assessment, including the parallel fan-out to the five agents and the policy gate's ability to override.

Figure 3.6 — Assessment sequence (paste into https://mermaid.live)

BEGIN MERMAID
sequenceDiagram
    participant U as Operator
    participant API as FastAPI
    participant AG as Five Agents
    participant TR as Trust Engine
    participant PO as Policy Gate
    participant CR as Crypto Selector
    participant AU as Audit Log
    U->>API: request assessment (document_id)
    API->>AG: fan out (security, compliance, contextual, quantum, sustainability)
    par parallel
        AG-->>API: security score + rationale
    and
        AG-->>API: compliance score + rationale
    and
        AG-->>API: contextual / quantum / sustainability scores
    end
    Note over AG,API: a timed-out agent is recorded, not silently dropped
    API->>TR: aggregate five outputs
    TR-->>API: consensus trust score (versioned)
    API->>PO: gate (label, risk, trust, ai_recommendation)
    alt a rule matches
        PO-->>API: rule action overrides AI (rule_id set)
    else no rule matches
        PO-->>API: AI recommendation stands (rule_id null)
    end
    API->>CR: select profile from trust (fail-closed)
    CR-->>API: aes256 / hybrid / post_quantum
    API->>AU: append chained, hashed entry for every step
    AU-->>U: decision + audit reference
END MERMAID

3.6 User Interface Design

The front end is a Next.js App Router application with a single AppShell layout, a role-filtered navigation sidebar, and sixteen page routes. The front end never enforces access control on its own; it hides screens a role cannot use for usability only, and every underlying request is authorised server-side. The design maps each persona to the screens it needs, and it distinguishes input screens (where an operator acts) from output screens (where an operator reads).

Table 3.21 — Screens, routes and primary roles

Screen | Route | Kind | Primary role
------ | ----- | ---- | ------------
Classify / upload | / | Input | Data Owner
Manual override | /override | Input | Security Analyst
Policy rule authoring | /rules | Input | Compliance Officer
Ask (grounded Q&A) | /ask | Input | Any operator
Migration planning | /migration | Input | Security Admin, CISO
Risk dashboard | /dashboard | Output | Security Admin
Agents view | /agents | Output | ML / Platform Engineer
Audit index | /audit | Output | Auditor
Audit chain for a document | /audit/[document_id] | Output | Auditor
Audit checkpoints | /audit/checkpoints | Output | Auditor
Knowledge graph | /graph | Output | Security Admin, Analyst
Document summary | /documents/[id]/summary | Output | Data Owner, Admin
Summary landing | /summary | Output | Data Owner, Admin
CISO overview | /ciso | Output | CISO
Engineer overview | /engineer | Output | ML / Platform Engineer
Login | /login | Input | All

Figure 3.7 — User-interface navigation map (paste into https://mermaid.live)

BEGIN MERMAID
flowchart TB
    LOGIN["/login"] --> SHELL["AppShell (role-filtered nav)"]
    SHELL --> CLASSIFY["/ (classify + upload)"]
    SHELL --> DASH["/dashboard (risk)"]
    SHELL --> OVERRIDE["/override"]
    SHELL --> RULES["/rules"]
    SHELL --> ASK["/ask"]
    SHELL --> AGENTS["/agents"]
    SHELL --> GRAPH["/graph"]
    SHELL --> MIG["/migration"]
    SHELL --> CISO["/ciso"]
    SHELL --> ENG["/engineer"]
    SHELL --> AUDIT["/audit"]
    AUDIT --> ACHAIN["/audit/[document_id]"]
    AUDIT --> ACHECK["/audit/checkpoints"]
    CLASSIFY --> SUMM["/documents/[id]/summary"]
    DASH --> SUMM
    SHELL --> SUMLAND["/summary"]
END MERMAID

Reusable components keep the screens consistent: AppShell (layout and nav), MetricCard, RiskGauge, DataTable, Badge, StatusDot, HashDisplay (for truncated hashes with copy), D3AuditChain (a D3 visualisation of the Merkle chain), NotPermitted (the server-authorised empty state), and shared loading/empty/error states. Two behaviours are enforced on input screens to match acceptance criteria: the manual-override submit button is disabled until the operator confirms the action will be permanently logged and the justification reaches twenty characters, and the rule-authoring screen requires a unique name and at least one condition and offers a "test rule" action that evaluates against recent decisions without applying the rule.

Access to every action is decided server-side against the caller's role, independent of which screens the front end shows. Table 3.22 is the role-based access-control matrix that the backend enforces.

Table 3.22 — Role-based access control matrix

Capability | data_owner | security_analyst | security_admin | compliance_officer | auditor | ciso | engineer
---------- | ---------- | ---------------- | -------------- | ------------------ | ------- | ---- | --------
Upload / classify a document | Yes | Yes | Yes | No | No | No | Yes
Read a document summary | Own | Yes | Yes | Yes | Yes | Yes | Yes
Override a classification | No | Yes | No | No | No | No | No
Author / test a policy rule | No | No | No | Yes | No | No | No
Request erasure (shred) | Own | No | No | Yes | No | No | No
View the risk dashboard | No | Yes | Yes | Yes | No | Yes | Yes
View agent scores / rationale | No | Yes | Yes | No | No | Yes | Yes
Trigger audit verification | No | No | Yes | Yes | Yes | Yes | No
Issue / verify a checkpoint | No | No | No | No | Yes | No | No
Run migration ranking | No | No | Yes | No | No | Yes | Yes
Ask a grounded question | No | Yes | Yes | Yes | Yes | Yes | Yes

"Own" means the role may act only on documents it owns. The matrix is enforced in the API dependency layer; the front-end navigation merely mirrors it for usability.

CHAPTER 4 — IMPLEMENTATION

4.1 Development Environment

The system is developed and run as a containerised stack so that the exact runtime matches across machines. The application runs on Python 3.13 inside its Docker image, while the developer host runs Python 3.10; the split matters because the post-quantum library liboqs is built into the image and is not present on the host, so real post-quantum code paths run in the container and are gated behind an availability check on the host. The front end runs on Node with Next.js. Figure 4.1 shows the deployment topology of the local stack.

Figure 4.1 — Deployment topology (paste into https://mermaid.live)

BEGIN MERMAID
flowchart TB
    subgraph Host["Developer workstation (Docker Compose)"]
        FE["Frontend\nNext.js (dev server)"]
        subgraph BE["Backend container (Python 3.13)"]
            APP["FastAPI app (HTTPS 8443)"]
            OQS["liboqs 0.16.0 at /opt/liboqs"]
            RELAY["Outbox relay process"]
        end
        PG[("PostgreSQL 17 + pgvector\n15432 to 5432")]
        RD[("Redis 7 (TLS, 6379)")]
        NE[("Neo4j 5 (Bolt TLS, 7687 / 7474)")]
    end
    FE -->|HTTPS| APP
    APP -->|TLS| PG
    APP -->|TLS| RD
    APP -->|Bolt TLS| NE
    RELAY -->|drains outbox| RD
    APP --- OQS
END MERMAID

The database is published to the host on port 15432 (mapped to the container's 5432) so host-run tooling connects to the same instance. TLS is enforced in transit for every service, including local ones. The continuous-integration Postgres image is the pgvector build, because a plain Postgres image cannot create the vector extension and every migration would fail.

Table 4.1 — Development environment components

Component | Value
--------- | -----
Application runtime | Python 3.13 (Docker image)
Host tooling runtime | Python 3.10
Front-end runtime | Node with Next.js dev server
Orchestration | Docker Compose (single-host stack)
Database | PostgreSQL 17 with pgvector, published on host port 15432
Cache / event stream | Redis 7 over TLS
Graph database | Neo4j 5 over Bolt TLS
Post-quantum library | liboqs 0.16.0 built into the image at /opt/liboqs
API transport | HTTPS on port 8443
Version control / CI | Git with a continuous-integration coverage gate (floor 70 percent) and branch protection

4.2 Technologies and Tools

The choices below were made against the standing bar of production-grade and patent-credible, using standardised primitives rather than novel cryptography.

Table 4.2 — Technologies and tools used

Area | Technology | Why
---- | ---------- | ---
API framework | FastAPI + Pydantic | Typed request/response validation enforced server-side
Persistence | PostgreSQL + SQLAlchemy + Alembic | Strong typing, native enums, versioned migrations
Vector search | pgvector | Keeps embeddings in the same store as domain data
Event backbone | Redis Streams + transactional outbox | At-least-once delivery without losing events on broker downtime
Graph | Neo4j | Multi-hop attack-path queries in Cypher
Agents | LangGraph | Parallel agent orchestration with per-agent fail-safe
Language model | anthropic client (key-gated) | Real agent reasoning; deterministic scorers as offline fallback
Classical crypto | cryptography | AES-256-GCM baseline
Post-quantum crypto | liboqs-python | ML-KEM-1024 and ML-DSA-87
Hybrid KEM | X25519MLKEM768 | The TLS 1.3 named group already deployed by major browsers and CDNs
Policy | Open Policy Agent, Rego to WebAssembly | Deterministic, first-match, in-process evaluation
Optimisation | Qiskit (QAOA) | Migration ranking, compared against classical baselines
Embeddings | fastembed (BAAI bge-large-en-v1.5) | Real transformer embeddings for retrieval
Classifier | scikit-learn | Trained, calibrated sensitivity model with keyword escalation
Front end | Next.js, React, TypeScript, Tailwind | Role-filtered operator console
Testing | pytest, pytest-cov, vitest | Enforced coverage floor, unit and integration suites
Quality gates | black, flake8 | Formatting and lint enforced before merge

4.3 System Modules

Each module is implemented as a single backend subpackage. Their runtime behaviour is described below.

Sensitivity classifier (FR-1). A trained scikit-learn model (a hashing-vectoriser support-vector classifier, calibrated for probability output) assigns one of three machine tiers, and a policy layer distinguishes the fourth label. When the model's confidence falls below the threshold of 0.60, the fail-safe defaults the label upward to the more sensitive class and marks the row as defaulted; a set of keyword detectors act only to escalate, never to reduce, a label. A malformed model artifact fails loud rather than silently degrading. Every classification records the model version and can be superseded by a later classification, never overwritten.

Contextual risk engine (FR-2). Risk is computed from a closed context snapshot (actor, device, whether the device is new, access time, and whether the access is after hours). The after-hours flag is derived server-side from the access time and the organisation timezone when the caller omits it. Risk recomputes on a schedule and immediately on trigger events such as a new device or after-hours access, and every computation is appended with the signals that produced it.

Five scoring agents (FR-3). Security, compliance, contextual, quantum-readiness and sustainability agents run in parallel in a LangGraph graph. Each returns a numeric score and a human-readable rationale. A per-agent timeout is a recorded, visible fail-safe: a slow or failed agent does not block or silently corrupt the assessment. A real language-model backend activates when its key is configured; otherwise deterministic scorers serve as the documented offline fallback.

Trust engine (FR-4). The five agent outputs are combined by an explicit weighted arithmetic mean (security 0.250, compliance 0.250, contextual 0.200, quantum 0.175, sustainability 0.125), versioned as trust-weighted-mean-1.0.0. The engine refuses to compute from anything other than exactly the five expected agent types, and ambiguity resolves toward less trust.

Policy gate (FR-5). Compliance-authored rules are evaluated as a first-match, priority-ordered list. A rule's condition is a bounded tree (all/any/not combinators; eq/neq/gt/gte/lt/lte/in leaf operators over sensitivity label, risk value, trust score and AI recommendation) compiled to WebAssembly and evaluated in-process. A matching rule's action overrides the AI recommendation and records the rule id; when no rule matches, the AI recommendation stands and the rule id is null, which is a first-class, correctly modelled outcome, not a workaround.

Crypto selector and encryption (FR-6). The selector maps the trust score to a profile using calibrated bands (version trust-crypto-policy-bands-1.0.0): trust at or below 0.50 selects full post-quantum, at or below 0.85 selects hybrid, and above 0.85 selects the AES-256 baseline. Boundaries resolve toward more protection. Selection is fail-closed: a non-finite or out-of-range trust value raises rather than silently choosing a weaker profile, and hybrid or post-quantum without liboqs never falls back to AES.

Audit log and checkpoints (FR-7). Every decision writes exactly one chained row: a canonical payload, its SHA-256 hash, the previous row's hash, and the Merkle root and frontier as of that row. Chains are per document. A checkpoint issues a post-quantum Signed Tree Head (ML-DSA-87) over the tree size, Merkle root, timestamp and document id, which an auditor verifies by recomputing the root from stored payloads and checking the signature against an out-of-band-pinned public key.

Supporting modules. Crypto-shredding (FR-8) destroys a document's wrapped key irreversibly while preserving the audit trail. The migration scheduler (FR-9) ranks documents for post-quantum upgrade with a QAOA formulation and compares it against greedy and simulated-annealing baselines on an identical constraint set. The knowledge graph (FR-10) answers multi-hop attack-path queries over Neo4j. The agentic retrieval module (FR-11) runs a four-node graph (planner, retriever, reasoner, verifier) over the pgvector store and refuses to answer when the evidence does not ground the answer.

The Trust Engine combines the five agent scores with an explicit, versioned weighted arithmetic mean. The weights are principled policy defaults: security and compliance co-lead because they carry the highest business consequence, contextual risk follows, and quantum-readiness and sustainability contribute but do not dominate. The method and its version are recorded on every trust score so any past decision can be recomputed. Table 4.3 gives the weights.

Table 4.3 — Trust Score consensus weights (version trust-weighted-mean-1.0.0)

Agent | Weight | Rationale
----- | ------ | ---------
Security | 0.250 | Highest-consequence signal; co-lead
Compliance | 0.250 | Regulatory exposure; co-lead
Contextual risk | 0.200 | Actor, device and time context
Quantum-readiness | 0.175 | Harvest-now-decrypt-later exposure
Sustainability | 0.125 | Cost/energy of over-protection
Total | 1.000 | Weighted arithmetic mean

The crypto selector maps the resulting trust score to one of three protection profiles using the calibrated bands in Table 4.4. Lower trust demands stronger protection, and every boundary resolves toward the stronger profile. Selection is fail-closed.

Table 4.4 — Trust-to-crypto selector bands (version trust-crypto-policy-bands-1.0.0)

Trust score range | Profile selected | Cryptography
----------------- | ---------------- | ------------
0.00 to 0.50 | post_quantum | ML-KEM-1024 + ML-DSA-87
0.51 to 0.85 | hybrid | X25519MLKEM768
0.86 to 1.00 | aes256 | AES-256-GCM
Non-finite / out of [0,1] | (none) | Raises; never downgrades

The two strong profiles use NIST-standardised post-quantum primitives. Tables 4.5 and 4.6 record their standardised parameter sets and the sizes verified in the liboqs-equipped image, so the report's numbers match the running system rather than a specification quote alone.

Table 4.5 — ML-KEM-1024 key-encapsulation parameters (FIPS 203)

Property | Value
-------- | -----
Standard | FIPS 203 (ML-KEM), formerly CRYSTALS-Kyber
Parameter set | ML-KEM-1024 (Category 5)
Public (encapsulation) key | 1568 bytes
Secret (decapsulation) key | 3168 bytes
Ciphertext | 1568 bytes
Shared secret | 32 bytes
Library | liboqs-python 0.16.0

Table 4.6 — ML-DSA-87 digital-signature parameters (FIPS 204)

Property | Value
-------- | -----
Standard | FIPS 204 (ML-DSA), formerly CRYSTALS-Dilithium
Parameter set | ML-DSA-87 (Category 5)
Public key | 2592 bytes (verified)
Secret key | 4896 bytes (verified)
Signature | 4627 bytes (verified)
Use in system | Signed Tree Head over audit checkpoints
Library | liboqs-python 0.16.0

Every module capability is reached through a versioned REST API under /api/v1, with server-side identity and role checks on every route. Table 4.7 catalogues the endpoint groups.

Table 4.7 — REST API endpoint catalogue (prefix /api/v1)

Router | Representative endpoints | Purpose
------ | ----------------------- | -------
auth | POST /auth/login, GET /auth/me | JWT issue and identity
classify | POST /classify, GET /classify/{doc_id} | Sensitivity classification (FR-1)
documents | POST /documents, GET /documents/{id} | Upload, extract, metadata
risk | GET /risk/{doc_id}, POST /risk/recompute | Contextual risk (FR-2)
agents | POST /agents/assess | Five-agent parallel scoring (FR-3)
trust | GET /trust/{doc_id} | Consensus trust score (FR-4)
policy | GET/POST /policy/rules, POST /policy/rules/test | Rule authoring and dry-run (FR-5, FR-13)
crypto | GET /crypto/{doc_id}, POST /crypto/reselect | Profile selection (FR-6)
erasure | POST /erasure/{doc_id} | Crypto-shredding (FR-8)
migration | GET /migration/ranking | Upgrade prioritisation (FR-9)
graph | POST /graph/attack-paths | Multi-hop paths (FR-10)
rag | POST /rag/query | Grounded Q&A (FR-11)
override | POST /override/{doc_id} | Manual analyst override (FR-12)
audit | GET /audit/{doc_id}, POST /audit/verify | Chain view and verification (FR-15)
audit (checkpoint) | POST /audit/checkpoint, GET /audit/signing-key | PQ-signed anchoring (FR-7)
dashboard | GET /dashboard/stream (SSE) | Aggregate risk view (FR-14)
report | GET /report/{doc_id}?format=pdf,csv | Document summary export (FR-16)

4.4 Database Implementation

The schema is created and evolved entirely through Alembic migrations; there is no hand-applied SQL. Append-only behaviour is implemented by a single plpgsql function and per-table triggers, so the guarantee lives in the database rather than in application code. Table 4.8 lists the migrations that build the schema.

Table 4.8 — Key database migrations

Migration | Adds
--------- | ----
Core schema | The twelve domain tables, enums, indexes and append-only triggers
rag_chunks (e1a9c3f70b22, f2c7a9d15e30) | pgvector table, widened to vector(1024) with an HNSW cosine index
event_outbox (a3d8b1e4c907) | Transactional outbox table with status, retry and backoff columns
audit_checkpoints (b5e1c9f0a2d4) | audit_signing_keys and audit_checkpoints evidence tables

The append-only triggers follow a fixed naming scheme, trg_{table}_no_{operation}, and all reference the one shared function; a new append-only table adds only CREATE TRIGGER statements. UPDATE and DELETE guards are per-row; TRUNCATE guards are per-statement, because TRUNCATE does not fire row-level triggers. The test suite asserts the live trigger set against the source-of-truth tuples in the model package, so a missing trigger fails a test rather than passing silently.

4.5 User Interface Implementation

The front end is a single Next.js application. A RoleContext provides the current operator role to the AppShell, which filters the navigation to the screens that role can use. Every data fetch goes through a typed API client with a shared type module, so the front end and backend share one contract. The live risk dashboard consumes a server-sent-events stream, so the aggregate view updates without polling. The audit chain screen renders the Merkle chain with a D3 visualisation and lets an auditor trigger a full-chain verification whose result is computed server-side, not asserted by the front end. Input screens enforce their acceptance criteria in the UI for immediate feedback, but the same rules are re-validated server-side, because front-end validation is never treated as access control or as the authority on a rule.

4.6 Source Code and Snippets

The snippets below are representative of the core decision logic. They are shortened for the report; the full sources are in Appendix A.

Crypto profile selection (fail-closed bands), backend/app/crypto/selector.py:

    SELECTOR_VERSION = "trust-crypto-policy-bands-1.0.0"
    POST_QUANTUM_MAX = 0.50
    HYBRID_MAX = 0.85

    def select_profile(trust_score: float) -> CryptoProfileType:
        if not math.isfinite(trust_score) or not (0.0 <= trust_score <= 1.0):
            raise ValueError("trust_score must be finite and within [0, 1]")
        # Boundaries resolve toward MORE protection.
        if trust_score <= POST_QUANTUM_MAX:
            return CryptoProfileType.post_quantum
        if trust_score <= HYBRID_MAX:
            return CryptoProfileType.hybrid
        return CryptoProfileType.aes256

Trust consensus (explicit, versioned weights), backend/app/trust_engine/consensus.py:

    CONSENSUS_VERSION = "trust-weighted-mean-1.0.0"
    WEIGHTS = {
        "security": 0.250, "compliance": 0.250, "contextual": 0.200,
        "quantum": 0.175, "sustainability": 0.125,
    }

    def compute_consensus(outputs: dict[str, float]) -> float:
        if set(outputs) != set(WEIGHTS):
            raise ValueError("exactly the five agent outputs are required")
        return sum(WEIGHTS[a] * outputs[a] for a in WEIGHTS)

Classifier fail-safe (ambiguity escalates upward):

    def finalize_label(base_label, confidence, threshold=0.60):
        if confidence < threshold:
            # Never default toward the less sensitive label.
            return escalate(base_label), True   # (label, is_defaulted)
        return base_label, False

Policy gate outcome (no match is first-class):

    def evaluate(rules, facts):
        for rule in sorted(active(rules), key=lambda r: r.priority):
            if matches(rule.condition_expr, facts):
                return Decision(final=rule.action, rule_id=rule.id, overridden=rule.action != facts.ai_recommendation)
        # No rule fired: the AI recommendation stands.
        return Decision(final=facts.ai_recommendation, rule_id=None, overridden=False)

4.7 Screenshots

Screenshots are captured from the running application. Because they are live captures rather than diagrams, they are not reproducible from source in this document; each placeholder below names the screen to capture and what it must show. Insert the captured image at the corresponding placeholder.

Table 4.9 — Screenshot placeholders

Placeholder | Screen | Must show
----------- | ------ | ---------
Screenshot 4.1 | Classify / upload (/) | A document uploaded, its returned label, confidence and defaulted flag
Screenshot 4.2 | Risk dashboard (/dashboard) | Aggregate risk and protection status updating over the live stream
Screenshot 4.3 | Agents view (/agents) | The five agent scores and rationales for one assessment
Screenshot 4.4 | Manual override (/override) | The disabled submit button before the justification and confirmation are complete
Screenshot 4.5 | Policy rule authoring (/rules) | A condition tree being built and the test-rule result against recent decisions
Screenshot 4.6 | Audit chain (/audit/[document_id]) | The D3 Merkle chain and a full-chain verification result
Screenshot 4.7 | Audit checkpoints (/audit/checkpoints) | A signed checkpoint with its tree size, root and verification state
Screenshot 4.8 | Migration planning (/migration) | The QAOA ranking beside the baseline ranking on the same constraints
Screenshot 4.9 | Knowledge graph (/graph) | A multi-hop attack path between an actor and an asset
Screenshot 4.10 | Document summary (/documents/[id]/summary) | The exportable classification, protection and risk breakdown

CHAPTER 5 — TESTING

5.1 Testing Strategy

Testing is treated as part of each requirement, not a follow-up activity. A pull request that touches a module without a corresponding test update is incomplete, and a seventy-percent coverage floor is enforced in continuous integration rather than advised. The strategy is layered: unit tests exercise individual functions (the consensus weights, the crypto bands, the classifier fail-safe); functional tests assert each functional requirement's acceptance criteria; integration tests run stages together against a real database; and system tests run the whole pipeline end to end. Two areas carry extra, mandated coverage because of their consequence: the policy gate requires one test per rule type and per condition operator, and the audit log requires explicit tampered-entry and odd-leaf cases plus checkpoint tamper-root, tamper-signature and wrong-key rejection cases. Real post-quantum tests are gated behind a liboqs-availability check and are skipped on the host that lacks the library; they run in the post-quantum-equipped container.

The full backend suite comprises 47 test files, of which 46 are executed in the standard run (one synthetic-corpus module is held out pending an optional gated-dataset dependency), exercising 695 test functions that expand through parameterization to 1,059 test cases. The most recent complete run recorded 1,040 passed, 19 skipped and 0 failed. Statement-and-branch coverage of the served backend is 85.47 percent against the 70 percent floor, measured with offline corpus-generation scripts excluded as non-runtime tooling; the same run measures 78.58 percent when those untracked offline scripts are counted in the denominator. The 19 skips are the liboqs-gated real ML-DSA-87 tests, which execute in the post-quantum-equipped container.

Table 5.1 — Test suite composition

Metric | Value
------ | -----
Test files | 47 (46 executed; 1 held out)
Test functions | 695
Test cases (after parameterization) | 1,059
Passed | 1,040
Skipped (liboqs-gated post-quantum) | 19
Failed | 0
Statement-and-branch coverage (served runtime) | 85.47 percent
Statement-and-branch coverage (full working tree) | 78.58 percent
Coverage floor (enforced) | 70 percent

Figure 5.1 — Test outcome distribution (paste into https://mermaid.live)

BEGIN MERMAID
pie showData
    title Backend test outcomes (latest full run)
    "Passed" : 1040
    "Skipped (PQ, liboqs-gated)" : 19
    "Failed" : 0
END MERMAID

5.2 Unit Testing

Unit tests isolate the decision logic that must never regress. The crypto selector is tested at and around each band boundary to confirm that boundaries resolve toward more protection and that a non-finite or out-of-range trust value raises rather than downgrading. The trust consensus is tested to confirm the exact weighted mean and that a partial or extra set of agent outputs is rejected. The classifier fail-safe is tested to confirm that a confidence below threshold escalates the label and sets the defaulted flag, directly covering the documented risk that this behaviour could be silently weakened in a refactor. The Merkle functions are property-tested to confirm the incremental frontier root and a full recomputation agree across a range of chain lengths.

5.3 Functional Testing

Functional tests assert the acceptance criteria of each functional requirement. Representative cases: a low-confidence classification returns the more sensitive label with the defaulted flag set (FR-1); a manual override is rejected below twenty justification characters and without the logging confirmation (FR-12); a rule with a matching condition produces its action and records the rule id, while no matching rule leaves the AI recommendation standing with a null rule id (FR-5); a protection selection references the exact trust score that drove it and re-evaluates on material change (FR-6); an erasure destroys the key while the audit entries referencing it remain (FR-8); and the migration ranker's output includes the constraint values used, not just the order (FR-9).

5.4 Integration Testing

Integration tests run stages together against a real PostgreSQL instance rather than mocks, so the append-only triggers, foreign keys and check constraints are exercised as they run in production. These tests confirm that an UPDATE against any append-only table is rejected at the database with the expected restrict-violation error; that a TRUNCATE against an audit-evidence table is rejected by the statement-level trigger; that a fork (two rows claiming the same predecessor hash) is rejected by the unique constraint; and that the transactional outbox delivers an event to Redis Streams and moves the row from pending to sent, or to the dead-letter state after exhausting retries. The suite is run against a throwaway database so that a live smoke run cannot pollute it.

5.5 System Testing

System testing runs the whole bound pipeline end to end: a document is registered and classified, risk is scored, the five agents run in parallel, the trust consensus is computed, the policy gate is evaluated, a protection profile is selected and the bytes are encrypted, and every step appends a chained audit entry. A checkpoint is then issued and independently verified. The end-to-end smoke script exercises this path against the running Docker stack. The post-quantum path is validated in the liboqs-equipped container, where a valid checkpoint verifies and tamper-root, tamper-signature and wrong-key attempts are all rejected, and the ML-DSA-87 key and signature sizes are confirmed at 2592, 4896 and 4627 bytes.

5.6 Test Cases and Results

Table 5.2 lists representative test cases and their results, drawn from the passing suite.

Table 5.2 — Representative test cases and results

ID | Requirement | Scenario | Expected | Result
-- | ----------- | -------- | -------- | ------
TC-01 | FR-1 | Confidence below 0.60 | Label escalates, is_defaulted true | Pass
TC-02 | FR-1 | Malformed model artifact | Fails loud, no silent downgrade | Pass
TC-03 | FR-3 | One agent times out | Failure recorded, assessment completes | Pass
TC-04 | FR-4 | Only four agent outputs supplied | Rejected (422), no short mean | Pass
TC-05 | FR-4 | Five valid outputs | Exact weighted mean, versioned | Pass
TC-06 | FR-5 | Matching deny rule vs allow AI | final_decision deny, rule_id set, overridden true | Pass
TC-07 | FR-5 | No matching rule | AI recommendation stands, rule_id null | Pass
TC-08 | FR-6 | Trust 0.50 boundary | post_quantum selected (toward more protection) | Pass
TC-09 | FR-6 | Trust non-finite | Raises, no weaker profile | Pass
TC-10 | FR-6 | Hybrid requested without liboqs | Fails closed, no AES fallback | Pass
TC-11 | FR-7 | UPDATE an audit_log row | Rejected at database (restrict_violation) | Pass
TC-12 | FR-7 | Tampered payload | Verification detects alteration | Pass
TC-13 | FR-7 | TRUNCATE audit_checkpoints | Rejected by statement-level trigger | Pass
TC-14 | FR-7 | Wrong-key checkpoint verify | Rejected | Pass
TC-15 | FR-8 | Erase then read | Key destroyed, audit entries remain | Pass
TC-16 | FR-9 | Rank under budget | Includes constraint snapshot, beats baseline on the set | Pass
TC-17 | FR-11 | Ungrounded question | Verifier refuses to answer | Pass
TC-18 | FR-12 | 19-character justification | Rejected server-side | Pass
TC-19 | FR-13 | Rule without a condition | Rejected; save blocked | Pass
TC-20 | FR-10 | Multi-hop query | Returns the attack path across nodes | Pass

CHAPTER 6 — CONCLUSION

6.1 Conclusion

Q-AEGIS Shield demonstrates that classification, continuous risk, multi-agent assessment, trust consensus, deterministic policy override, crypto-agile protection and tamper-evident proof can be bound into a single automated loop rather than assembled from disconnected tools. The novelty is the binding itself: each stage consumes the previous stage's output, every stage writes an immutable record, and the whole chain is independently verifiable by a party who does not trust the operator. The system meets its primary goals. Sensitivity is classified automatically with a conservative fail-safe. Risk is reassessed continuously from signals beyond the document. Protection strength is selected automatically from a live trust score. A deterministic rule layer can override any artificial-intelligence recommendation, and the common case where no rule fires is modelled as a first-class outcome. Every decision is anchored in an append-only, Merkle-chained, post-quantum-signed audit log. Post-quantum protection is available today, and migration is prioritised rather than deferred.

6.2 Project Outcomes

Table 6.1 — Outcomes against the stated goals

Goal | Outcome
---- | -------
Automatic classification without manual pre-labelling | A trained, calibrated model with a fail-safe that defaults toward more sensitive on low confidence
Continuous risk beyond the document | Contextual scoring on schedule and on trigger events, with recorded signals
Automatic, risk-matched crypto selection | Calibrated bands selecting AES-256, hybrid or full post-quantum, fail-closed
Permanent, independently verifiable record | Per-document Merkle chains with post-quantum Signed Tree Head checkpoints
Deterministic override of any AI recommendation | First-match OPA/Rego gate above the model, with the no-match case first-class
Real, prioritised post-quantum migration | QAOA ranker compared against classical baselines on an identical constraint set

The engineering evidence is a green suite of 1,040 passing tests at 85.47 percent coverage of the served runtime (78.58 percent across the full working tree), database-enforced append-only guarantees, fail-closed cryptography, and a post-quantum checkpoint path proven end to end with confirmed ML-DSA-87 parameter sizes.

6.3 Limitations

The system is a working prototype, and its boundaries are stated honestly rather than hidden. Key management this phase uses environment-configured secrets, not a hardware security module. The post-quantum library is not independently audited, and no claim of a certified or audited-grade guarantee is made on its behalf. The audit chain's previous-hash links are not themselves covered by the payload hash, so the external anchoring of the Merkle root, not the chain alone, is what makes tampering detectable; the chain is not described as sufficient on its own. A database superuser can drop a trigger, so the append-only guarantee stops every application path and accidental migration but is not a defence against a superuser. Live ingestion from third-party systems, a plugin marketplace, a quantitative incident-cost simulator and public production hosting are explicitly out of scope this phase.

6.4 Future Enhancements

Natural extensions follow from the boundaries above. Key storage can move to a hardware security module. Live connectors to identity providers, source-control and cloud storage can feed the risk engine and knowledge graph, an integration the architecture is already shaped to accept. Periodic automatic checkpoint anchoring can layer onto the existing scheduler, and external anchoring of the Signed Tree Head to a public transparency log would further strengthen independent verifiability. The classifier can be retrained on a larger labelled corpus as one becomes available, and the agent language-model backend can be enabled in place of the deterministic offline fallback. Finally, the policy authoring interface can grow richer nested any/not editing to match the full expressiveness of the underlying condition tree.

REFERENCES / BIBLIOGRAPHY

Books and Standards

[1] National Institute of Standards and Technology, "FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard," U.S. Department of Commerce, 2024.

[2] National Institute of Standards and Technology, "FIPS 204: Module-Lattice-Based Digital Signature Standard," U.S. Department of Commerce, 2024.

[3] National Institute of Standards and Technology, "FIPS 205: Stateless Hash-Based Digital Signature Standard," U.S. Department of Commerce, 2024.

[4] B. Laurie, A. Langley, and E. Kasper, "RFC 6962: Certificate Transparency," Internet Engineering Task Force, 2013.

[5] R. C. Merkle, "A Digitized Signature and Public Key Cryptosystem in a Conventional Encryption Function," Technical Report, Stanford University, 1979.

[6] E. Barker, "NIST SP 800-57 Part 1 Rev. 5: Recommendation for Key Management," National Institute of Standards and Technology, 2020.

[7] E. Farhi, J. Goldstone, and S. Gutmann, "A Quantum Approximate Optimization Algorithm," arXiv:1411.4028, 2014.

[8] P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in Advances in Neural Information Processing Systems 33, 2020, pp. 9459-9474.

[9] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in Proc. EMNLP-IJCNLP, 2019, pp. 3982-3992.

[10] F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," Journal of Machine Learning Research, vol. 12, pp. 2825-2830, 2011.

[11] European Parliament and Council, "Regulation (EU) 2016/679 (General Data Protection Regulation), Article 17: Right to erasure," Official Journal of the European Union, 2016.

[12] Government of India, "The Digital Personal Data Protection Act, 2023," Ministry of Law and Justice, 2023.

Web and Online Resources

[13] Internet Engineering Task Force, "X25519MLKEM768 hybrid key exchange for TLS 1.3," 2024. [Online]. Available: https://datatracker.ietf.org/

[14] Open Policy Agent Project, "Open Policy Agent and the Rego Policy Language Documentation." [Online]. Available: https://www.openpolicyagent.org/docs/

[15] Open Quantum Safe Project, "liboqs and liboqs-python." [Online]. Available: https://openquantumsafe.org/

[16] LangChain Inc., "LangGraph Documentation." [Online]. Available: https://langchain-ai.github.io/langgraph/

[17] Sebastian Ramirez, "FastAPI Documentation." [Online]. Available: https://fastapi.tiangolo.com/

[18] Vercel Inc., "Next.js Documentation." [Online]. Available: https://nextjs.org/docs

[19] pgvector Contributors, "pgvector: Open-source vector similarity search for Postgres." [Online]. Available: https://github.com/pgvector/pgvector

[20] Neo4j Inc., "Neo4j Graph Database Documentation." [Online]. Available: https://neo4j.com/docs/

[21] Redis Ltd., "Redis Streams Documentation." [Online]. Available: https://redis.io/docs/latest/develop/data-types/streams/

[22] IBM, "Qiskit Documentation." [Online]. Available: https://www.ibm.com/quantum/qiskit

[23] Python Cryptographic Authority, "cryptography Library Documentation." [Online]. Available: https://cryptography.io/

[24] Qdrant / fastembed Contributors, "fastembed: Fast, lightweight embedding generation." [Online]. Available: https://github.com/qdrant/fastembed

APPENDIX A — SOURCE CODE

The full source is organised so that each backend subpackage maps to exactly one module. The layout is:

    backend/app/
      classifier/     sensitivity classification (FR-1)
      risk_engine/     contextual risk scoring + scheduler (FR-2)
      agents/          five-agent LangGraph orchestration (FR-3)
      trust_engine/    versioned consensus (FR-4)
      policy/          OPA/Rego first-match gate (FR-5)
      crypto/          selector + encrypt, oqs support (FR-6)
      audit/           merkle, service, checkpoint (FR-7)
      documents/       upload + extraction
      scheduler/       QAOA + baselines, migration ranking (FR-9)
      graph/           Neo4j multi-hop paths (FR-10)
      rag/             planner-retriever-reasoner-verifier (FR-11)
      event_bus/       outbox, relay, client (durable events)
      api/             routers, deps, auth wiring (~36 endpoints)
      auth/            JWT issue/verify, role resolution
      db/models/       SQLAlchemy models + append-only tuples
    backend/alembic/versions/   migrations
    backend/tests/              47 test files, 695 test functions
    frontend/src/               Next.js App Router, 16 routes, components, api client

Representative full function — audit payload canonicalisation and verification (backend/app/audit/merkle.py, shortened):

    import hashlib, json

    def canonicalize(payload: dict) -> bytes:
        # Stable key order and separators so the hash is reproducible by an auditor.
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def leaf_hash(payload: dict) -> str:
        return hashlib.sha256(b"\x00" + canonicalize(payload)).hexdigest()

    def verify_chain(rows: list[dict]) -> bool:
        prev = None
        for row in rows:                      # rows in link order, genesis first
            if leaf_hash(row["payload"]) != row["payload_hash"]:
                return False                  # payload does not match its stored hash
            if row["prev_hash"] != prev:
                return False                  # chain link broken (tamper or fork)
            prev = row["payload_hash"]
        return True

Representative full function — post-quantum Signed Tree Head verification (backend/app/audit/checkpoint.py, shortened):

    def verify_checkpoint(cp, public_key_hex) -> bool:
        import oqs                              # imported inside the function on purpose
        signing_input = canonicalize({
            "tree_size": cp.tree_size,
            "merkle_root": cp.merkle_root,
            "signed_at": cp.signed_at.isoformat(),
            "document_id": str(cp.document_id) if cp.document_id else None,
            "domain": "qaegis-audit-sth-v1",
        })
        with oqs.Signature("ML-DSA-87") as verifier:
            return verifier.verify(signing_input, bytes.fromhex(cp.signature),
                                   bytes.fromhex(public_key_hex))

APPENDIX B — DATABASE SCRIPTS

The schema is built and evolved only through Alembic migrations. The scripts below are representative of the append-only enforcement and a core table definition.

Append-only guard function (created once, referenced by every append-only trigger):

    CREATE OR REPLACE FUNCTION qaegis_reject_append_only_write()
    RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'append-only table: % not permitted on %',
            TG_OP, TG_TABLE_NAME
            USING ERRCODE = '23001';   -- restrict_violation
    END;
    $$ LANGUAGE plpgsql;

Trigger installation (naming scheme trg_{table}_no_{operation}; row-level for UPDATE/DELETE, statement-level for TRUNCATE):

    -- History table: block UPDATE only.
    CREATE TRIGGER trg_risk_scores_no_update
        BEFORE UPDATE ON risk_scores
        FOR EACH ROW EXECUTE FUNCTION qaegis_reject_append_only_write();

    -- Audit evidence table: block UPDATE, DELETE and TRUNCATE absolutely.
    CREATE TRIGGER trg_audit_log_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION qaegis_reject_append_only_write();
    CREATE TRIGGER trg_audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION qaegis_reject_append_only_write();
    CREATE TRIGGER trg_audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION qaegis_reject_append_only_write();

Representative core table (audit_log), showing the fork-prevention constraint:

    CREATE TABLE audit_log (
        id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id           uuid REFERENCES documents(id),
        actor_id              uuid REFERENCES users(id),
        event_type            varchar(60) NOT NULL,
        payload               jsonb       NOT NULL,
        payload_hash          char(64)    NOT NULL,
        prev_hash             char(64),
        merkle_root_at_time   char(64)    NOT NULL,
        frontier              jsonb       NOT NULL,
        created_at            timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT no_forked_chain UNIQUE NULLS NOT DISTINCT (document_id, prev_hash)
    );
    CREATE INDEX ix_audit_log_created_at ON audit_log (created_at);

pgvector retrieval table (vector width must match the configured embedding dimension):

    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE rag_chunks (
        id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id      uuid REFERENCES documents(id) ON DELETE CASCADE,
        source_type      varchar(80)  NOT NULL,
        source_id        varchar(120),
        content          text         NOT NULL,
        embedding        vector(1024) NOT NULL,
        embedding_model  varchar(80)  NOT NULL,
        metadata         jsonb        NOT NULL DEFAULT '{}',
        created_at       timestamptz  NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_rag_chunks_embedding ON rag_chunks
        USING hnsw (embedding vector_cosine_ops);

Migration and run commands (PowerShell):

    cd backend; .\venv\Scripts\Activate.ps1
    alembic upgrade head
    uvicorn app.main:app --reload
    # full local stack
    cd infra; docker compose --env-file ..\.env up -d

APPENDIX C — USER MANUAL

This manual describes how each operator role uses the system. All actions are authorised server-side against the signed-in role; a screen a role cannot use is hidden and its underlying request is also refused.

Getting started

1. Open the application and sign in at /login with an issued account. A session token is held for the browser session.
2. The navigation sidebar shows only the screens permitted for your role.

Data Owner

- Upload a document on the home screen (/). The system classifies it and returns a sensitivity label, a confidence score and whether the fail-safe defaulted the label upward.
- Open the document summary (/documents/[id]/summary) to see the classification, the selected protection profile and the risk breakdown, and export it as PDF or CSV.

Security Analyst

- Open Manual Override (/override) to correct a classification. Enter a justification of at least twenty characters and tick the confirmation that the action will be permanently logged. The submit button stays disabled until both are satisfied. The override is recorded permanently and does not delete the prior classification.

Compliance Officer

- Open Policy Rules (/rules) to author an override rule. Give it a unique name and at least one condition (combining sensitivity label, risk value, trust score or AI recommendation with the supported operators). Use "Test rule" to evaluate it against recent decisions without applying it, then activate it. Priorities are unique among active rules; a lower number is evaluated first.
- Handle an erasure request through the shredding action; the document's key is destroyed irreversibly while its audit trail is preserved.

Security Admin

- Open the Risk Dashboard (/dashboard) for a live, aggregate view of risk and protection status across all documents; it updates automatically.
- Open Migration Planning (/migration) to see the post-quantum upgrade ranking and the constraints that produced it.

Auditor

- Open the Audit index (/audit), then a document's chain (/audit/[document_id]) to see its full chained decision history. Trigger a full-chain verification; the result is computed server-side by recomputing hashes from stored payloads.
- Open Checkpoints (/audit/checkpoints) to verify a Signed Tree Head. Pin the signing public key out-of-band from /audit/signing-key so verification does not rely on trusting the operator.

CISO and Engineer

- The CISO overview (/ciso) presents portfolio posture and migration readiness. The Engineer overview (/engineer) and Agents view (/agents) expose the five agent scores and rationales and the module health needed to maintain the pipeline.

Asking a question

- Open Ask (/ask) and pose a natural-language question about a security event. The answer is grounded in and verified against actual records; if the evidence does not support an answer, the system refuses rather than generating an unverified one.

END OF REPORT





























