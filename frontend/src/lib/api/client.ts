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
  ClassificationRequest,
  ClassificationResponse,
  DocumentRegistrationRequest,
  DocumentResponse,
  HealthResponse,
  ManualOverrideRequest,
  ManualOverrideResponse,
  PolicyRuleRequest,
  PolicyRuleTestResponse,
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
