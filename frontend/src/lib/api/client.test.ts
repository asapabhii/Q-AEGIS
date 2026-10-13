/**
 * Smoke tests for the Q-AEGIS API client.
 *
 * These verify that the client builds the correct request shape — URL, method,
 * headers (including the X-Q-AEGIS-Actor-Role header), and body — for both
 * the register and classify calls. They mock fetch so no backend is needed.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  checkHealth,
  registerDocument,
  listDocuments,
  getDocument,
  listAuditEntries,
  verifyAudit,
  classifyDocument,
  overrideClassification,
  createPolicyRule,
  testPolicyRule,
  shredDocument,
  rankMigration,
  downloadDocumentSummary,
  getGraphStatus,
  seedGraph,
  getDocumentAttackPaths,
  ingestRagDocument,
  askRag,
  login,
  getDocumentAgents,
  getMe,
  uploadDocumentFile,
  subscribeEvents,
  listCheckpoints,
  issueCheckpoint,
  verifyCheckpoint,
  getSigningKey,
  getInclusionProof,
  getConsistencyProof,
  registerAndClassify,
  registerUploadAndClassify,
  runAssessment,
  submitRiskScore,
  submitTrustScore,
  selectCryptoProfile,
  evaluatePolicyDecision,
  ApiError,
} from "./client";
import type {
  AssessmentRequest,
  CreateCheckpointRequest,
  PolicyAction,
  RiskScoreRequest,
  TrustScoreRequest,
} from "./types";

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
    headers: new Headers(),
    redirected: false,
    type: "basic",
    url: "",
    clone: () => jsonResponse(body, status) as Response,
    body: null,
    bodyUsed: false,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    bytes: () => Promise.resolve(new Uint8Array()),
    formData: () => Promise.resolve(new FormData()),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response;
}

beforeEach(() => {
  mockFetch.mockReset();
  if (typeof window !== "undefined") {
    window.localStorage.clear();
  }
});

function headerValue(
  headers: HeadersInit | undefined,
  name: string
): string | null {
  if (!headers) return null;
  return new Headers(headers).get(name);
}

// ---------------------------------------------------------------------------
// checkHealth
// ---------------------------------------------------------------------------

describe("checkHealth", () => {
  it("sends GET to /api/v1/health with no role header", async () => {
    const body = { status: "ok", service: "q-aegis-shield-backend", version: "0.1.0" };
    mockFetch.mockResolvedValueOnce(jsonResponse(body));

    const result = await checkHealth();

    expect(result).toEqual(body);
    expect(mockFetch).toHaveBeenCalledOnce();

    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit | undefined];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/health");
    // Health is unauthenticated — no role header
    expect(headerValue(options?.headers, "X-Q-AEGIS-Actor-Role")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// registerDocument
// ---------------------------------------------------------------------------

describe("registerDocument", () => {
  it("sends POST to /api/v1/documents with the role header and filename", async () => {
    const responseBody = {
      id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      filename: "report.pdf",
      storage_path: null,
      current_status: "registered",
      uploaded_by: "11111111-2222-3333-4444-555555555555",
      uploaded_at: "2026-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody, 201));

    const result = await registerDocument(
      { filename: "report.pdf" },
      "data_owner"
    );

    expect(result).toEqual(responseBody);
    expect(mockFetch).toHaveBeenCalledOnce();

    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/documents");
    expect(options.method).toBe("POST");

    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe("data_owner");
    expect(headerValue(options.headers, "Content-Type")).toBe("application/json");

    const body = JSON.parse(options.body as string);
    expect(body).toEqual({ filename: "report.pdf" });
  });

  it("throws ApiError on 401 when role header is missing", async () => {
    const errorBody = {
      detail: "Missing X-Q-AEGIS-Actor-Role header; caller identity is required.",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(errorBody, 401));

    await expect(
      registerDocument({ filename: "test.pdf" }, "data_owner")
    ).rejects.toThrow(/401/);
  });
});

// ---------------------------------------------------------------------------
// classifyDocument
// ---------------------------------------------------------------------------

describe("classifyDocument", () => {
  it("sends POST to /api/v1/classify with the role header, document_id, and content", async () => {
    const responseBody = {
      document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      sensitivity_label: "CONFIDENTIAL",
      confidence: 0.85,
      model_version: "stub-keyword-rules-0.1.0",
      is_defaulted: false,
      base_label: "CONFIDENTIAL",
      confidence_threshold: 0.6,
      matched_keywords: ["confidential"],
      rationale: "Keyword rules suggested CONFIDENTIAL.",
      classified_at: "2026-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const result = await classifyDocument(
      {
        document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        content: "This document contains confidential financial data.",
      },
      "data_owner"
    );

    expect(result).toEqual(responseBody);
    expect(mockFetch).toHaveBeenCalledOnce();

    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/classify");
    expect(options.method).toBe("POST");

    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe("data_owner");
    expect(headerValue(options.headers, "Content-Type")).toBe("application/json");

    const body = JSON.parse(options.body as string);
    expect(body).toEqual({
      document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      content: "This document contains confidential financial data.",
    });
  });

  it("throws ApiError with 404 when document_id is not registered", async () => {
    const errorBody = {
      detail:
        "No document registered with id 00000000-0000-0000-0000-000000000000. " +
        "Register it first via POST /api/v1/documents.",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(errorBody, 404));

    await expect(
      classifyDocument(
        {
          document_id: "00000000-0000-0000-0000-000000000000",
          content: "test",
        },
        "data_owner"
      )
    ).rejects.toThrow(ApiError);
  });

  it("throws ApiError on 503 when seed data is missing", async () => {
    const errorBody = {
      detail:
        "No user exists with role 'data_owner', so this request cannot be attributed " +
        "to an actor. Seed the development accounts with `python -m app.db.seed`.",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(errorBody, 503));

    await expect(
      classifyDocument(
        {
          document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
          content: "test",
        },
        "data_owner"
      )
    ).rejects.toThrow(/503/);
  });

  it("formats 422 validation errors with readable msg rather than [object Object]", async () => {
    const validationErrorBody = {
      detail: [
        {
          type: "string_too_long",
          loc: ["body", "content"],
          msg: "String should have at most 1000000 characters",
          input: "oversized content",
        },
      ],
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(validationErrorBody, 422));

    let caughtError: unknown;
    try {
      await classifyDocument(
        {
          document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
          content: "oversized content",
        },
        "data_owner"
      );
    } catch (e) {
      caughtError = e;
    }
    expect(caughtError).toBeInstanceOf(ApiError);
    const apiErr = caughtError as ApiError;
    expect(apiErr.status).toBe(422);
    expect(apiErr.message).toContain(
      "String should have at most 1000000 characters"
    );
    expect(apiErr.message).not.toContain("[object Object]");
  });
});

// ---------------------------------------------------------------------------
// overrideClassification
// ---------------------------------------------------------------------------

describe("overrideClassification", () => {
  it("sends POST to /api/v1/manual-overrides without original_label", async () => {
    const responseBody = {
      id: "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
      document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      overridden_by: "11111111-2222-3333-4444-555555555555",
      original_label: "RESTRICTED",
      new_label: "INTERNAL",
      justification: "Reviewed with the data owner and reclassified.",
      overridden_at: "2026-01-01T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody, 201));

    const result = await overrideClassification(
      {
        document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        new_label: "INTERNAL",
        justification: "Reviewed with the data owner and reclassified.",
      },
      "security_analyst"
    );

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/manual-overrides");
    expect(options.method).toBe("POST");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe("security_analyst");
    expect(JSON.parse(options.body as string)).toEqual({
      document_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      new_label: "INTERNAL",
      justification: "Reviewed with the data owner and reclassified.",
    });
  });
});

describe("listDocuments", () => {
  it("sends GET to /api/v1/documents with the role header and no body", async () => {
    const responseBody = { count: 0, documents: [] };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const result = await listDocuments("security_admin");

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/documents");
    expect(options.method).toBe("GET");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "security_admin"
    );
    expect(options.body).toBeUndefined();
  });
});

describe("getDocument", () => {
  it("sends GET to /api/v1/documents/{id} with the role header", async () => {
    const id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    const responseBody = {
      id,
      filename: "report.pdf",
      storage_path: null,
      current_status: "registered",
      uploaded_by: "11111111-2222-3333-4444-555555555555",
      uploaded_at: "2026-09-10T00:00:00Z",
      sensitivity_label: null,
      label_source: null,
      override_id: null,
      classification_id: null,
      risk_score_id: null,
      risk_value: null,
      risk_computed_at: null,
      trust_score_id: null,
      trust_score: null,
      trust_computed_at: null,
      policy_decision_id: null,
      final_decision: null,
      decided_at: null,
      crypto_profile_id: null,
      profile_type: null,
      selected_at: null,
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const result = await getDocument(id, "auditor");

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`http://127.0.0.1:8000/api/v1/documents/${id}`);
    expect(options.method).toBe("GET");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "auditor"
    );
  });
});

describe("listAuditEntries", () => {
  it("sends GET to /api/v1/audit/entries with document_id and the role header", async () => {
    const id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    const responseBody = { document_id: id, count: 0, entries: [] };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const result = await listAuditEntries(id, "auditor");

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      `http://127.0.0.1:8000/api/v1/audit/entries?document_id=${id}`
    );
    expect(options.method).toBe("GET");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "auditor"
    );
    expect(options.body).toBeUndefined();
  });
});

describe("verifyAudit", () => {
  it("sends GET to /api/v1/audit/verify with document_id and no end_index", async () => {
    const id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    const responseBody = {
      is_valid: true,
      computed_root: "aa",
      stored_root: "aa",
      end_index: 0,
      entry_count: 1,
      document_id: id,
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const result = await verifyAudit(id, "auditor");

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      `http://127.0.0.1:8000/api/v1/audit/verify?document_id=${id}`
    );
    expect(url).not.toContain("end_index");
    expect(options.method).toBe("GET");
    expect(
      headerValue(options.headers, "X-Q-AEGIS-Actor-Role")
    ).toBe("auditor");
    expect(options.body).toBeUndefined();
  });
});

describe("createPolicyRule", () => {
  it("sends POST to /api/v1/policy-rules", async () => {
    const responseBody = {
      id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      rule_name: "Deny restricted",
      condition_expr: {
        field: "sensitivity_label",
        op: "eq",
        value: "RESTRICTED",
      },
      action: "deny",
      priority: 10,
      active: true,
      created_at: "2026-09-10T12:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody, 201));

    const body = {
      rule_name: "Deny restricted",
      condition_expr: {
        field: "sensitivity_label",
        op: "eq",
        value: "RESTRICTED",
      },
      action: "deny" as const,
      priority: 10,
    };
    const result = await createPolicyRule(body, "compliance_officer");

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/policy-rules");
    expect(options.method).toBe("POST");
    expect(
      headerValue(options.headers, "X-Q-AEGIS-Actor-Role")
    ).toBe("compliance_officer");
    expect(JSON.parse(options.body as string)).toEqual(body);
  });
});

describe("testPolicyRule", () => {
  it("sends POST to /api/v1/policy-rules/test without a window", async () => {
    const responseBody = {
      rule_name: "Deny restricted",
      action: "deny",
      priority: 10,
      condition_expr: { field: "sensitivity_label", op: "eq", value: "RESTRICTED" },
      window: 20,
      considered: 0,
      skipped: 0,
      replays: [],
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const body = {
      rule_name: "Deny restricted",
      condition_expr: { field: "sensitivity_label", op: "eq", value: "RESTRICTED" },
      action: "deny" as const,
      priority: 10,
    };
    const result = await testPolicyRule(body, "compliance_officer");

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/policy-rules/test");
    expect(options.method).toBe("POST");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "compliance_officer"
    );
    expect(JSON.parse(options.body as string)).toEqual(body);
  });
});

describe("shredDocument", () => {
  it("posts confirmed shred with the caller role", async () => {
    const responseBody = {
      document_id: "doc-1",
      ciphertext_count: 1,
      newly_destroyed: 1,
      already_shredded: false,
      irreversible: true,
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody));

    const result = await shredDocument(
      { document_id: "doc-1", confirmed: true },
      "compliance_officer"
    );

    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/shred");
    expect(options.method).toBe("POST");
    expect(
      headerValue(options.headers, "X-Q-AEGIS-Actor-Role")
    ).toBe("compliance_officer");
  });
});

describe("rankMigration", () => {
  it("posts budgeted ranking as security_admin", async () => {
    const responseBody = {
      schedule: [],
      primary: {
        method: "qaoa_numpy",
        selected_ids: [],
        total_score: 0,
        total_cost: 0,
      },
      baselines: [],
      constraint_snapshot: { budget: 2 },
      ranked_at: "2026-09-14T00:00:00Z",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(responseBody, 201));

    const result = await rankMigration(
      { budget: 2, window_days: 30, seed: 42 },
      "security_admin"
    );
    expect(result).toEqual(responseBody);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/migration-schedule/rank");
    expect(options.method).toBe("POST");
  });
});

describe("downloadDocumentSummary", () => {
  it("fetches summary CSV and triggers a download", async () => {
    const click = vi.fn();
    const createElement = vi.spyOn(document, "createElement");
    createElement.mockImplementation(((tag: string) => {
      if (tag === "a") {
        return { href: "", download: "", click } as unknown as HTMLAnchorElement;
      }
      return document.createElement(tag);
    }) as typeof document.createElement);

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      writable: true,
      value: vi.fn(() => "blob:summary"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });

    mockFetch.mockResolvedValueOnce({
      ...jsonResponse({}),
      ok: true,
      status: 200,
      blob: () => Promise.resolve(new Blob(["field,value"])),
      headers: new Headers({ "content-type": "text/csv" }),
    } as Response);

    await downloadDocumentSummary("doc-1", "csv", "data_owner");

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/documents/doc-1/summary?format=csv");
    expect(
      headerValue(options.headers, "X-Q-AEGIS-Actor-Role")
    ).toBe("data_owner");
    expect(click).toHaveBeenCalledOnce();
    createElement.mockRestore();
  });
});

describe("graph and rag clients", () => {
  it("reads graph status", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ configured: true }));
    await expect(getGraphStatus()).resolves.toEqual({ configured: true });
  });

  it("seeds the graph and loads document paths", async () => {
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(
          { nodes_upserted: 5, relationships_upserted: 6, demo: true },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({ document_id: "doc-1", paths: [], note: null })
      );
    await seedGraph({ document_id: "doc-1" }, "security_admin");
    await getDocumentAttackPaths("doc-1", "security_admin");
    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/v1/graph/seed"
    );
    expect(String(mockFetch.mock.calls[1][0])).toContain(
      "/api/v1/graph/documents/doc-1/paths"
    );
  });

  it("ingests and asks RAG questions", async () => {
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse(
          {
            document_id: "doc-1",
            chunks_written: 2,
            embedding_model: "stub-hash-v1",
          },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          question: "status?",
          answer: "ok",
          verified: true,
          plan: "plan",
          citations: [],
          embedding_model: "stub-hash-v1",
          refusal_reason: null,
        })
      );
    await ingestRagDocument("doc-1", "security_admin");
    await askRag({ question: "status?", document_id: "doc-1" }, "auditor");
    expect(String(mockFetch.mock.calls[0][0])).toContain(
      "/api/v1/rag/ingest/doc-1"
    );
    expect(mockFetch.mock.calls[1][0]).toBe(
      "http://127.0.0.1:8000/api/v1/rag/ask"
    );
  });
});

describe("login", () => {
  it("posts credentials and stores the session token", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        access_token: "jwt-token",
        token_type: "bearer",
        user_id: "u1",
        email: "security_admin@dev.qaegis.local",
        role: "security_admin",
        name: "Admin",
      })
    );
    const result = await login({
      email: "security_admin@dev.qaegis.local",
      password: "local-dev-only-password",
    });
    expect(result.access_token).toBe("jwt-token");
    expect(window.localStorage.getItem("qaegis.access_token")).toBe("jwt-token");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/auth/login");
    expect(options.method).toBe("POST");
  });
});

describe("getDocumentAgents", () => {
  it("gets agent deep-dive with the role header", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        document_id: "doc-1",
        risk_score_id: null,
        assessed_at: null,
        agents: [],
        missing_agents: ["security"],
        note: "none yet",
      })
    );
    await getDocumentAgents("doc-1", "security_admin");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/documents/doc-1/agents");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "security_admin"
    );
  });
});

// ---------------------------------------------------------------------------
// Streaming/download helpers
// ---------------------------------------------------------------------------

/** Flush the microtask + macrotask queues so a fire-and-forget async loop drains. */
async function tick(times = 6): Promise<void> {
  for (let i = 0; i < times; i += 1) {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

/** Fake SSE Response whose body reader yields the given raw chunks then ends. */
function sseResponse(chunks: string[], ok = true, status = 200): Response {
  const encoder = new TextEncoder();
  let i = 0;
  return {
    ok,
    status,
    body: ok
      ? {
          getReader() {
            return {
              read: async () =>
                i < chunks.length
                  ? { done: false, value: encoder.encode(chunks[i++]) }
                  : { done: true, value: undefined },
            };
          },
        }
      : null,
  } as unknown as Response;
}


describe("getMe", () => {
  it("sends GET to /api/v1/auth/me with the role header", async () => {
    const body = {
      id: "u1",
      email: "auditor@dev.qaegis.local",
      role: "auditor",
      name: "Auditor",
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(body));

    const result = await getMe("auditor");

    expect(result).toEqual(body);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/auth/me");
    expect(options.method).toBe("GET");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe("auditor");
    expect(options.body).toBeUndefined();
  });
});

describe("uploadDocumentFile", () => {
  it("posts multipart FormData without forcing a JSON Content-Type", async () => {
    const body = {
      document_id: "doc-1",
      filename: "report.txt",
      extracted_text: "hello world",
      extracted_text_chars: 11,
      stored: true,
    };
    mockFetch.mockResolvedValueOnce(jsonResponse(body, 201));

    const file = new File(["hello world"], "report.txt", { type: "text/plain" });
    const result = await uploadDocumentFile("doc-1", file, "data_owner");

    expect(result).toEqual(body);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/documents/doc-1/upload");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    // The browser must set the multipart boundary — the client must NOT.
    expect(headerValue(options.headers, "Content-Type")).toBeNull();
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe("data_owner");
  });
});


describe("subscribeEvents", () => {
  it("parses SSE frames and forwards named events, ignoring keepalives", async () => {
    mockFetch.mockResolvedValueOnce(
      sseResponse([
        ":\n\n", // keepalive comment — no data line, must be skipped
        'event: ready\ndata: {"ok":true}\n\n',
        "data: not-json\n\n", // non-JSON payload falls back to the raw string
      ])
    );

    const onEvent = vi.fn();
    const unsubscribe = subscribeEvents(onEvent, "security_admin");
    await tick();

    expect(typeof unsubscribe).toBe("function");
    expect(onEvent).toHaveBeenCalledWith("ready", { ok: true });
    expect(onEvent).toHaveBeenCalledWith("message", "not-json");
    // The keepalive frame produced no callback.
    expect(onEvent).toHaveBeenCalledTimes(2);

    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/events/stream");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "security_admin"
    );
    unsubscribe();
  });

  it("reports an error event when the stream response is not ok", async () => {
    mockFetch.mockResolvedValueOnce(sseResponse([], false, 401));

    const onEvent = vi.fn();
    subscribeEvents(onEvent, "security_admin");
    await tick();

    expect(onEvent).toHaveBeenCalledWith("error", { status: 401 });
  });
});


describe("audit checkpoints and proofs", () => {
  it("lists checkpoints for a specific document chain", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse([]));
    await listCheckpoints("doc-1", "auditor");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://127.0.0.1:8000/api/v1/audit/checkpoints?document_id=doc-1"
    );
    expect(options.method).toBe("GET");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe("auditor");
  });

  it("lists system-chain checkpoints with no query when documentId is omitted", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse([]));
    await listCheckpoints(null, "auditor");
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/audit/checkpoints");
    expect(url).not.toContain("?");
  });

  it("issues a Signed Tree Head over a document chain", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "ck-1" }, 201));
    const body = { document_id: "doc-1" } as unknown as CreateCheckpointRequest;
    await issueCheckpoint(body, "auditor");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/audit/checkpoint");
    expect(options.method).toBe("POST");
    expect(headerValue(options.headers, "Content-Type")).toBe("application/json");
    expect(JSON.parse(options.body as string)).toEqual({ document_id: "doc-1" });
  });

  it("verifies a stored checkpoint by id", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ is_valid: true }));
    await verifyCheckpoint("ck-1", "auditor");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://127.0.0.1:8000/api/v1/audit/checkpoint/ck-1/verify"
    );
    expect(options.method).toBe("GET");
  });

  it("reads the active signing key", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ public_key_hex: "ab" }));
    await getSigningKey("auditor");
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/audit/signing-key");
  });

  it("builds an inclusion proof query with all optional params", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ audit_path: [] }));
    await getInclusionProof(3, "doc-1", 10, "auditor");
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/audit/inclusion-proof?");
    expect(url).toContain("leaf_index=3");
    expect(url).toContain("document_id=doc-1");
    expect(url).toContain("tree_size=10");
  });

  it("omits inclusion proof params that are not supplied", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ audit_path: [] }));
    await getInclusionProof(0);
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://127.0.0.1:8000/api/v1/audit/inclusion-proof?leaf_index=0"
    );
  });

  it("builds a consistency proof query with all optional params", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ proof: [] }));
    await getConsistencyProof(2, "doc-1", 8, "auditor");
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/audit/consistency-proof?");
    expect(url).toContain("old_size=2");
    expect(url).toContain("document_id=doc-1");
    expect(url).toContain("new_size=8");
  });
});


