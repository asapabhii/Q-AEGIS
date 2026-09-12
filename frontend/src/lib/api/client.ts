/**
 * Centralized API client for Q-AEGIS Shield.
 *
 * Every call to the backend goes through this module. No inline fetch() in
 * components — that rule is in AGENTS.md and exists so there is one place to
 * change when the backend's contract or the authorization mechanism changes.
 *
 * Authorization plumbing: the X-Q-AEGIS-Actor-Role header is a STUB that
 * trusts a forgeable header to state the caller's role. It is NOT
 * authentication. See backend/app/api/deps.py for the full explanation. Do
 * not build a login screen on this header and do not describe it as auth in
 * the UI or in the code.
 */

import type {
  AuditChainResponse,
  ClassificationRequest,
  ClassificationResponse,
  CryptoProfileResponse,
  DocumentInventoryResponse,
  DocumentRegistrationRequest,
  DocumentResponse,
  DocumentSnapshot,
  HealthResponse,
  ManualOverrideRequest,
  ManualOverrideResponse,
  PolicyDecisionResponse,
  PolicyRuleRequest,
  PolicyRuleResponse,
  PolicyRuleTestResponse,
  RiskScoreRequest,
  RiskScoreResponse,
  TrustScoreRequest,
  TrustScoreResponse,
  UserRole,
} from "./types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Base URL for the backend API. Reads from the NEXT_PUBLIC_API_URL
 * environment variable; falls back to the local dev server address.
 *
 * Uses 127.0.0.1 (not localhost) per docs/LOCAL_DEV.md: on Windows, localhost
 * resolves to ::1 first while the containers publish on IPv4 only, causing
 * hangs rather than clean refusals.
 */
const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Header name for the caller-role stub. Defined once here and in the backend
 * at backend/app/api/deps.py as ACTOR_ROLE_HEADER.
 */
const ACTOR_ROLE_HEADER = "X-Q-AEGIS-Actor-Role";

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as Record<string, unknown>).msg)
          : JSON.stringify(item)
      )
      .join("; ");
  }
  return JSON.stringify(detail);
}

/** Structured error thrown when the backend returns a non-2xx response. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly body: unknown
  ) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? formatDetail((body as Record<string, unknown>).detail)
        : statusText;
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, options);

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  return (await response.json()) as T;
}

function roleHeaders(role: UserRole): HeadersInit {
  return {
    "Content-Type": "application/json",
    [ACTOR_ROLE_HEADER]: role,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/health — liveness check.
 *
 * Deliberately unauthenticated: a liveness probe is consumed by the container
 * runtime before any user identity exists.
 */
export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health");
}

/**
 * POST /api/v1/documents — register a document's metadata.
 *
 * This is step 1 of the register-then-classify flow. The returned document_id
 * is a real foreign key that POST /api/v1/classify requires.
 */
