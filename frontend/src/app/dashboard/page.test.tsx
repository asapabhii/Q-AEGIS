import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/client", () => ({
  listDocuments: vi.fn(),
  // The dashboard opens an SSE feed on mount; the mock returns a no-op
  // unsubscribe so the effect's cleanup path matches the real signature
  // (subscribeEvents(onEvent, role?) => () => void).
  subscribeEvents: vi.fn(() => () => {}),
  ApiError: class MockApiError extends Error {
    status: number;
    constructor(status: number, message: string, body?: unknown) {
      super(message);
      this.status = status;
    }
  },
}));

import { listDocuments, ApiError } from "@/lib/api/client";
import RiskDashboardPage from "@/app/dashboard/page";
import { RoleProvider } from "@/lib/context/RoleContext";

const mockListDocuments = vi.mocked(listDocuments);
const MockApiError = ApiError;

function createApiError(message: string): InstanceType<typeof MockApiError> {
  return new MockApiError(403, message, null);
}

const MOCK_SNAPSHOTS = {
  count: 4,
  documents: [
    {
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
    },
    {
      id: "123e4567-e89b-12d3-a456-426614174002",
      filename: "internal-memo.docx",
      storage_path: "/storage/internal-memo.docx",
      current_status: "classified" as const,
      uploaded_by: "user-002",
      uploaded_at: "2026-09-02T11:00:00Z",
      sensitivity_label: "INTERNAL" as const,
      label_source: "classification" as const,
      override_id: null,
      classification_id: "cls-002",
      risk_score_id: "rs-002",
      risk_value: "0.2",
      risk_computed_at: "2026-09-02T11:05:00Z",
      trust_score_id: "ts-002",
      trust_score: "0.3",
      trust_computed_at: "2026-09-02T11:06:00Z",
      policy_decision_id: "pd-002",
      final_decision: "allow" as const,
      decided_at: "2026-09-02T11:07:00Z",
      crypto_profile_id: "cp-002",
      profile_type: "aes256" as const,
      selected_at: "2026-09-02T11:08:00Z",
    },
  ],
};

describe("Risk Dashboard (FR-14)", () => {
  beforeEach(() => {
    mockListDocuments.mockResolvedValue(MOCK_SNAPSHOTS);
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockListDocuments.mockReturnValue(new Promise(() => {}));
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    expect(screen.getByText(/Loading security data/i)).toBeInTheDocument();
    cleanup();
  });

  it("renders three aggregate summary cards after load", async () => {
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText("Total Documents")).toBeInTheDocument();
    });
    expect(screen.getByText("Avg Risk Score")).toBeInTheDocument();
    expect(screen.getByText("Policy Overrides")).toBeInTheDocument();
    cleanup();
  });

  it("displays the correct document count", async () => {
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText("Total Documents")).toBeInTheDocument();
    });
    expect(screen.getByText("2")).toBeInTheDocument();
    cleanup();
  });

  it("renders the featured distribution section", async () => {
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText("Sensitivity Distribution")).toBeInTheDocument();
    });
    expect(screen.getByText(/Protection Profiles/)).toBeInTheDocument();
    cleanup();
  });

  it("renders the high-risk documents table", async () => {
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getAllByText("High-Risk Documents").length).toBeGreaterThan(0);
    });
    expect(screen.getByText(/Documents at or above risk threshold/)).toBeInTheDocument();
    cleanup();
  });

  it("displays error message on API failure", async () => {
    mockListDocuments.mockRejectedValue(createApiError("403 Forbidden: Access denied"));
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText("403 Forbidden: Access denied")).toBeInTheDocument();
    });
    cleanup();
  });

  it("calls listDocuments with security_admin role", async () => {
    render(<RoleProvider><RiskDashboardPage /></RoleProvider>);
    await waitFor(() => {
      expect(mockListDocuments).toHaveBeenCalledWith("security_admin");
    });
    cleanup();
  });
});