describe("registerAndClassify", () => {
  it("registers then classifies, threading the new id into the classify body", async () => {
    mockFetch
      .mockResolvedValueOnce(
        jsonResponse({ id: "new-doc", filename: "notes.txt" }, 201)
      )
      .mockResolvedValueOnce(
        jsonResponse({
          document_id: "new-doc",
          sensitivity_label: "INTERNAL",
          confidence: 0.9,
        })
      );

    const { document, classification } = await registerAndClassify(
      "notes.txt",
      "just some ordinary text",
      "data_owner"
    );

    expect(document.id).toBe("new-doc");
    expect(classification.document_id).toBe("new-doc");

    expect(mockFetch.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8000/api/v1/documents"
    );
    expect(mockFetch.mock.calls[1][0]).toBe(
      "http://127.0.0.1:8000/api/v1/classify"
    );
    const classifyBody = JSON.parse(
      (mockFetch.mock.calls[1][1] as RequestInit).body as string
    );
    expect(classifyBody).toEqual({
      document_id: "new-doc",
      content: "just some ordinary text",
    });
  });
});


describe("registerUploadAndClassify", () => {
  it("classifies extracted text when the upload returns some", async () => {
    mockFetch
      .mockResolvedValueOnce(jsonResponse({ id: "up-doc", filename: "a.txt" }, 201))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            document_id: "up-doc",
            filename: "a.txt",
            extracted_text: "extracted body text",
            extracted_text_chars: 19,
            stored: true,
          },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({ document_id: "up-doc", sensitivity_label: "PUBLIC" })
      );

    const file = new File(["extracted body text"], "a.txt", {
      type: "text/plain",
    });
    const { classification } = await registerUploadAndClassify(
      file,
      "fallback paste",
      "data_owner"
    );

    expect(classification.document_id).toBe("up-doc");
    expect(mockFetch).toHaveBeenCalledTimes(3);
    const classifyBody = JSON.parse(
      (mockFetch.mock.calls[2][1] as RequestInit).body as string
    );
    // Extracted text won over the paste fallback.
    expect(classifyBody.content).toBe("extracted body text");
  });

  it("falls back to the pasted text when extraction is empty", async () => {
    mockFetch
      .mockResolvedValueOnce(jsonResponse({ id: "up-doc2", filename: "b.pdf" }, 201))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            document_id: "up-doc2",
            filename: "b.pdf",
            extracted_text: "",
            extracted_text_chars: 0,
            stored: true,
          },
          201
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({ document_id: "up-doc2", sensitivity_label: "PUBLIC" })
      );

    const file = new File(["scanned image"], "b.pdf", {
      type: "application/pdf",
    });
    await registerUploadAndClassify(file, "typed fallback", "data_owner");

    const classifyBody = JSON.parse(
      (mockFetch.mock.calls[2][1] as RequestInit).body as string
    );
    expect(classifyBody.content).toBe("typed fallback");
  });
});


