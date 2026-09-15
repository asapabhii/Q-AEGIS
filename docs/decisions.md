# Decisions

A running log of implementation decisions made where `SPEC.md` deliberately left a choice open, plus any other significant technical decision worth recording so the reasoning survives past whoever made the call. Newest at the top. Each entry: date, decision, who made it, why, what was rejected and why.

---

## Pending

_(none — pgvector decided with FR-11; Neo4j Bolt TLS closed on this branch;
Postgres/Redis/API TLS landed via #27)_

---

## Log

### 2026-09-15: after_hours derives from org timezone when omitted

Decided by: Abhinav, with Codex implementation support, closing a small Track C
behavioral hardening gap for `SPEC.md` 3.3 / PRD FR-2.

`after_hours` remains in the stored risk snapshot so historical rows are still a
closed five-field record. The API now derives it when callers omit the field,
using an IANA `org_timezone` value that defaults to `Asia/Kolkata`. Business
hours are Monday-Friday, 09:00 inclusive to 18:00 exclusive in that timezone.
Existing callers may still send `after_hours` explicitly for compatibility.

Rejected: reopening Redis Streams/Kafka or policy engine decisions for this
small hardening item. Rejected: deriving from a naive timestamp; `accessed_at`
must stay timezone-aware.

### 2026-09-15: Trust-to-action and trust-to-crypto policy bands calibrated

Decided by: Abhinav, with Codex implementation support, closing the Track A
threshold-placeholder gap for `SPEC.md` 3.5 / 3.7.

The first shipped thresholds were deliberately labelled placeholders. They are
now versioned as policy bands rather than incident-statistical calibration:
`trust-recommendation-policy-bands-1.0.0` and
`trust-crypto-policy-bands-1.0.0`. No historical incident dataset exists in this
repository, so this entry does **not** claim empirical precision. It records the
risk posture the deterministic layer will enforce until a measured calibration
pack supersedes it.

- **AI recommendation from consensus:** `0.000–0.250` → `deny`,
  `0.251–0.500` → `force_pqc`, `0.501–0.750` → `require_mfa`,
  `0.751–1.000` → `allow`.
- **Crypto profile selection:** `0.000–0.500` → `post_quantum`,
  `0.501–0.850` → `hybrid`, `0.851–1.000` → `aes256`.
- Boundaries are inclusive on the more protective side. For example `0.500`
  still selects full post-quantum crypto, and `0.750` still requires MFA.
- The crypto band is intentionally more conservative than the policy action
  band: a request may be allowed or MFA-gated while its bytes still receive
  hybrid protection, because harvest-now-decrypt-later exposure is about data
  lifetime, not only the current access decision.

Rejected: keeping the old placeholder labels after the cut-points became part
of the product contract. Rejected: claiming model-derived calibration without a
labelled outcomes dataset. Rejected: making AES-256 the default for any
non-finite or out-of-range value; invalid trust input still raises rather than
falling through to the weakest profile.

### 2026-09-14: Neo4j Bolt TLS for local compose

Decided by: Abhinav, closing the Pending item from AGENTS.md TLS-in-transit for the knowledge graph.

- Compose sets `NEO4J_server_bolt_tls__level=REQUIRED` and the bolt SSL policy under `/var/lib/neo4j/certificates/bolt`.
- Certs come from `scripts/generate-local-certs.*` → `infra/certs/` (gitignored). Entrypoint copies from `/certs-ro` and `chmod 400` the private key so Windows bind mounts do not break Neo4j's permission check.
- App URI is `bolt+s://127.0.0.1:7687` with `QAEGIS_NEO4J_SSL_CA_CERTS` pointing at the local CA. The Python driver rewrites `bolt+s` → `bolt` + `encrypted=True` + `TrustCustomCAs` because neo4j-python forbids `trusted_certificates` on `+s` URI schemes. Healthcheck uses `bolt+ssc://` so cypher-shell does not need a custom Java truststore.
- Neo4j Browser HTTP on `:7474` stays plaintext on loopback (Bolt is the application path). Postgres/Redis TLS remains on `feature/auth-upload-sse-tls-personas` / PR #27, not duplicated on the FR-10/11 branch.

Rejected: leaving Bolt plaintext with “loopback only” as enough. Rejected: requiring operators to import the CA into the JVM for the healthcheck.

### 2026-09-14: FR-10 Neo4j attack paths; FR-11 agentic RAG on pgvector

Decided by: Abhinav, implementing `SPEC.md` 3.11 / 3.12 (PRD FR-10, FR-11). FR-12–16 screens were already on `main`; this change adds Graph + Ask screens and keeps those APIs unchanged.

- **FR-10:** Neo4j via `QAEGIS_NEO4J_*`. Demo seed + Cypher multi-hop paths (`GET /graph/documents/{id}/paths`, `GET /graph/attack-paths`). Nodes: Employee, Document, Repository, Vendor, CloudAsset. Application-level `document_id` property, not a Postgres FK.
- **FR-11:** Four LangGraph nodes Planner → Retriever → Reasoner → Verifier. Vector store **pgvector** (closes `SPEC.md` 2.4 for this phase). Table `rag_chunks`. Embeddings are the labelled stub `stub-hash-v1` (deterministic hash vectors) so CI needs no remote embedder. Answers are refused when the Verifier cannot ground the draft in retrieved chunks. Compose Postgres image is `pgvector/pgvector:pg17`.
- **FR-12–16:** No API contract changes. Nav already covered Override / Rules / Dashboard / Audit / Summary (/migration is FR-9). Added `/graph` and `/ask`.

Rejected: Qdrant (no measured latency problem; one fewer service). Rejected: a single LLM prompt for RAG (SPEC requires four nodes). Rejected: returning unverified generated text (PRD FR-11).

### 2026-09-14: Local JWT auth, disk upload, SSE, self-signed TLS

Decided by: Abhinav, closing the P0 auth/upload/live-UI gaps called out after FR-12–15 / P0 merge.

- **Auth:** email/password → JWT (`Authorization: Bearer`). Seeded users take `QAEGIS_DEV_SEED_PASSWORD` from the environment (see `.env.example`); nothing hard-codes a shared password in application source. `X-Q-AEGIS-Actor-Role` stays as a **dev-only** bypass behind `AUTH_DEV_HEADER_BYPASS` (Settings default **false**; `.env.example` opts in for local).
- **Upload:** local disk under `DOCUMENT_STORAGE_DIR` (not object storage this phase). 50 MiB cap, enforced by chunked reads server-side and a matching client-side gate. All common document types accepted; paste classify remains.
- **Live dashboard:** SSE on `GET /api/v1/events/stream` (Redis Streams when configured, inventory poll otherwise). Stream fan-out validates via `parse_stream_fields`. Clients use `fetch` so Bearer headers work.
- **TLS:** self-signed CA via `scripts/generate-local-certs.*`; Postgres SSL, Redis TLS, API HTTPS `:8443` in compose. Neo4j Bolt TLS is completed on the FR-10/11 branch (see entry above / Neo4j Bolt TLS log).
- **Personas:** `/login`, `/ciso`, `/engineer` screens; agent deep-dive at `GET /documents/{id}/agents`.
Rejected: IdP/OIDC for local Phase 1 (heavier than needed). Rejected: S3/MinIO for upload this phase. Rejected: WebSockets (SSE is enough for inventory refresh). Rejected: dropping the role header entirely (tests and quick local demos still need a bypass).

### 2026-09-14: FR-8 shred overwrites wrapped_dek; FR-9 ranks with QAOA+baselines; FR-16 exports CSV/PDF

Decided by: Abhinav, implementing `SPEC.md` 3.9 / 3.10 / 3.13 (FR-8, FR-9, FR-16) in one PR after P0 encrypt.

- **FR-8:** `POST /api/v1/shred` with `{document_id, confirmed: true}`. Overwrites `document_ciphertexts.wrapped_dek` in place with a marker + random pad (same length, column stays NOT NULL). Ciphertext and `audit_log` stay. Idempotent re-shred is allowed and audited. Roles: data_owner, compliance_officer, security_admin. Document status moves to `archived`.
- **FR-9:** `POST /api/v1/migration-schedule/rank` with budget/window/seed. Collects candidates that have a non-PQ profile. Runs greedy, simulated annealing, and QAOA on the same set. Persists the QAOA order into `migration_schedule` with full `constraint_snapshot` (including baseline totals). Qiskit is preferred when importable; numpy statevector QAOA is the fallback so CI/Windows still rank. No claim that QAOA beats baselines — totals are returned for the required comparison.
- **FR-16:** `GET /api/v1/documents/{id}/summary?format=csv|pdf`. Roles: data_owner, security_admin. Minimal PDF writer (no reportlab) so the export path has no extra native dep. Export is audited.

Rejected: nullable `wrapped_dek` (would need a data-dictionary + migration change for no gain). Rejected: deleting ciphertext on shred (FR-8 keeps evidence). Rejected: shipping FR-9 without baseline totals in the same response.

### 2026-09-14: Event bus is Redis Streams; P0 pipeline runs agents then gate then encrypt

Decided by: Abhinav, closing `SPEC.md` 2.3 while implementing P0 (FR-2 schedule/triggers, FR-3 agents, FR-6 encrypt).

- **Bus:** Redis Streams (`qaegis:events`), not Kafka. One Redis is already in `infra/docker-compose.yml`. Streams give consumer groups and durability at this volume without a second broker. Move to Kafka only if partitioned multi-group scale appears as a measured need (`SPEC.md` 2.3).
- Event envelopes are validated on publish and consume. First event types: `document.uploaded`, `document.classified`, `risk.trigger` (new device / after-hours), `trust.updated`.
- Contextual risk stays callable via `POST /risk-scores`. The bus adds scheduled recomputes and immediate trigger events so FR-2 is not "once at upload" only. `after_hours` remains a fact on the snapshot, not derived from a hard-coded business-hours window.
- **FR-3:** five LangGraph agents produce the `agent_outputs` rows. `POST /trust-scores` still accepts caller-supplied outputs for direct tests; the assessment pipeline prefers agent-produced scores.
- **FR-5:** when `ai_recommendation` is omitted on the gate, it is derived from the persisted consensus via a versioned mapping (`allow` / `require_mfa` / `force_pqc` / `deny`). Callers may still supply it explicitly.
- **FR-6:** profile selection still writes `crypto_profiles`; encrypting document bytes is a separate step that uses the selected profile and stores ciphertext + wrapped DEK so FR-8 can destroy the key later without touching `audit_log`.

Rejected: Kafka at this team size. Rejected: inventing business hours for `after_hours`. Rejected: silently falling hybrid/PQ encrypt back to AES when liboqs is missing.

### 2026-09-10: Dashboard and audit viewer are separate screens; verify is its own call

Decided by: Abhinav, implementing `PRD.md` FR-14 and FR-15 screens together. The APIs were already on `main`; the screens share nav, role plumbing, and the same inventory/audit types.

- `/dashboard` reads `GET /documents` only. It sums how many rows already have a label. It does not invent a risk, trust, or profile for a stage that has not run. Null stages render as an em dash.
- `/audit` loads `GET /audit/entries?document_id=` and verifies with `GET /audit/verify?document_id=`. The list card has no validity flag. Verify can run without loading first. `document_id` is always sent; this is not the system-chain viewer. `end_index` is omitted so the server verifies through the tail.
- Dashboard rows link to `/audit?document_id=` and `/override?document_id=`.

Rejected: putting `is_valid` on the chain list (already decided on the API). Rejected: omitting `document_id` on verify from this screen. Rejected: averaging null scores on the dashboard.

### 2026-09-10: Policy rule screen authors a flat condition list; test writes nothing

Decided by: Abhinav, implementing `PRD.md` FR-13's screen.

`/rules` is a separate App Router page. Default role is `compliance_officer`.

- Save and Test share one body: `{ rule_name, condition_expr, action, priority }`. Extra keys, including `window`, are not sent.
- Save is disabled until the name is non-blank after trim (max 150), priority is an integer greater than 0, and every visible condition row is a valid v1 leaf. One leaf is sent as itself; two or more are `{ "all": [...] }`.
- Test calls `POST /policy-rules/test` and persists nothing. Save calls `POST /policy-rules`. Unique name and unique active priority are 409 from the server; there is no list endpoint to pre-check.
- Nested `any` / `not` trees are still valid on the API. This screen does not author them.

Rejected: a panel on classify (FR-13 says dedicated). Rejected: requiring a successful test before save (the PRD says test is available before live, not a gate). Rejected: inventing field layout from a CIA spec that is not in this repository — same tokens as the other screens.

### 2026-09-10: Manual override screen is dedicated; confirmation stays in the browser

Decided by: Abhinav, implementing `PRD.md` FR-12's screen.

`/override` is a separate App Router page, not a panel on classify. `?document_id=` is a convenience from the classify result.

- Load uses `GET /api/v1/documents/{id}` so the current effective label is the same snapshot the inventory and the gate use.
- Submit is disabled until the document is classified, the new label differs, justification is at least 20 characters after trim, and the analyst checks "I confirm this action will be permanently logged".
- The POST body is `{ document_id, new_label, justification }` only. `confirmed` is not sent.

Rejected: a section on the classify workbench (FR-12 says dedicated). Rejected: sending `confirmed` (forgeable; already decided on persist). Rejected: inventing field layout from a CIA spec that is not in this repository — same tokens as the classify workbench.

### 2026-09-10: Audit viewer lists one document's chain, does not judge it

Decided by: Abhinav, implementing `PRD.md` FR-15's read surface.

`GET /api/v1/audit/entries?document_id=` returns `{ document_id, count, entries }`. HTTP 200. `document_id` is required. Unknown document is 404. Existing document with no entries is an empty list.

- Order follows `prev_hash` links, genesis first. `created_at` is not the order: entries written in one transaction share `now()`.
- Each entry is `id`, zero-based `index`, `actor_id`, `event_type`, `payload`, `payload_hash`, `prev_hash`, `merkle_root_at_time`, `created_at`.
- `frontier` is omitted. It is write-path Merkle state. Verification recomputes from payloads.
- No `is_valid`. That is `GET /audit/verify`. Putting a verdict on the same response as the rows would ask the auditor to trust this system.
- Roles: same as verify (`auditor`, `security_admin`, `security_analyst`). Data owners are refused (FR-16 is a summary).
- The system chain (null `document_id`) is not this endpoint. FR-15 is one document. Verify still accepts an omitted id.
- Reads write nothing. A broken chain is 409.

Rejected: omitting `document_id` (this is not the system-chain viewer). Rejected: newest-first (the links are the authority). Rejected: a validity flag on the list. Rejected: exposing `frontier`. Rejected: pagination (FR-15 is the full chain).

### 2026-09-10: Document inventory reads latest rows, does not invent scores

Decided by: Abhinav, implementing `PRD.md` FR-14's read surface.

`GET /api/v1/documents` returns `{ count, documents }`. `GET /api/v1/documents/{document_id}` returns one row of the same shape. HTTP 200. Unknown id is 404.

- Each row is document identity plus the latest effective label, contextual risk, trust consensus, policy decision, and crypto profile.
- A stage that has not run is null. The API does not invent a label, score, or profile.
- The effective label is the latest override `new_label`, else the latest classification. A later classification does not retract an override. Same rule as the policy gate.
- Latest in each history table is timestamp desc, then `id`. Classification, risk, trust, policy, and crypto use transaction-scoped `now()`, so two rows written in one transaction share a timestamp and `id` is the tiebreak. Overrides do not: `overridden_at` is `clock_timestamp()`, so two overrides in one transaction have distinct times, and that clock order is what determines the effective label.
- No query params. No pagination. The list is the whole set, newest `uploaded_at` first.
- Roles: `security_admin` (FR-14), `security_analyst` (FR-12 pick a document), `auditor` (FR-15 pick a document). Data owners are refused: FR-16 is one document's summary, not the fleet.
- Reads write nothing. No audit entry for a GET.

Rejected: a caller-supplied filter or limit (FR-14 is the monitored set). Rejected: aggregating counts in the API (the screen can sum). Rejected: showing a data owner every document. Rejected: writing an audit row for a read (FR-7 is decisions).

### 2026-09-10: Policy rule dry-run reads historical audit snapshots

Decided by: Abhinav, implementing `PRD.md` FR-13's "test rule" action.

`POST /api/v1/policy-rules/test` body is the same shape as `POST /policy-rules`: `{ rule_name, condition_expr, action, priority }`. Extra keys forbidden, including a caller-supplied window.

- The candidate is not inserted. No `policy_decisions` row. No audit entry. HTTP 200.
- Live `policy_rules` are not consulted. The question is "would this rule have matched these past facts?", not a replay of first-match against the current set.
- Facts come from the last 20 `policy_decision_recorded` audit payloads, newest first. Re-reading current classification or trust would test against today.
- A payload missing the v1 fact keys, or with an unrecognized `sensitivity_label` or action, is skipped, not guessed. `skipped` is counted.
- `hypothetical_final_decision` is the candidate action on a match, else that snapshot's `ai_recommendation`.
- Role: `compliance_officer` only, same as authoring.

Rejected: a `limit` query param (window is part of the contract). Rejected: writing a "test" audit event (FR-13 says the action is not applied; an audit row would look like a decision). Rejected: requiring the rule to be saved first (the point is to test before it goes live).

### 2026-09-10: Manual override persist, and the gate reads the effective label

Decided by: Abhinav, implementing `PRD.md` FR-12 persist and binding 3.6 to it.

`POST /api/v1/manual-overrides` body is `{ "document_id", "new_label", "justification" }` only. Extra keys forbidden.

- `original_label` is the current effective sensitivity: latest override `new_label`, else latest `classification_metadata`. The client cannot supply it.
- No classification is 422. `new_label` equal to the effective label is 422. Unknown document is 404.
- Justification is stripped, then must be at least 20 characters. The database CHECK remains the backstop.
- Persist writes one `manual_overrides` row and `MANUAL_OVERRIDE` in the same transaction. A later override is a new row. `documents.current_status` is not changed.
- Roles: `security_analyst` and `security_admin`. Data owners see the outcome; they do not write this table.

FR-12's confirmation checkbox is a UI requirement. It is not an API field. A client-supplied `confirmed: true` is forgeable and would not prove the analyst confirmed.

The policy gate now uses that same effective label. A later classification does not retract an override. Clearing an override back to "whatever the AI says now" is a later endpoint, not a timestamp comparison. `POST /policy-decisions` records `override_id` (nullable) and `label_source` (`classification` | `manual_override`) on the response and the audit payload so an auditor does not have to infer provenance.

This supersedes the "manual overrides are not applied" sentence in "Policy v1 reads persisted facts from a trust_score_id" below.

Concurrent writes take a `documents` row lock (`SELECT … FOR UPDATE`) before reading the effective label and hold it through the insert and audit append. `overridden_at` on that write path is `clock_timestamp()`, not transaction-scoped `now()`, so a writer that started earlier but inserted later cannot sort as current. The UUID is only a last-resort tiebreak.

Rejected: accepting `original_label` from the client (the snapshot would be caller-asserted). Rejected: a `confirmed` boolean. Rejected: writing the human label into `classification_metadata` (that table is AI history). Rejected: latest-event-wins between `classified_at` and `overridden_at` (the stub classifier would silently undo an analyst). Rejected: relying on `now()` plus `id` under concurrency — two transactions can start in one order and commit in the other.

### 2026-09-09: Policy v1 reads persisted facts from a trust_score_id

Decided by: Abhinav, binding 3.6 to 3.2 / 3.3 / 3.5.

`POST /api/v1/policy-decisions` body is `{ "trust_score_id": "<uuid>", "ai_recommendation": "allow" }` only. Extra keys forbidden.

- `document_id` comes from the trust row.
- `trust_score` is that row's `consensus_value`.
- `risk_value` is the linked `risk_scores` row. A document mismatch is 422.
- `sensitivity_label` was originally `latest_for_document` on `classification_metadata`, with overrides ignored because no persist API existed. Superseded on 2026-09-10: the gate now reads the effective label (latest override, else latest classification). No classification is still 422.
- `ai_recommendation` stays caller-asserted until 3.4 exists to produce it.

Unknown `trust_score_id` is 404. Roles unchanged: `compliance_officer` and `security_admin`.

Rejected: "latest trust for this document" — append-only history, same reason 3.7 takes an explicit id. Rejected: keeping caller-supplied `trust_score` now that 3.5 persists one. Rejected: a pipeline orchestrator endpoint; that is sneaking toward 3.4.

This supersedes the request-shape sentence in "Policy v1 condition language, depth-unrolled Rego, caller-supplied facts" below. That entry's condition language still stands.

### 2026-09-09: Crypto v1 persist is trust_score_id only, after a policy row

Decided by: Abhinav, implementing 3.7 persist.

v1 selection, `SPEC.md` 3.7, `PRD.md` FR-6:

- `POST /api/v1/crypto-profiles` body is `{ "trust_score_id": "<uuid>" }` only. Extra keys forbidden. The client cannot supply `profile_type` or `document_id`.
- The stored `consensus_value` is mapped with the existing `select_crypto_profile` stub. Thresholds stay `POST_QUANTUM_MAX = 0.4` inclusive and `HYBRID_MAX = 0.8` inclusive; they remain uncalibrated placeholders.
- Persist writes one `crypto_profiles` row and `CRYPTO_PROFILE_SELECTED` in the same transaction. Reselection is a new row. `documents.current_status` is not changed.
- FR-6 is after the policy gate. v1 enforces that by requiring at least one `policy_decisions` row for the same `document_id`. The endpoint does not re-run OPA. A `deny` still counts; this table is separate history.
- Roles: `security_analyst` and `security_admin`, same allow-list as 3.3 and 3.5.

This endpoint does not encrypt or decrypt bytes. liboqs is not independently audited.

Rejected: selecting from `POST /trust-scores` (would skip the gate). Rejected: a new FK from `crypto_profiles` to `policy_decisions` (would need a data-dictionary change and a migration). Rejected: refusing persist when `final_decision` is `deny` (the gate already recorded; the profile history is independent).

### 2026-09-09: Trust v1 is an equal-weight mean over a complete agent set

Decided by: Abhinav, implementing 3.5.

v1 consensus, `SPEC.md` 3.5:

- Weighted arithmetic mean of the five `AgentType` scores.
- Each weight is `0.200`. They sum to `1.000`.
- Scores are quantized to three decimal places (half-even) before weighting, matching `agent_outputs.score` `numeric(4,3)`.
- `consensus_version = trust-weighted-mean-0.1.0`.
- A missing or duplicate type is 422. The function does not invent a score for an absent agent.

These weights have no calibration against real incident data. Equal fifths exist so the function is deterministic and reviewable, not because security and sustainability are known to contribute the same amount. Changing any weight bumps the version.

The five scores on `POST /trust-scores` are caller-asserted until 3.4 exists to produce them. Same treatment as 3.3's `after_hours`. LangGraph is Phase 5 and is not imported here.

Rejected: filling a missing agent with 0.0 or 1.0. Either default fabricates a number the audit log would then treat as real. Rejected: an opaque model call; FR-4 requires the method to be documented.

Roles: `POST /trust-scores` is `security_analyst` and `security_admin`, the same allow-list as 3.3.

### 2026-09-09: Policy v1 condition language, depth-unrolled Rego, caller-supplied facts

Decided by: Abhinav, implementing 3.6.

Closed v1 `condition_expr`:

- Combinators: `all`, `any`, `not`. Empty `all`/`any` rejected (vacuous `all` would be fail-open).
- Leaf operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`.
- Fields: `sensitivity_label`, `risk_value`, `trust_score`, `ai_recommendation`.
- Extra keys forbidden. Max combinator depth 8.

Rego forbids recursive rules (evaluation must terminate). The interpreter is therefore unrolled to depth 8 in `policy.rego`; Python rejects a deeper tree at 422 so the WASM module never sees one.

`trust_score` and `ai_recommendation` on `POST /policy-decisions` were caller-asserted when this entry was written. That request shape is superseded: `trust_score` is now read from a persisted `trust_scores` row (see "Policy v1 reads persisted facts from a trust_score_id" above). `ai_recommendation` remains caller-asserted until 3.4. The condition language in this entry is unchanged.

Host builtins provided to `opa-wasmtime`: `object.get` and `count` only, in-process. `capabilities.json` is an allowlist of the eleven builtins `policy.rego` actually uses (`assign`, `count`, `eq`, `equal`, `gt`, `gte`, `lt`, `lte`, `neq`, `object.get`, `internal.member_2`). It is not OPA `--current` minus a few names. `io.jwt.*`, `providers.aws.sign_req`, `http.*`, `net.*`, and `time.now_ns` are absent, so `opa check --capabilities` fails if they appear in the interpreter. Compile with OPA 1.8.0.

Inequality operators (`gt`/`gte`/`lt`/`lte`) are numeric-only and the comparison value must lie in `[0, 1]`, same as `eq`/`neq` on those fields. A threshold of `1.5` is 422, not a rule that never matches.

Rejected: interpreting the tree in Python and using OPA only for first-match. That would make the engine a fig leaf. Rejected: unbounded recursion in Rego; the compiler refuses it.

Roles: `POST /policy-rules` is `compliance_officer` only (FR-13). `POST /policy-decisions` is `compliance_officer` and `security_admin`.

### 2026-09-09: Contextual risk weights are placeholders, additive, versioned

Decided by: Abhinav.

v1 formula, `SPEC.md` 3.3:

- `BASE_RISK = 0.20`
- `+ NEW_DEVICE_WEIGHT (0.35)` if `device_is_new`
- `+ AFTER_HOURS_WEIGHT (0.25)` if `after_hours`
- clamp to `[0, 1]`, round half-even to four decimal places
- `model_version = contextual-risk-additive-0.1.0`

These three constants have no calibration against real incident data. They exist
so the engine is deterministic and reviewable, not because 0.35 is an empirically
justified new-device penalty. Changing any weight requires bumping
`model_version`; silent edits would make historical `risk_scores` rows
uninterpretable.

Rejected: interaction terms (e.g. new device after hours scoring higher than the
sum). v1 has no incident dataset to justify a cross term. Headroom under 1.0
(max 0.80) is intentional so later signals can join the same scale.

Rejected: treating `risk_value` as a five-agent aggregate. That number is
`trust_scores.consensus_value` (3.5). The data dictionary's original sentence
is corrected in this PR.

### 2026-09-09: after_hours is caller-asserted, not derived

Decided by: Abhinav.

`context_snapshot.after_hours` is a fact the caller sends, same as
`device_is_new`. The server does not derive it from `accessed_at`, a timezone,
or a business-hours window.

Rejected: hardcoding 09:00–17:00 UTC (or any other window) inside the scorer.
Working hours are an org policy that does not exist in this repository, and
baking one in would be a product claim disguised as a default. Server-side
derivation waits until that policy exists.

v1 snapshot is exactly five required fields, `extra="forbid"`, no nulls. An
incomplete snapshot is a 422 and never reaches the scorer.

This PR does not wire a scheduler or an event bus. Redis Streams vs Kafka stays
in Pending until recompute-on-schedule is actually built.

### 2026-09-05: Policy engine, chose OPA with Rego

Decided by: Abhinav, as integration owner. Replaces the Pending entry and
supersedes the default stated in `SPEC.md` 2.2, which has been updated to point
here. Udhav owns 3.6 and can reopen this before writing code if he disagrees;
after that the cost of switching stops being a conversation and starts being a
rewrite.

This goes against 2.2's stated default. Three things drove it.

**FR-5 is not an authorization problem, and Cedar is an authorization engine.**
Cedar answers "may this principal perform this action on this resource". FR-5 asks
"what should the system do about this document's protection, and did a rule
override what the AI proposed". `policy_rules.action` includes `require_mfa` and
`force_pqc`, which are actions the system takes, not access decisions about a
request. Expressing them through permit and forbid is a category change, not an
encoding inconvenience, and the translation layer on either side of it would be
new unverified code sitting in the module `PRD.md` R2 calls the
highest-consequence one in the system. That is the opposite of what adopting a
formally verified engine is supposed to buy.

**The merged schema already commits to semantics Cedar does not have.** Three
independent ones, all pointing the same way. `policy_rules.priority` is an integer,
lower evaluated first, unique among active rules, and that unique partial index is
what closes DEF-10 from the Sprint 3 defect log; Cedar has no rule ordering at all,
and its order-independence is one of its proven theorems rather than a setting.
`policy_decisions.rule_id` is a single nullable foreign key, matching FR-5's "and
which rule", singular; Cedar returns a set of determining policies. And
`policy_decisions.ai_recommendation` and `final_decision` both draw from a
four-value domain; Cedar answers Allow or Deny. Changing the schema to suit the
engine was considered and rejected: it is the source of truth, it came from the
CIA-I design and a real defect log, and priority ordering is a product requirement
rather than an implementation detail.

**Rules are data here, not code, and only Rego can take them that way.**
`policy_rules.condition_expr` is a `jsonb` condition tree produced by FR-13's rule
builder, and `AGENTS.md` requires one test per condition operator, which only makes
sense for a closed operator set. So the rules are structured data authored through
a UI, not policy source authored by engineers. That means one fixed, reviewed Rego
module interprets condition trees passed in as input, and no policy text is ever
generated from user input. Cedar has no data-driven equivalent, so it would require
compiling user-authored trees into Cedar source, which is code generation from user
input in the security gate. Rules-as-data also keeps the amount of Rego in the
repository small enough to review line by line, which is the direct mitigation for
Rego's measured error-proneness.

Why the determinism objection no longer decides it: it is fixable by the build
rather than by discipline. `opa check` and `opa build` accept a `--capabilities`
file listing permitted built-ins, and a policy referencing anything outside it
fails to compile. Banning the non-deterministic built-ins there turns FR-5's
determinism requirement into a CI gate, which is the standard this repository
already holds itself to everywhere else. Two caveats worth writing down now rather
than discovering later: `opa eval` does not honour capabilities for parsing
(OPA issue 6379), so the gate has to be `opa check` in CI and not a runtime flag;
and compiling to WebAssembly does not by itself remove the network built-ins, since
whether `http.send` exists depends on what the host runtime implements, so the
capabilities file is the real control and WASM is not a substitute for it.

Rejected: Cedar. Its formal guarantees are real and stronger than OPA's, and
giving them up is the actual cost of this decision, stated plainly rather than
argued away. But the property Cedar proves is order-independence, and this system
needs priority-ordered first match, so the proof covers a behaviour we are not
relying on while the behaviour that decides the outcome would move into Python
around the engine. Cedar also has no first-party Python binding, so embedding it
means `cedarpy`, which is third party and explicitly unsupported by AWS, and the
only first-party Python path is boto3 against AWS Verified Permissions.

Also rejected: AWS Verified Permissions, independently of the language choice. A
policy decision and its `audit_log` entry commit in one Postgres transaction, and a
call to a paid external service inside that transaction swaps a local function call
for a dependency that can fail, rate-limit, or hold the transaction open, while
moving evaluation somewhere the audit log cannot observe it. Deployment is out of
scope this phase anyway per `PRD.md` NG4. The same objection rules out an OPA
sidecar answering over HTTP, which is why evaluation runs in-process via a
WebAssembly bundle; that also avoids adding a container to
`infra/docker-compose.yml` and the TLS obligation `AGENTS.md` places on local
compose services.

The in-process host is `opa-wasmtime`, checked against PyPI on 2026-09-05: version
0.1.1, released September 2025, built on `wasmtime`, and it resolves cleanly on the
Python 3.13 this repository pins. It is one author and two releases, so it is the
weakest link in this decision and is named here precisely so nobody swaps it
casually. In particular, do not switch to `opa-wasm`, which looks like the more
established choice at version 0.3.2 and is not: its last release was November 2022
and it depends on `wasmer`, whose Python bindings stopped at version 1.1.0 in
January 2022 and ship no wheel newer than CPython 3.10. It cannot install on 3.13
at all. There is no well-maintained in-process OPA runtime for Python; that is the
honest state of the ecosystem, not a gap in the search.

If `opa-wasmtime` disappoints, the fallback ladder in order is: invoke the
first-party `opa` binary as a subprocess, which keeps evaluation local with no
container, no socket and no third-party binding at the cost of process spawn
latency; and only then a localhost sidecar over HTTP, accepting the network hop.
Both are reversible implementation details. The language choice is not, which is
why it is the part of this entry that had to be got right.

Revisit if: the condition operator set stays as small as it currently looks. At
that point a hand-written evaluator over a closed operator set would be fully
testable with no engine dependency at all, and the honest question becomes whether
either engine is earning its place. Not acted on now, because 2.2 framed this as a
choice between two engines and because a third option deserves its own decision
rather than being smuggled in through this one.

The rest of this entry is the criterion-by-criterion comparison against the list in
2.2, written down because several findings contradict what 2.2 assumes and nobody
should have to rediscover them. Everything below holds regardless of which way the
decision had gone.

**2.2's determinism citation is weaker than 2.2 makes it sound.** The source is
the Teleport/Doyensec Security Policy Evaluation Framework (June 2025), built on
threat-modelling research AWS itself commissioned from Trail of Bits. Cedar is
AWS's language, so "independent benchmarking" overstates it. The framework's
authors also say plainly they would not encourage using it to compare engines
against each other and that they optimised none of them. On the determinism test
specifically, testcase-06, Rego's FAIL is measured while Cedar's PASS is marked a
predicted result rather than a run one. Cedar also fails testcase-02 outright and
is predicted to fail testcase-01 and testcase-08, the last being about logging
values and decisions, which for a system built around FR-7 is not a minor column.

The broader claim survives even though that one does not. Rego measurably fails a
range of tests around undefined values, negation, side effects and
denial-of-service resilience, so "error-prone" is supported. "Non-deterministic"
is narrower than it sounds, and the precise version is more useful: Rego
evaluation is deterministic unless a policy calls one of a known set of
non-deterministic builtins, and OPA has machinery acknowledging exactly that, a
`Nondeterministic` flag per builtin, a cache for their results, and a
`--nondeterministic-builtins` switch for partial evaluation. Two of them,
`json.match_schema` and `json.verify_schema`, can dereference arbitrary URLs and
were not declared non-deterministic at all (OPA issue 8998). So on OPA the
property FR-5 needs is available but rests on author discipline. On Cedar the
engine enforces it: the Lean model carries a machine-checked theorem that
authorization produces the same result regardless of policy evaluation order or
duplicates, and no release ships without its model, proofs and differential tests
current.

**`policy_rules.priority` has no Cedar equivalent.** This is the mismatch nobody
had noticed. `docs/data-dictionary.md` gives `policy_rules` an integer `priority`,
lower evaluated first, unique among active rules, and that unique partial index is
what closes DEF-10 from the Sprint 3 defect log. That is a priority-ordered
first-match model. Cedar has no rule ordering whatsoever; its only precedence is
that `forbid` beats `permit`, and its order-independence is deliberate, one of the
proven theorems. Cedar's headline guarantee is therefore not the guarantee FR-5
asks for, and priority resolution would have to be implemented in Python around
the engine, which puts the ordering behaviour back in our own unverified code for
the part that actually decides the outcome.

Cedar's decision shape is narrower than FR-5's too. Cedar answers Allow or Deny.
`policy_rules.action` has four values, `allow`, `deny`, `require_mfa` and
`force_pqc`, and `policy_decisions` stores an `ai_recommendation` and a
`final_decision` from that same domain. Getting four outcomes from a boolean engine
means either one authorization query per candidate action, or carrying the action
in policy annotations and reading it back out of the diagnostics. Both are
encodings.

**"No rule fired, the AI recommendation stood" fits Rego and fights Cedar.**
`SPEC.md` 3.6 and FR-5 both call this the common case, and
`policy_decisions.rule_id` is nullable for it. In Rego a rule set that matches
nothing is undefined, which maps onto null directly, and one evaluation can return
the matched rule's id and action as structured JSON. Cedar defaults to deny, so
nothing matching yields a `Deny` with an empty determining-policy set, and the
caller has to read "no rule fired, defer to the AI" out of a response whose value
says Deny. Recoverable by inspecting diagnostics, but it places a semantic
inversion inside the module `PRD.md` R2 calls the highest-consequence one in the
system.

**Ecosystem maturity, checked rather than assumed.** OPA came out of the August
2025 Apple acqui-hire in better shape than 2.2 implies. It is still CNCF Graduated
with governance, licence and monthly release cadence unchanged, its maintainers now
span Apple, Google and Microsoft, and v1.19.0 shipped in July 2026. What did change
is the commercial layer: Styra's commercial offerings have been wound down, and its
paid products, Enterprise OPA, the OPA Control Plane, several SDKs and the Regal
linter, were open-sourced into the CNCF OPA organisation. 2.2's "less settled
than it was" is fair about the commercial tooling and wrong about the project.
Cedar is healthy but AWS-led rather than foundation-governed, a different risk of
the same kind that 2.2 does not mention.

**Python integration is a wash; neither engine has a first-party answer.** Cedar's
engine is Rust with no AWS-supported Python binding. In-process use means
`cedarpy`, third party, PyO3-based, explicitly not supported by AWS or the Cedar
team, though it tracks engine releases closely and ships wheels for Python 3.9
through 3.14 including Windows. OPA's canonical deployment is a sidecar answering
over HTTP, which is first-party but adds a container to
`infra/docker-compose.yml`, a network hop inside the decision path, and a TLS
obligation, since `AGENTS.md` requires TLS in transit for local compose services
too. In-process OPA means compiling Rego to WebAssembly and running the bundle
through a Python WebAssembly runtime, also third party. Two candidates exist on
PyPI and only one of them is usable here, so the names matter and are recorded
below rather than left to whoever installs it.

**AWS Verified Permissions is rejected whichever engine wins.** A policy decision
and its `audit_log` entry commit in one Postgres transaction. A network call to a
paid AWS service inside that transaction trades a local function call for a
dependency that can fail, rate-limit or hold the transaction open, and it moves
evaluation somewhere the audit log cannot observe it. Deployment of any kind is
also out of scope this phase per `PRD.md` NG4. Either engine has to run embedded
and offline, which is what the decision above settles on.

Not answered here: team familiarity. 2.2 lists it as a criterion, but nobody on the
team has production experience with either engine, so it does not discriminate
between them. It does argue for keeping the amount of hand-written Rego small,
which the rules-as-data shape above already does.

### 2026-09-05: audit appends carry a Merkle frontier instead of rereading the chain

Decided by: Abhinav, from review feedback on PR #4.

The first version of `append_entry` loaded a document's entire chain on every
append, rehashed every payload, and rebuilt the tree from scratch. That is O(n)
per write and O(n^2) over a chain's life, on the one write path every decision in
the system passes through. The system chain, meaning rows with a null
`document_id`, has no natural bound at all.

`audit_log` now carries a `frontier` column, `[[size, hash], ...]`, holding the
O(log n) Merkle state as of that row. An append reads only the current tail, found
through the `no_forked_chain` index by the property that nothing builds on it, and
extends that frontier. Details and the reasoning are in
`docs/data-dictionary.md` under `audit_log`.

What deliberately did not change: verification still rebuilds the root from the
stored payloads and never reads `frontier` or `merkle_root_at_time` back. The
whole point of `PRD.md` FR-7 is that an auditor does not have to trust state this
system wrote, so the fast path is for writing only. `app.audit.merkle` holds both,
and a property test asserts the incremental root equals a full rebuild at every
length from 0 to 34; if they ever diverge, the incremental path is wrong.

Rejected: keeping the full rebuild and treating this as acceptable at coursework
data volumes. It would have been, right up until the risk engine started
recomputing scores on a schedule, and by then the signature would have been baked
into three other modules. Also rejected: dropping the per-row
`merkle_root_at_time` so appends became trivially O(1). That column is what makes
tampering detectable per row and is what external anchoring would commit to.

Consequence worth stating: `frontier` is derived data living in an append-only
table, and a wrong one would produce a plausible but wrong root for every entry
after it. `frontier_from_json` therefore validates the structure, sizes, and
digests on the way back in rather than trusting the database, and an append against
a malformed frontier fails instead of continuing.

### 2026-09-05: `docs/data-dictionary.md` is the schema's source of truth

Decided by: Abhinav.

`SPEC.md` Section 5 pointed the column-level data dictionary and ER diagram at a
"system design reference document" that is not in this repository, and `docs/`
has no `er-diagram.svg`. `AGENTS.md` already warned against inventing columns
against a reference nobody can open, which left the data model blocked.

The document exists outside the repository as the team's CIA-I submission. It is
now used as a reference, not as the citation: `docs/data-dictionary.md` is
written in-repo, is the cited source of truth, and `SPEC.md` Section 5 and
`AGENTS.md`'s code-style note both point at it.

Why in-repo rather than committing the PDF: a schema reference has to be
reviewable in a diff and changeable in the same pull request as the migration
that implements it. A binary attachment satisfies neither, and a column rename
would then be invisible to review. Every place the models depart from CIA-I is
listed in that file's "Deviations" section with the reason, so the coursework
document stays traceable rather than being quietly overwritten.

### 2026-09-05: Four schema calls made while writing the models

Decided by: Abhinav. Detail and the full deviation list: `docs/data-dictionary.md`.

Recorded here because each one is a choice someone could reasonably have made
differently, and all four are cheap to change now and expensive later.

**Sensitivity labels are stored uppercase.** CIA-I lowercases them. The shipped
`SensitivityLabel` enum in `backend/app/classifier/labels.py` uses `PUBLIC` and
already serializes that way in the live `/classify` response, so matching it
keeps one representation across the API and the database instead of a mapping
layer between them. The alternative meant editing the classifier owner's module
and its tests to satisfy a casing preference. Changing this later means changing
`labels.py` and the database enum in one pull request.

**`audit_log` gains a `payload` column.** CIA-I stores only `payload_hash`. A
hash with no payload can confirm that a stored row has not changed, but nobody
can independently re-derive what the decision actually was, which is most of what
`SPEC.md` 3.8 is for. The payload is stored as `jsonb` and hashed canonically, so
the hash still verifies after a round trip through Postgres key reordering.

**`audit_log` gains a nullable `actor_id`.** CIA-I's Output Screen 2 specifies an
"Actor" column sourced from the acting user, but no column held one, so that
screen could not have been built as specified. Nullable because system-initiated
events have no human actor and a sentinel user row would be a false statement.

**Development accounts are seeded by a script, not a migration.** Four tables
have foreign keys to `users.id` while the API's identity source is still the
header-trusting stub, so no request could satisfy them without a row per role.
`python -m app.db.seed` is idempotent and labelled a stub in code, docstring, and
tests. Deliberately not an Alembic data migration: a migration inserting people
into `users` would run against every database the chain is ever applied to,
including a future non-development one. It is deleted, along with the
`first_by_role` lookup, when real authentication lands.

### 2026-09-05: Code Owner review and a one-approval minimum, now enabled

Decided by: Abhinav. Supersedes the deferral logged on 2026-09-04.

`@sukhideas` now has write access, so both owners named in `.github/CODEOWNERS`
resolve and the silent no-op described in that earlier entry no longer applies.
Branch protection on `main` is therefore tightened to:

- `require_code_owner_reviews: true`
- `required_approving_review_count: 1`

Consequence worth stating plainly, because it changes everyone's workflow:
GitHub does not let an author approve their own pull request. Every change to
`main` now needs a second person, including Abhinav's. That is the intent, not a
side effect, but it does mean no one can land work solo any more.

Ordering note for anyone repeating this: enable the approval minimum only after
any in-flight pull request has merged. Turning it on with an open PR authored by
the sole admin blocks that PR outright, since there is nobody eligible to
approve it.

If a genuine emergency ever requires bypassing this, the honest route is to
lower the setting, land the fix, and put it back, leaving the change visible in
the audit trail. Do not add an exemption that quietly persists.

### 2026-09-04: Branching model, trunk-based with no long-lived branches

Decided by: Abhinav.

`main` is the only long-lived branch. There is no `develop` branch, no `release/*`
branches, and no per-person branches.

All work happens on short-lived branches:

- Named `feature/<module>-<short-description>`, for example
  `feature/5-2-classifier-stub` or `feature/phase-1-bootstrap`.
- Branched from an up-to-date `main`.
- Merged back into `main` via pull request only, never by direct push.
- Deleted immediately after merge.

Why: with three contributors and a module ownership split already enforced by
review (`WORK_DIVISION.md`), a long-lived integration branch adds a second merge
surface and a second place for CI to diverge from what actually ships, while
solving a coordination problem this team size does not have. Trunk-based keeps
one branch protected, one CI target, and one definition of "current".

Consequence to keep in mind: because `main` is the integration point, a feature
branch that lives longer than a few days starts accumulating drift and the
"require branches to be up to date before merging" rule will force repeated
rebases. That is the intended pressure, it is a signal to split the change into
smaller pull requests, not a reason to introduce a long-lived branch.

Rejected: Git Flow, its `develop` and `release/*` branches are designed around
versioned, batched releases to external consumers, which this phase explicitly
does not have (`PRD.md` Non-Goal NG4).

### 2026-09-04: CODEOWNERS added, but Code Owner review enforcement deferred

Decided by: Abhinav.

`.github/CODEOWNERS` now exists and maps the three highest-consequence backend
modules (`backend/app/crypto/`, `backend/app/policy/`, `backend/app/audit/`) to
`@UdhavFr` and `frontend/` to `@sukhideas`, matching the required-reviewer rule
already stated in `AGENTS.md` and `WORK_DIVISION.md`.

The usernames are real GitHub accounts, not placeholders. Despite that,
**"Require review from Code Owners" is deliberately NOT enabled in branch
protection yet**, and neither is a minimum approval count.

Why: a CODEOWNERS entry naming an account that lacks write access to the
repository does not block a merge, GitHub ignores the entry and the pull request
merges as if no owner were assigned. The failure mode is silent, there is no
error surfaced on the pull request, which makes it strictly worse than not
configuring the rule at all, an unenforced rule that is believed to be enforced.
At the time of writing, `@UdhavFr` has write access and would resolve correctly,
but `@sukhideas` is not yet a collaborator, so the `frontend/` line would be one
of these silent no-ops. A minimum approval count is also deferred because with
effectively one active reviewer, requiring approvals blocks all merges rather
than improving them.

Revisit when: `@sukhideas` has been added as a collaborator with write access.
At that point verify both owners resolve (GitHub shows unresolvable owners in the
repository's CODEOWNERS settings view, and a pull request touching an owned path
should auto-request the owner as a reviewer, that auto-request is the observable
proof the entry works), then enable "Require review from Code Owners" and set a
minimum approval count of 1 in the same change.

Until then, the reviewer requirement is enforced by convention and review
discipline as documented in `AGENTS.md`, not by the platform. Treat it as such.

<!-- Add entries above this line, most recent first. Example format:

### 2026-08-20: Vector store, chose pgvector

Decided by: Whoever made the call.
Why: one fewer service to run, and the filtered-search volumes here are nowhere near where a dedicated store starts paying for itself.
Rejected: Qdrant, better filtered-search performance at scale, but that scale is not in evidence and it adds a container.

-->