export async function registerDocument(
  body: DocumentRegistrationRequest,
  role: UserRole
): Promise<DocumentResponse> {
  return request<DocumentResponse>("/api/v1/documents", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

/**
 * GET /api/v1/documents — current risk and protection status for every document.
 *
 * Writes nothing. Stage fields are null until that step has run. data_owner
 * is refused; this is the fleet view, not FR-16.
 */
export async function listDocuments(
  role: UserRole
): Promise<DocumentInventoryResponse> {
  return request<DocumentInventoryResponse>("/api/v1/documents", {
    method: "GET",
    headers: roleHeaders(role),
  });
}

/**
 * GET /api/v1/documents/{id} — one document's current snapshot.
 *
 * Same field contract as one row of listDocuments. Unknown id is 404.
 */
export async function getDocument(
  documentId: string,
  role: UserRole
): Promise<DocumentSnapshot> {
  return request<DocumentSnapshot>(
    `/api/v1/documents/${encodeURIComponent(documentId)}`,
    {
      method: "GET",
      headers: roleHeaders(role),
    }
  );
}

/**
 * GET /api/v1/audit/entries — one document's chain, genesis first.
 *
 * Writes nothing. No is_valid on this response; call verify separately.
 * document_id is required.
 */
export async function listAuditEntries(
  documentId: string,
  role: UserRole
): Promise<AuditChainResponse> {
  const query = new URLSearchParams({ document_id: documentId });
  return request<AuditChainResponse>(`/api/v1/audit/entries?${query.toString()}`, {
    method: "GET",
    headers: roleHeaders(role),
  });
}

/**
 * POST /api/v1/classify — classify a registered document.
 *
 * This is step 2 of the register-then-classify flow. Calling this with a
 * document_id that was not registered first returns 404 — that is correct
 * backend behaviour, not a bug.
 */
export async function classifyDocument(
  body: ClassificationRequest,
  role: UserRole
): Promise<ClassificationResponse> {
  return request<ClassificationResponse>("/api/v1/classify", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

/**
 * Convenience: register a document then classify it in one call.
 *
 * This is the real shape of the flow. Every screen that classifies a document
 * must register it first because classification_metadata.document_id is a
 * foreign key to documents.id.
 */
export async function registerAndClassify(
  filename: string,
  content: string,
  role: UserRole
): Promise<{ document: DocumentResponse; classification: ClassificationResponse }> {
  const document = await registerDocument({ filename }, role);
  const classification = await classifyDocument(
    { document_id: document.id, content },
    role
  );
  return { document, classification };
}

/**
 * POST /api/v1/manual-overrides — persist a human relabel.
 *
 * original_label is computed server-side. Do not send it, and do not send a
 * confirmed boolean: the checkbox is a UI gate, not an API field.
 */
export async function overrideClassification(
  body: ManualOverrideRequest,
  role: UserRole
): Promise<ManualOverrideResponse> {
  return request<ManualOverrideResponse>("/api/v1/manual-overrides", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

/**
 * POST /api/v1/policy-rules — persist one override rule.
 *
 * Name must be unique. Priority must be unique among active rules. Extra
 * keys are forbidden. Role: compliance_officer.
 */
export async function createPolicyRule(
  body: PolicyRuleRequest,
  role: UserRole
): Promise<PolicyRuleResponse> {
  return request<PolicyRuleResponse>("/api/v1/policy-rules", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

/**
 * POST /api/v1/policy-rules/test — dry-run a candidate against recent decisions.
 *
 * Does not save the rule. Do not send a window or limit; the server uses 20.
 */
export async function testPolicyRule(
  body: PolicyRuleRequest,
  role: UserRole
): Promise<PolicyRuleTestResponse> {
  return request<PolicyRuleTestResponse>("/api/v1/policy-rules/test", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Risk scoring — SPEC.md 3.3
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/risk-scores — compute a contextual risk score for one access event.
 *
 * The server returns the score and its context snapshot. This is a write
 * endpoint: the score is persisted and its id becomes the foreign key for
 * POST /api/v1/trust-scores.
 */
export async function submitRiskScore(
  body: RiskScoreRequest,
  role: UserRole
): Promise<RiskScoreResponse> {
  return request<RiskScoreResponse>("/api/v1/risk-scores", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Trust engine — SPEC.md 3.4 / 3.5
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/trust-scores — record five agent outputs and compute consensus.
 *
 * The server persists each AgentOutput row, then derives the equal-weight
 * trust score. risk_score_id must reference an existing risk score.
 */
export async function submitTrustScore(
  body: TrustScoreRequest,
  role: UserRole
): Promise<TrustScoreResponse> {
  return request<TrustScoreResponse>("/api/v1/trust-scores", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Crypto profile selection — SPEC.md 3.7
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/crypto-profiles — select and persist the protection profile.
 *
 * trust_score_id must reference an existing trust score. The server selects
 * the profile based on the policy engine's decision and the trust consensus.
 */
export async function selectCryptoProfile(
  trustScoreId: string,
  role: UserRole
): Promise<CryptoProfileResponse> {
  return request<CryptoProfileResponse>("/api/v1/crypto-profiles", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify({ trust_score_id: trustScoreId }),
  });
}

// ---------------------------------------------------------------------------
// Audit verification — SPEC.md 3.8
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/audit/verify — verify the chain integrity for one document.
 *
 * Returns whether the chain is intact, along with the chain length and any
 * tampered entry indices.
 */
export async function verifyAuditChain(
  documentId: string,
  role: UserRole
): Promise<{
  document_id: string;
  is_valid: boolean;
  chain_length: number;
  tampered_indices: number[];
}> {
  const query = new URLSearchParams({ document_id: documentId });
  return request<{
    document_id: string;
    is_valid: boolean;
    chain_length: number;
    tampered_indices: number[];
  }>(`/api/v1/audit/verify?${query.toString()}`, {
    method: "GET",
    headers: roleHeaders(role),
  });
}

// ---------------------------------------------------------------------------
// Policy decisions — SPEC.md 3.6
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/policy-decisions — evaluate a policy decision for a document.
 *
 * Returns the matched rule (if any) and the final decision. The server reads
 * the document's current sensitivity label and risk score, evaluates the
 * active rules in priority order, and returns the first match or a default
 * allow.
 */
export async function evaluatePolicyDecision(
  documentId: string,
  role: UserRole
): Promise<PolicyDecisionResponse> {
  return request<PolicyDecisionResponse>("/api/v1/policy-decisions", {
    method: "POST",
    headers: roleHeaders(role),
    body: JSON.stringify({ document_id: documentId }),
  });
}
