/**
 * API type definitions for the Q-AEGIS Shield frontend.
 *
 * These types mirror the backend's Pydantic response models exactly:
 *   - HealthResponse:          backend/app/api/routes/health.py
 *   - DocumentResponse:        backend/app/api/routes/documents.py
 *   - ClassificationResponse:  backend/app/classifier/schemas.py
 *   - UserRole:                backend/app/db/enums.py
 *   - SensitivityLabel:        backend/app/classifier/labels.py
 *   - DocumentStatus:          backend/app/db/enums.py
 *   - RiskScoreResponse:       backend/app/risk_engine/schemas.py
 *   - TrustScoreResponse:      backend/app/trust_engine/schemas.py
 *   - PolicyDecisionResponse:  backend/app/policy/schemas.py
 *   - CryptoProfileResponse:   backend/app/crypto/schemas.py
 *   - AuditEntry:              backend/app/api/routes/audit.py
 *
 * Keep these in sync with the backend. If a backend model changes, update
 * the corresponding type here in the same PR.
 */

// ---------------------------------------------------------------------------
// Domain enums
// ---------------------------------------------------------------------------

/**
 * Caller roles recognized by the backend.
 * Prefer JWT login; X-Q-AEGIS-Actor-Role is a DEV-ONLY bypass.
 */
export type UserRole =
  | "data_owner"
  | "security_analyst"
  | "security_admin"
  | "compliance_officer"
  | "auditor"
  | "ciso"
  | "engineer";

/** Sensitivity labels, ordered least to most sensitive in the backend. */
export type SensitivityLabel =
  | "PUBLIC"
  | "INTERNAL"
  | "CONFIDENTIAL"
  | "RESTRICTED";

/** Document lifecycle stages from backend/app/db/enums.py. */
export type DocumentStatus =
  | "registered"
  | "uploaded"
  | "classified"
  | "protected"
  | "archived";

/** Protection profile selected after the policy gate. */
export type CryptoProfileType = "aes256" | "hybrid" | "post_quantum";

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

/** GET /api/v1/health — liveness check, deliberately unauthenticated. */
export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

/** POST /api/v1/documents — request body. */
export interface DocumentRegistrationRequest {
  filename: string;
}

/** POST /api/v1/documents — response body. */
export interface DocumentResponse {
  id: string;
  filename: string;
  storage_path: string | null;
  current_status: DocumentStatus;
  uploaded_by: string;
  uploaded_at: string;
}

/** GET /api/v1/documents/{id} — current risk and protection snapshot. */
export interface DocumentSnapshot {
  id: string;
  filename: string;
  storage_path: string | null;
  current_status: DocumentStatus;
  uploaded_by: string;
  uploaded_at: string;
  sensitivity_label: SensitivityLabel | null;
  label_source: SensitivitySource | null;
  override_id: string | null;
  classification_id: string | null;
  risk_score_id: string | null;
  risk_value: string | null;
  risk_computed_at: string | null;
  trust_score_id: string | null;
  trust_score: string | null;
  trust_computed_at: string | null;
  policy_decision_id: string | null;
  final_decision: PolicyAction | null;
  decided_at: string | null;
  crypto_profile_id: string | null;
  profile_type: CryptoProfileType | null;
  selected_at: string | null;
}

/** GET /api/v1/documents — FR-14 inventory. */
export interface DocumentInventoryResponse {
  count: number;
  documents: DocumentSnapshot[];
}

// ---------------------------------------------------------------------------
// Classification
// ---------------------------------------------------------------------------

/** POST /api/v1/classify — request body. */
export interface ClassificationRequest {
  document_id: string;
  content: string;
}

/**
 * POST /api/v1/classify — response body.
 *
 * The four fields required by SPEC.md 3.2's API contract are
 * sensitivity_label, confidence, model_version, and is_defaulted.
 * The rest support FR-16's risk breakdown and FR-12's override screen.
 */
export interface ClassificationResponse {
  document_id: string;
  sensitivity_label: SensitivityLabel;
  confidence: number;
  model_version: string;
  is_defaulted: boolean;
  base_label: SensitivityLabel;
  confidence_threshold: number;
  matched_keywords: string[];
  rationale: string;
  classified_at: string;
}

/** Where the effective sensitivity label was read from. */
export type SensitivitySource = "classification" | "manual_override";

