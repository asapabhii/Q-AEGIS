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

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/** Shape of the error body the backend returns on 4xx/5xx. */
export interface ApiErrorDetail {
  detail: string | Record<string, unknown>[];
}
