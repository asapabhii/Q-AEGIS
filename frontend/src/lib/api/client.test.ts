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
  classifyDocument,
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
});

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
    const headers = options?.headers as Record<string, string> | undefined;
    expect(headers?.["X-Q-AEGIS-Actor-Role"]).toBeUndefined();
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

    const headers = options.headers as Record<string, string>;
    expect(headers["X-Q-AEGIS-Actor-Role"]).toBe("data_owner");
    expect(headers["Content-Type"]).toBe("application/json");

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

    const headers = options.headers as Record<string, string>;
    expect(headers["X-Q-AEGIS-Actor-Role"]).toBe("data_owner");
    expect(headers["Content-Type"]).toBe("application/json");

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