/** POST /api/v1/manual-overrides — request body. */
export interface ManualOverrideRequest {
  document_id: string;
  new_label: SensitivityLabel;
  justification: string;
}

/** POST /api/v1/manual-overrides — response body. */
export interface ManualOverrideResponse {
  id: string;
  document_id: string;
  overridden_by: string;
  original_label: SensitivityLabel;
  new_label: SensitivityLabel;
  justification: string;
  overridden_at: string;
}

/** An action a policy rule can take. */
export type PolicyAction = "allow" | "deny" | "require_mfa" | "force_pqc";

/** POST /api/v1/policy-rules and /policy-rules/test — request body. */
export interface PolicyRuleRequest {
  rule_name: string;
  condition_expr: Record<string, unknown>;
  action: PolicyAction;
  priority: number;
}

/** POST /api/v1/policy-rules — persisted rule. */
export interface PolicyRuleResponse {
  id: string;
  rule_name: string;
  condition_expr: Record<string, unknown>;
  action: PolicyAction;
  priority: number;
  active: boolean;
  created_at: string;
}

/** POST /api/v1/policy-rules/test — one historical replay. */
export interface PolicyRuleTestReplay {
  decision_id: string;
  document_id: string;
  decided_at: string;
  sensitivity_label: SensitivityLabel;
  recorded_final_decision: PolicyAction;
  would_match: boolean;
  hypothetical_final_decision: PolicyAction;
  would_change_outcome: boolean;
}

/** POST /api/v1/policy-rules/test — response body. Nothing is persisted. */
export interface PolicyRuleTestResponse {
  rule_name: string;
  action: PolicyAction;
  priority: number;
  condition_expr: Record<string, unknown>;
  window: number;
  considered: number;
  skipped: number;
  replays: PolicyRuleTestReplay[];
}

/** GET /api/v1/audit/entries — one chain row. No frontier, no is_valid. */
export interface AuditEntry {
  id: string;
  index: number;
  actor_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  payload_hash: string;
  prev_hash: string | null;
  merkle_root_at_time: string;
  created_at: string;
}

/** GET /api/v1/audit/entries — one document's chain, genesis first. */
export interface AuditChainResponse {
  document_id: string;
  count: number;
  entries: AuditEntry[];
}

/** GET /api/v1/audit/verify — independent prefix check. Not a list field. */
export interface AuditVerifyResponse {
  is_valid: boolean;
  computed_root: string;
  stored_root: string;
  end_index: number;
  entry_count: number;
  document_id: string | null;
}

// ---------------------------------------------------------------------------
// Audit checkpoints and RFC 6962 proofs — SPEC.md 3.8 (PQ-signed anchoring)
// ---------------------------------------------------------------------------

/** POST /api/v1/audit/checkpoint — request body. */
export interface CreateCheckpointRequest {
  /** Omit/null anchors the system chain. */
  document_id?: string | null;
  /** Omit anchors the full chain as it stands. */
  tree_size?: number | null;
}

/**
 * A Signed Tree Head: an ML-DSA-87 signature over (document_id, tree_size,
 * signed_at, merkle_root). `public_key` is the hex key the signature verifies
 * under; an auditor pins it out-of-band. Returned by POST /audit/checkpoint
 * and GET /audit/checkpoints.
 */
export interface SignedCheckpointResponse {
  checkpoint_id: string;
  document_id: string | null;
  tree_size: number;
  merkle_root: string;
  signed_at: string;
  algorithm: string;
  signature: string;
  signing_key_id: string;
  public_key: string;
}

/** GET /api/v1/audit/checkpoint/{id}/verify — independent re-check outcome. */
export interface CheckpointVerificationResponse {
  is_valid: boolean;
  signature_valid: boolean;
  root_matches: boolean;
  stored_root: string;
  recomputed_root: string;
  tree_size: number;
  signed_at: string;
  algorithm: string;
  public_key: string;
  document_id: string | null;
}

/** GET /api/v1/audit/signing-key — the active key's public half, for pinning. */
export interface SigningKeyResponse {
  signing_key_id: string;
  algorithm: string;
  public_key: string;
  created_at: string;
}

/** GET /api/v1/audit/inclusion-proof — RFC 6962 proof for one entry. */
export interface InclusionProofResponse {
  document_id: string | null;
  leaf_index: number;
  tree_size: number;
  audit_path: string[];
  leaf_hash: string;
  root: string;
  payload: Record<string, unknown>;
}

