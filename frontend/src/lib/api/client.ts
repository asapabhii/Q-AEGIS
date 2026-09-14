/**
 * Centralized API client for Q-AEGIS Shield.
 *
 * Primary auth: Authorization Bearer JWT from localStorage.
 * Dev-only fallback: X-Q-AEGIS-Actor-Role when AUTH_DEV_HEADER_BYPASS is on
 * and no token is stored.
 */

import {
  getAccessToken,
  getDevRole,
  setSession,
  type SessionUser,
} from "@/lib/auth/session";
import type {
  AgentDeepDiveResponse,
  AssessmentRequest,
  AssessmentResponse,
  AuditChainResponse,
  AuditVerifyResponse,
  ClassificationRequest,
  ClassificationResponse,
  DocumentInventoryResponse,
  DocumentRegistrationRequest,
  DocumentResponse,
  DocumentSnapshot,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  ManualOverrideRequest,
  ManualOverrideResponse,
  MeResponse,
  PolicyRuleRequest,
  PolicyRuleResponse,
  PolicyRuleTestResponse,
  UploadResponse,
  UserRole,
  MigrationRankRequest,
  MigrationRankResponse,
  ShredRequest,
  ShredResponse,
} from "./types";

const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const ACTOR_ROLE_HEADER = "X-Q-AEGIS-Actor-Role";

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

function authHeaders(
  role?: UserRole,
  extra?: HeadersInit
): HeadersInit {
  const headers = new Headers(extra);
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    const effective = role ?? getDevRole();
    if (effective) {
      headers.set(ACTOR_ROLE_HEADER, effective);
    }
  }
  if (!headers.has("Content-Type") && !(extra instanceof FormData)) {
    // Leave Content-Type unset for FormData; browser sets boundary.
  }
  return headers;
}

function jsonHeaders(role?: UserRole): HeadersInit {
  const headers = new Headers(authHeaders(role));
  headers.set("Content-Type", "application/json");
  return headers;
}

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health");
}

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const result = await request<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const user: SessionUser = {
    id: result.user_id,
    email: result.email,
    role: result.role,
    name: result.name,
  };
  setSession(result.access_token, user);
  return result;
}

export async function getMe(role?: UserRole): Promise<MeResponse> {
  return request<MeResponse>("/api/v1/auth/me", {
    method: "GET",
    headers: authHeaders(role),
  });
}

export async function registerDocument(
  body: DocumentRegistrationRequest,
  role?: UserRole
): Promise<DocumentResponse> {
  return request<DocumentResponse>("/api/v1/documents", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

export async function uploadDocumentFile(
  documentId: string,
  file: File,
  role?: UserRole
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/upload`,
    {
      method: "POST",
      headers: authHeaders(role),
      body: form,
    }
  );
}

export async function listDocuments(
  role?: UserRole
): Promise<DocumentInventoryResponse> {
  return request<DocumentInventoryResponse>("/api/v1/documents", {
    method: "GET",
    headers: authHeaders(role),
  });
}

export async function getDocument(
  documentId: string,
  role?: UserRole
): Promise<DocumentSnapshot> {
  return request<DocumentSnapshot>(
    `/api/v1/documents/${encodeURIComponent(documentId)}`,
    {
      method: "GET",
      headers: authHeaders(role),
    }
  );
}

export async function getDocumentAgents(
  documentId: string,
  role?: UserRole
): Promise<AgentDeepDiveResponse> {
  return request<AgentDeepDiveResponse>(
    `/api/v1/documents/${encodeURIComponent(documentId)}/agents`,
    {
      method: "GET",
      headers: authHeaders(role),
    }
  );
}

/**
 * Subscribe to SSE inventory/bus updates. Uses fetch so Bearer works.
 * Returns an abort function.
 */
export function subscribeEvents(
  onEvent: (eventName: string, data: unknown) => void,
  role?: UserRole
): () => void {
  const controller = new AbortController();
  const headers = new Headers(authHeaders(role));
  void (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/events/stream`, {
        method: "GET",
        headers,
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        onEvent("error", { status: response.status });
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const lines = chunk.split("\n");
          let eventName = "message";
          let dataLine = "";
          for (const line of lines) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            if (line.startsWith("data:")) dataLine = line.slice(5).trim();
          }
          if (!dataLine) continue;
          try {
            onEvent(eventName, JSON.parse(dataLine));
          } catch {
            onEvent(eventName, dataLine);
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onEvent("error", { message: String(err) });
      }
    }
  })();
  return () => controller.abort();
}

