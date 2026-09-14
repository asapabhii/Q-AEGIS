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
  login,
  getDocumentAgents,
  ApiError,
} from "./client";

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
      password: "SET_LOCALLY",
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

describe("shredDocument", () => {
  it("posts confirmed shred", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        document_id: "doc-1",
        ciphertext_count: 1,
        newly_destroyed: 1,
        already_shredded: false,
        irreversible: true,
      })
    );
    await shredDocument(
      { document_id: "doc-1", confirmed: true },
      "compliance_officer"
    );
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/shred");
    expect(headerValue(options.headers, "X-Q-AEGIS-Actor-Role")).toBe(
      "compliance_officer"
    );
  });
});