/** GET /api/v1/audit/consistency-proof — RFC 6962 append-only proof. */
export interface ConsistencyProofResponse {
  document_id: string | null;
  old_size: number;
  new_size: number;
  nodes: string[];
  old_root: string;
  new_root: string;
}

/** POST /api/v1/assessments — full P0 pipeline. */
export interface AssessmentRequest {
  document_id: string;
  device_id: string;
  device_is_new: boolean;
  accessed_at: string;
  /** IANA timezone the server derives after_hours against; optional. */
  org_timezone?: string;
  content?: string;
  ai_recommendation?: PolicyAction;
}

/** POST /api/v1/assessments — response. */
export interface AssessmentResponse {
  document_id: string;
  risk_score_id: string;
  trust_score_id: string;
  consensus_value: string;
  ai_recommendation: PolicyAction;
  policy_decision_id: string;
  final_decision: PolicyAction;
  overridden: boolean;
  crypto_profile_id: string;
  profile_type: CryptoProfileType;
  ciphertext_id: string | null;
  encrypted: boolean;
  reselected: boolean;
}

/** POST /api/v1/auth/login */
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  role: UserRole;
  name: string;
}

/** GET /api/v1/auth/me */
export interface MeResponse {
  id: string;
  email: string;
  role: UserRole;
  name: string;
  auth_mode: string;
}

/** POST /api/v1/documents/{id}/upload */
export interface UploadResponse {
  document_id: string;
  filename: string;
  storage_path: string;
  current_status: DocumentStatus;
  size_bytes: number;
  extracted_text_chars: number;
  extracted_text_preview: string;
  extracted_text: string;
}

/** GET /api/v1/documents/{id}/agents */
export interface AgentDeepDiveResponse {
  document_id: string;
  risk_score_id: string | null;
  assessed_at: string | null;
  agents: {
    id: string;
    agent_type: AgentType;
    score: string;
    rationale: string;
  }[];
  missing_agents: AgentType[];
  note: string | null;
}

/** POST /api/v1/shred — request / response (FR-8). */
export interface ShredRequest {
  document_id: string;
  confirmed: boolean;
}

export interface ShredResponse {
  document_id: string;
  ciphertext_count: number;
  newly_destroyed: number;
  already_shredded: boolean;
  irreversible: boolean;
}

/** POST /api/v1/migration-schedule/rank (FR-9). */
export interface MigrationRankRequest {
  budget: number;
  window_days?: number;
  seed?: number;
}

export interface BaselineComparison {
  method: string;
  selected_ids: string[];
  total_score: number;
  total_cost: number;
}

export interface MigrationScheduleItem {
  id: string;
  document_id: string;
  priority_rank: number;
  scheduled_upgrade_date: string | null;
  status: string;
  constraint_snapshot: Record<string, unknown>;
}

export interface MigrationRankResponse {
  schedule: MigrationScheduleItem[];
  primary: BaselineComparison;
  baselines: BaselineComparison[];
  constraint_snapshot: Record<string, unknown>;
  ranked_at: string;
}

/** FR-10 knowledge graph */
export interface GraphSeedResponse {
  nodes_upserted: number;
  relationships_upserted: number;
  demo: boolean;
}

export interface GraphNode {
  labels: string[];
  key: string;
  properties: Record<string, unknown>;
}

export interface GraphPath {
  hops: number;
  nodes: GraphNode[];
  relationships: string[];
  summary: string;
}

export interface AttackPathResponse {
  document_id: string | null;
  paths: GraphPath[];
  note: string | null;
}

/** FR-11 agentic RAG */
export interface RagAskRequest {
  question: string;
  document_id?: string | null;
}

export interface RagCitation {
  chunk_id: string;
  source_type: string;
  source_id: string | null;
  document_id: string | null;
  content: string;
  score: number;
}

export interface RagAnswer {
  question: string;
  answer: string;
  verified: boolean;
  plan: string;
  citations: RagCitation[];
  embedding_model: string;
  refusal_reason: string | null;
}

