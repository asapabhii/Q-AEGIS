import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api/client", () => ({
  listAuditEntries: vi.fn(),
  verifyAudit: vi.fn(),
  ApiError: class MockApiError extends Error {
    status: number;
    constructor(status: number, message: string, body?: unknown) {
      super(message);
      this.status = status;
    }
  },
}));

import { listAuditEntries, verifyAudit, ApiError } from "@/lib/api/client";
import { AuditViewer } from "@/app/audit/[document_id]/page";
import { MOCK_AUDIT_LOG } from "@/lib/api/mock-data";
import { RoleProvider } from "@/lib/context/RoleContext";

const mockListAuditEntries = vi.mocked(listAuditEntries);
const mockVerifyAudit = vi.mocked(verifyAudit);

function createApiError(message: string): ApiError {
  return new ApiError(404, message, null) as unknown as ApiError;
}

const MOCK_CHAIN_RESPONSE = {
  document_id: "123e4567-e89b-12d3-a456-426614174001",
  count: MOCK_AUDIT_LOG.length,
  entries: MOCK_AUDIT_LOG,
};

describe("Audit Viewer (FR-15)", () => {
  beforeEach(() => {
    mockListAuditEntries.mockResolvedValue(MOCK_CHAIN_RESPONSE);
    mockVerifyAudit.mockResolvedValue({
      is_valid: true,
      computed_root: "abcd1234",
      stored_root: "abcd1234",
      end_index: MOCK_AUDIT_LOG.length - 1,
      entry_count: MOCK_AUDIT_LOG.length,
      document_id: "123e4567-e89b-12d3-a456-426614174001",
    });
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it("shows loading state while fetching", () => {
    mockListAuditEntries.mockReturnValue(new Promise(() => {}));
    const { container } = render(<RoleProvider><AuditViewer documentId="123e4567-e89b-12d3-a456-426614174001" /></RoleProvider>);
    // The in-flight state renders Skeleton placeholders (.skeleton-pulse)
    // rather than a text spinner.
    expect(container.querySelector(".skeleton-pulse")).toBeInTheDocument();
    cleanup();
  });

  it("renders the audit trail header and chain integrity section after load", async () => {
    render(<RoleProvider><AuditViewer documentId="123e4567-e89b-12d3-a456-426614174001" /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText(/Cryptographic Audit Viewer/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Chain Integrity Check/i)).toBeInTheDocument();
    expect(screen.getByText(/Cryptographic Audit Trail/i)).toBeInTheDocument();
    cleanup();
  });

  it("shows unverified status before the chain is verified", async () => {
    render(<RoleProvider><AuditViewer documentId="123e4567-e89b-12d3-a456-426614174001" /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText(/Unverified/i)).toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: /verify chain integrity/i }),
    ).toBeEnabled();
    cleanup();
  });

  it("verifies the chain after clicking the button", async () => {
    const user = userEvent.setup();
    render(<RoleProvider><AuditViewer documentId="123e4567-e89b-12d3-a456-426614174001" /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText(/Unverified/i)).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /verify chain integrity/i }),
    );
    // Wait for the chain to be verified
    expect(
      await screen.findByText(/Verified/i)
    ).toBeInTheDocument();
    cleanup();
  }, 10000);

  it("renders the D3 visual chain container when chain entries exist", async () => {
    render(<RoleProvider><AuditViewer documentId="123e4567-e89b-12d3-a456-426614174001" /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText(/CRYPTOGRAPHIC AUDIT TRAIL/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Merkle-root visualization/i)).toBeInTheDocument();
    cleanup();
  });

  it("displays error message on API failure", async () => {
    mockListAuditEntries.mockRejectedValue(createApiError("404 Not Found: Document not found"));
    render(<RoleProvider><AuditViewer documentId="nonexistent" /></RoleProvider>);
    await waitFor(() => {
      expect(screen.getByText("404 Not Found: Document not found")).toBeInTheDocument();
    });
    cleanup();
  });

  it("calls listAuditEntries with the correct document ID and role", async () => {
    render(<RoleProvider><AuditViewer documentId="123e4567-e89b-12d3-a456-426614174001" /></RoleProvider>);
    await waitFor(() => {
      expect(mockListAuditEntries).toHaveBeenCalledWith(
        "123e4567-e89b-12d3-a456-426614174001",
        "security_admin",
      );
    });
    cleanup();
  });
});
