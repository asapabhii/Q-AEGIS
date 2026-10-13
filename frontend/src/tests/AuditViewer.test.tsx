import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AuditViewer } from "@/app/audit/[document_id]/page";
import { listAuditEntries, verifyAudit } from "@/lib/api/client";
import { RoleProvider } from "@/lib/context/RoleContext";

// Mock the API client
vi.mock("@/lib/api/client", () => {
  return {
    listAuditEntries: vi.fn(),
    verifyAudit: vi.fn(),
    ApiError: class ApiError extends Error {},
  };
});

// Mock D3 component to avoid SVG rendering issues in jsdom
vi.mock("@/components/ui/D3AuditChain", () => {
  return {
    __esModule: true,
    default: () => <div data-testid="d3-audit-chain">Mock D3 Chain</div>,
  };
});

// Mock gsap reveal hook
vi.mock("@/lib/hooks/useGsapReveal", () => {
  return {
    useGsapReveal: () => ({ current: null }),
  };
});

describe("AuditViewer", () => {
  const documentId = "test-doc-123";

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(listAuditEntries).mockResolvedValue({
      document_id: "test-doc-123",
      count: 0,
      entries: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows loading state initially", async () => {
    const documentId = "test-doc-123";
    vi.mocked(listAuditEntries).mockReturnValue(new Promise(() => {}));
    const { container } = render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);
    // While the entries request is in flight the page renders skeleton
    // placeholders (Skeleton -> .skeleton-pulse) in place of the chain UI.
    expect(container.querySelector(".skeleton-pulse")).toBeInTheDocument();
  });

  it("renders audit chain after loading", async () => {
    const mockChain = [
      {
        id: "mock-1",
        index: 0,
        event_type: "document_registered",
        created_at: "2026-09-09T12:00:00Z",
        actor_id: "user1",
        payload_hash: "hash1",
        prev_hash: null,
        merkle_root_at_time: "root1",
        payload: { filename: "test.pdf" },
      },
      {
        id: "mock-2",
        index: 1,
        event_type: "classification_completed",
        created_at: "2026-09-09T12:05:00Z",
        actor_id: "system",
        payload_hash: "hash2",
        prev_hash: "hash1",
        merkle_root_at_time: "root2",
        payload: { sensitivity_label: "RESTRICTED" },
      },
    ];

    vi.mocked(listAuditEntries).mockResolvedValue({ 
      document_id: documentId,
      count: mockChain.length,
      entries: mockChain 
    });

    render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);

    await waitFor(() => {
      expect(screen.queryByText(/Loading audit trail/i)).not.toBeInTheDocument();
    });

    // Check header
    expect(screen.getByText(/Forensic inspection for document/i)).toBeInTheDocument();
    expect(screen.getByText(documentId)).toBeInTheDocument();

    // Check D3 mock is rendered
    expect(screen.getByTestId("d3-audit-chain")).toBeInTheDocument();
  });

  it("handles chain integrity verification", async () => {
    const mockChain = [
      {
        id: "mock-1",
        index: 0,
        event_type: "document_registered",
        created_at: "2026-09-09T12:00:00Z",
        actor_id: "user1",
        payload_hash: "hash1",
        prev_hash: null,
        merkle_root_at_time: "root1",
        payload: { filename: "test.pdf" },
      },
      {
        id: "mock-2",
        index: 1,
        event_type: "classification_completed",
        created_at: "2026-09-09T12:05:00Z",
        actor_id: "system",
        payload_hash: "hash2",
        prev_hash: "hash1",
        merkle_root_at_time: "root2",
        payload: { sensitivity_label: "RESTRICTED" },
      },
    ];

    vi.mocked(listAuditEntries).mockResolvedValue({
      document_id: documentId,
      count: mockChain.length,
      entries: mockChain
    });

    vi.mocked(verifyAudit).mockResolvedValue({
      is_valid: true,
      computed_root: "abcd1234",
      stored_root: "abcd1234",
      end_index: mockChain.length - 1,
      entry_count: mockChain.length,
      document_id: documentId,
    });

    render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);

    await waitFor(() => {
      expect(screen.queryByText(/Loading audit trail/i)).not.toBeInTheDocument();
    });

    // Check that button is present
    const verifyButton = screen.getByRole("button", { name: /Verify Chain Integrity/i });
    expect(verifyButton).toBeInTheDocument();

    // Click to verify against the real backend endpoint (mocked here)
    fireEvent.click(verifyButton);

    expect(await screen.findByText("Verified", {}, { timeout: 3000 })).toBeInTheDocument();
    // The page threads the caller's real role (RoleProvider default is
    // security_admin, which ACCESS.audit permits) rather than remapping it.
    expect(vi.mocked(verifyAudit)).toHaveBeenCalledWith(documentId, "security_admin");
  });

  it("handles broken chain verification", async () => {
    const brokenChain = [
      {
        id: "mock-1",
        index: 0,
        event_type: "document_registered",
        created_at: "2026-09-09T12:00:00Z",
        actor_id: "user1",
        payload_hash: "hash1",
        prev_hash: null,
        merkle_root_at_time: "root1",
        payload: { filename: "test.pdf" },
      },
      {
        id: "mock-2",
        index: 1,
        event_type: "classification_completed",
        created_at: "2026-09-09T12:05:00Z",
        actor_id: "system",
        payload_hash: "hash2",
        prev_hash: "badhash", // Broken link
        merkle_root_at_time: "root2",
        payload: { sensitivity_label: "RESTRICTED" },
      },
    ];

    vi.mocked(listAuditEntries).mockResolvedValue({
      document_id: documentId,
      count: brokenChain.length,
      entries: brokenChain
    });

    vi.mocked(verifyAudit).mockResolvedValue({
      is_valid: false,
      computed_root: "deadbeef",
      stored_root: "abcd1234",
      end_index: brokenChain.length - 1,
      entry_count: brokenChain.length,
      document_id: documentId,
    });

    render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);

    await waitFor(() => {
      expect(screen.queryByText(/Loading audit trail/i)).not.toBeInTheDocument();
    });

    const verifyButton = screen.getByRole("button", { name: /Verify Chain Integrity/i });
    fireEvent.click(verifyButton);

    expect(await screen.findByText("Compromised", {}, { timeout: 3000 })).toBeInTheDocument();
  });
});