export interface RagIngestResult {
  document_id: string;
  chunks_written: number;
  embedding_model: string;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/** Shape of the error body the backend returns on 4xx/5xx. */
export interface ApiErrorDetail {
  detail: string | Record<string, unknown>[];
}

// ---------------------------------------------------------------------------
// Contextual risk scoring — SPEC.md 3.3
// ---------------------------------------------------------------------------

/** POST /api/v1/risk-scores — request body. */
export interface RiskScoreRequest {
  document_id: string;
  actor_user_id: string;
  device_id: string;
  device_is_new: boolean;
  accessed_at: string;
  /** IANA timezone the server derives after_hours against; optional. */
  org_timezone?: string;
}

/** POST /api/v1/risk-scores — response body. */
export interface RiskScoreResponse {
  id: string;
  document_id: string;
  /** Decimal serialized as a JSON string by Pydantic v2. */
  risk_value: string;
  model_version: string;
  context_snapshot: {
    actor_user_id: string;
    device_id: string;
    device_is_new: boolean;
    accessed_at: string;
    after_hours: boolean;
  };
  computed_at: string;
}

// ---------------------------------------------------------------------------
// Multi-agent assessment and trust consensus — SPEC.md 3.4 and 3.5
// ---------------------------------------------------------------------------

/** The five independent risk agents, from backend/app/db/enums.py. */
export type AgentType =
  | "security"
  | "compliance"
  | "contextual"
  | "quantum"
  | "sustainability";

/** One caller-supplied agent score in POST /api/v1/trust-scores. */
export interface AgentOutputInput {
  agent_type: AgentType;
  score: number;
  rationale: string;
}

/** POST /api/v1/trust-scores — request body. */
export interface TrustScoreRequest {
  risk_score_id: string;
  outputs: AgentOutputInput[];
}

/** One persisted agent output in a trust-score response. */
export interface AgentOutputResponse {
  id: string;
  agent_type: AgentType;
  /** Decimal serialized as a JSON string by Pydantic v2. */
  score: string;
  rationale: string;
}

/** POST /api/v1/trust-scores — response body. */
export interface TrustScoreResponse {
  id: string;
  document_id: string;
  risk_score_id: string;
  /** Decimal serialized as a JSON string by Pydantic v2. */
  consensus_value: string;
  consensus_version: string;
  outputs: AgentOutputResponse[];
  computed_at: string;
}

// ---------------------------------------------------------------------------
// Policy engine — SPEC.md 3.6
// ---------------------------------------------------------------------------

/**
 * Leaf operators in the closed v1 condition language, from
 * backend/app/policy/conditions.py. Combinators (`all`, `any`, `not`) structure
 * a tree; these operators compare one field to one value.
 */
export type ConditionOperator =
  | "eq"
  | "neq"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "in";

/** POST /api/v1/policy-decisions — request body. */
export interface PolicyDecisionRequest {
  trust_score_id: string;
  ai_recommendation?: PolicyAction;
}

/** POST /api/v1/policy-decisions — response body. */
export interface PolicyDecisionResponse {
  id: string;
  document_id: string;
  trust_score_id: string;
  risk_score_id: string;
  classification_id: string;
  override_id: string | null;
  label_source: SensitivitySource;
  sensitivity_label: SensitivityLabel;
  /** Decimal serialized as a JSON string by Pydantic v2. */
  risk_value: string;
  /** Decimal serialized as a JSON string by Pydantic v2. */
  trust_score: string;
  rule_id: string | null;
  rule_name: string | null;
  ai_recommendation: PolicyAction;
  final_decision: PolicyAction;
  overridden: boolean;
  policy_version: string;
  decided_at: string;
}

// ---------------------------------------------------------------------------
// Crypto Profiles and Shredding — SPEC.md 3.7 & 3.9
// ---------------------------------------------------------------------------

/** POST /api/v1/crypto-profiles — response body. */
export interface CryptoProfileResponse {
  id: string;
  document_id: string;
  trust_score_id: string;
  profile_type: CryptoProfileType;
  /** Decimal serialized as a JSON string by Pydantic v2. */
  consensus_value: string;
  selected_at: string;
}

// ---------------------------------------------------------------------------
// Migration schedule — SPEC.md 3.10
// ---------------------------------------------------------------------------

/** One document's place in the post-quantum upgrade queue. */
export interface MigrationScheduleEntry {
  id: string;
  document_id: string;
  priority_rank: number;
  scheduled_upgrade_date: string | null;
  status: "pending" | "in_progress" | "done";
  constraint_snapshot: Record<string, unknown>;
}