export async function listAuditEntries(
  documentId: string,
  role?: UserRole
): Promise<AuditChainResponse> {
  const query = new URLSearchParams({ document_id: documentId });
  return request<AuditChainResponse>(`/api/v1/audit/entries?${query.toString()}`, {
    method: "GET",
    headers: authHeaders(role),
  });
}

export async function verifyAudit(
  documentId: string,
  role?: UserRole
): Promise<AuditVerifyResponse> {
  const query = new URLSearchParams({ document_id: documentId });
  return request<AuditVerifyResponse>(`/api/v1/audit/verify?${query.toString()}`, {
    method: "GET",
    headers: authHeaders(role),
  });
}

export async function classifyDocument(
  body: ClassificationRequest,
  role?: UserRole
): Promise<ClassificationResponse> {
  return request<ClassificationResponse>("/api/v1/classify", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

export async function registerAndClassify(
  filename: string,
  content: string,
  role?: UserRole
): Promise<{ document: DocumentResponse; classification: ClassificationResponse }> {
  const document = await registerDocument({ filename }, role);
  const classification = await classifyDocument(
    { document_id: document.id, content },
    role
  );
  return { document, classification };
}

/** Register, upload file, classify using extracted text (fallback to paste). */
export async function registerUploadAndClassify(
  file: File,
  pasteFallback: string,
  role?: UserRole
): Promise<{
  document: DocumentResponse;
  upload: UploadResponse;
  classification: ClassificationResponse;
}> {
  const document = await registerDocument({ filename: file.name }, role);
  const upload = await uploadDocumentFile(document.id, file, role);
  const content =
    upload.extracted_text && upload.extracted_text_chars > 0
      ? upload.extracted_text
      : pasteFallback;
  const classification = await classifyDocument(
    { document_id: document.id, content },
    role
  );
  return { document, upload, classification };
}

export async function overrideClassification(
  body: ManualOverrideRequest,
  role?: UserRole
): Promise<ManualOverrideResponse> {
  return request<ManualOverrideResponse>("/api/v1/manual-overrides", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

export async function createPolicyRule(
  body: PolicyRuleRequest,
  role?: UserRole
): Promise<PolicyRuleResponse> {
  return request<PolicyRuleResponse>("/api/v1/policy-rules", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

export async function testPolicyRule(
  body: PolicyRuleRequest,
  role?: UserRole
): Promise<PolicyRuleTestResponse> {
  return request<PolicyRuleTestResponse>("/api/v1/policy-rules/test", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

export async function runAssessment(
  body: AssessmentRequest,
  role?: UserRole
): Promise<AssessmentResponse> {
  return request<AssessmentResponse>("/api/v1/assessments", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

/**
 * POST /api/v1/shred — destroy wrapped DEKs for one document (FR-8).
 * Irreversible. confirmed must be true.
 */
export async function shredDocument(
  body: ShredRequest,
  role?: UserRole
): Promise<ShredResponse> {
  return request<ShredResponse>("/api/v1/shred", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}

/**
 * GET /api/v1/documents/{id}/summary — download CSV or PDF (FR-16).
 * Triggers a browser download; does not return parsed JSON.
 */
export async function downloadDocumentSummary(
  documentId: string,
  format: "csv" | "pdf",
  role?: UserRole
): Promise<void> {
  const url = `${API_BASE_URL}/api/v1/documents/${encodeURIComponent(
    documentId
  )}/summary?format=${format}`;
  const response = await fetch(url, { headers: authHeaders(role) });
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(response.status, response.statusText, body);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `qaegis-summary-${documentId}.${format}`;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

/**
 * POST /api/v1/migration-schedule/rank — QAOA + baselines (FR-9).
 * Role: security_admin.
 */
export async function rankMigration(
  body: MigrationRankRequest,
  role?: UserRole
): Promise<MigrationRankResponse> {
  return request<MigrationRankResponse>("/api/v1/migration-schedule/rank", {
    method: "POST",
    headers: jsonHeaders(role),
    body: JSON.stringify(body),
  });
}
