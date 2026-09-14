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
 *
 * Keep these in sync with the backend. If a backend model changes, update
 * the corresponding type here in the same PR.
 */

// ---------------------------------------------------------------------------
// Domain enums
// ---------------------------------------------------------------------------

/**
 * Caller roles recognized by the backend's authorization guard.
 *
 * IMPORTANT: The guard is a STUB that trusts a forgeable header
 * (X-Q-AEGIS-Actor-Role). It is authorization plumbing, not authentication.
 * See backend/app/api/deps.py for the full explanation.
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

/** POST /api/v1/assessments — full P0 pipeline. */
export interface AssessmentRequest {
  document_id: string;
  device_id: string;
  device_is_new: boolean;
  accessed_at: string;
  after_hours: boolean;
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

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/** Shape of the error body the backend returns on 4xx/5xx. */
export interface ApiErrorDetail {
  detail: string | Record<string, unknown>[];
}
