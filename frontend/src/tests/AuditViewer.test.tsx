import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AuditViewer } from "@/app/audit/[document_id]/page";
import { listAuditEntries } from "@/lib/api/client";
import { RoleProvider } from "@/lib/context/RoleContext";

// Mock the API client
vi.mock("@/lib/api/client", () => {
  return {
    listAuditEntries: vi.fn(),
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
  });

  afterEach(() => {
    cleanup();
  });

  it("shows loading state initially", () => {
    // Return an unresolved promise to keep it in loading state
    vi.mocked(listAuditEntries).mockReturnValue(new Promise(() => {}));
    render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);
    expect(screen.getByText(/INITIALIZING FORENSIC DECRYPTION/i)).toBeInTheDocument();
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
      expect(screen.queryByText(/INITIALIZING FORENSIC DECRYPTION/i)).not.toBeInTheDocument();
    });

    // Check header
    expect(screen.getByText(/FORENSIC INSPECTION FOR DOCUMENT_ID/i)).toBeInTheDocument();
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

    render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);

    await waitFor(() => {
      expect(screen.queryByText(/INITIALIZING FORENSIC DECRYPTION/i)).not.toBeInTheDocument();
    });

    // Check that button is present
    const verifyButton = screen.getByRole("button", { name: /VERIFY CHAIN INTEGRITY/i });
    expect(verifyButton).toBeInTheDocument();

    // Click to verify
    fireEvent.click(verifyButton);
    
    // Status should say verifying
    expect(screen.getByText(/VERIFYING PROOFS.../i)).toBeInTheDocument();
    
    // Wait for validation to finish (1 second timer)
    await waitFor(() => {
      expect(screen.getByText(/SYS: VERIFIED/i)).toBeInTheDocument();
    }, { timeout: 1500 });
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

    render(<RoleProvider><AuditViewer documentId={documentId} /></RoleProvider>);

    await waitFor(() => {
      expect(screen.queryByText(/INITIALIZING FORENSIC DECRYPTION/i)).not.toBeInTheDocument();
    });

    const verifyButton = screen.getByRole("button", { name: /VERIFY CHAIN INTEGRITY/i });
    fireEvent.click(verifyButton);
    
    await waitFor(() => {
      expect(screen.getByText(/SYS: TAMPERED/i)).toBeInTheDocument();
    }, { timeout: 1500 });
  });
});
