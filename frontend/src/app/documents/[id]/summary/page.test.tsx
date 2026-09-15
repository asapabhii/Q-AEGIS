import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/client", () => ({
  getDocument: vi.fn(),
  ApiError: class MockApiError extends Error {
    status: number;
    constructor(status: number, message: string, body?: unknown) {
      super(message);
      this.status = status;
    }
  },
}));

import { getDocument, ApiError } from "@/lib/api/client";
import DocumentSummaryPage from "@/app/documents/[id]/summary/page";
import { RoleProvider } from "@/lib/context/RoleContext";

const mockGetDocument = vi.mocked(getDocument);

function createApiError(message: string): ApiError {
  return new ApiError(404, message, null) as unknown as ApiError;
}

const MOCK_SNAPSHOT = {
  id: "123e4567-e89b-12d3-a456-426614174001",
  filename: "quarterly-report.pdf",
  storage_path: "/storage/quarterly-report.pdf",
  current_status: "protected" as const,
  uploaded_by: "user-001",
  uploaded_at: "2026-09-01T10:00:00Z",
  sensitivity_label: "CONFIDENTIAL" as const,
  label_source: "classification" as const,
  override_id: null,
  classification_id: "cls-001",
  risk_score_id: "rs-001",
  risk_value: "0.8",
  risk_computed_at: "2026-09-01T10:05:00Z",
  trust_score_id: "ts-001",
  trust_score: "0.65",
  trust_computed_at: "2026-09-01T10:06:00Z",
  policy_decision_id: "pd-001",
  final_decision: "force_pqc" as const,
  decided_at: "2026-09-01T10:07:00Z",
  crypto_profile_id: "cp-001",
  profile_type: "post_quantum" as const,
  selected_at: "2026-09-01T10:08:00Z",
};

describe("Document Summary Report (FR-16)", () => {
  beforeEach(() => {
    mockGetDocument.mockResolvedValue(MOCK_SNAPSHOT);
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockGetDocument.mockReturnValue(new Promise(() => {}));
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    expect(screen.getByText(/FETCHING DOCUMENT SNAPSHOT/i)).toBeInTheDocument();
    cleanup();
  });

  it("renders the page title and export button after load", async () => {
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Document Summary Report/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /print/i })).toBeInTheDocument();
    cleanup();
  });

  it("renders classification and protection profile sections", async () => {
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /CLASSIFICATION/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: /PROTECTION PROFILE/i })).toBeInTheDocument();
    cleanup();
  });

  it("displays the correct classification label", async () => {
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText("CONFIDENTIAL")).toBeInTheDocument();
    });
    cleanup();
  });

  it("displays the correct protection profile", async () => {
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText("Full PQC")).toBeInTheDocument();
    });
    cleanup();
  });

  it("renders the chain reference section", async () => {
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText(/CHAIN REFERENCE/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/TRUST SCORE ID/i)).toBeInTheDocument();
    cleanup();
  });

  it("displays error message on API failure", async () => {
    mockGetDocument.mockRejectedValue(createApiError("404 Not Found: Document not found"));
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "nonexistent" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText("404 Not Found: Document not found")).toBeInTheDocument();
    });
    cleanup();
  });

  it("calls getDocument with the correct document ID and role", async () => {
    render(
      <RoleProvider><DocumentSummaryPage params={Promise.resolve({ id: "123e4567-e89b-12d3-a456-426614174001" })} /></RoleProvider>,
    );
    await waitFor(() => {
      expect(mockGetDocument).toHaveBeenCalledWith(
        "123e4567-e89b-12d3-a456-426614174001",
        "security_admin",
      );
    });
    cleanup();
  });
});