describe("pipeline stage clients", () => {
  it("runs an assessment via POST /api/v1/assessments", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ risk_score_id: "rs-1" }, 201));
    const body = { document_id: "doc-1" } as unknown as AssessmentRequest;
    await runAssessment(body, "security_admin");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/assessments");
    expect(options.method).toBe("POST");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "security_admin"
    );
  });

  it("submits a risk score via POST /api/v1/risk-scores", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "rs-1" }, 201));
    const body = { document_id: "doc-1" } as unknown as RiskScoreRequest;
    await submitRiskScore(body, "security_admin");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/risk-scores");
    expect(options.method).toBe("POST");
  });

  it("submits a trust score via POST /api/v1/trust-scores", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "ts-1" }, 201));
    const body = { risk_score_id: "rs-1" } as unknown as TrustScoreRequest;
    await submitTrustScore(body, "security_admin");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/trust-scores");
    expect(options.method).toBe("POST");
  });

  it("selects a crypto profile by trust score id", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "cp-1" }, 201));
    await selectCryptoProfile("ts-1", "security_admin");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/crypto-profiles");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      trust_score_id: "ts-1",
    });
  });

  it("evaluates a policy decision without an AI recommendation", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ final_decision: "allow" }, 201));
    await evaluatePolicyDecision("ts-1", "security_admin");
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/policy-decisions");
    expect(JSON.parse(options.body as string)).toEqual({
      trust_score_id: "ts-1",
    });
  });

  it("threads an explicit AI recommendation into the policy body", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ final_decision: "deny" }, 201));
    await evaluatePolicyDecision(
      "ts-1",
      "security_admin",
      "deny" as PolicyAction
    );
    const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({
      trust_score_id: "ts-1",
      ai_recommendation: "deny",
    });
  });
});
