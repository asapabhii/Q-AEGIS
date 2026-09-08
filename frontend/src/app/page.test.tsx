import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPage from "./page";
import {
  checkHealth,
  registerAndClassify,
  ApiError,
} from "@/lib/api/client";
import type {
  ClassificationResponse,
  DocumentResponse,
  HealthResponse,
} from "@/lib/api/types";

// Mock the API client module — we test the component here, not the client.
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    checkHealth: vi.fn(),
    registerAndClassify: vi.fn(),
  };
});

const mockCheckHealth = vi.mocked(checkHealth);
const mockRegisterAndClassify = vi.mocked(registerAndClassify);

const sampleDocument: DocumentResponse = {
  id: "doc-uuid-12345",
  filename: "quarterly-report.pdf",
  storage_path: null,
  current_status: "registered",
  uploaded_by: "user-uuid-99999",
  uploaded_at: "2026-09-05T12:00:00Z",
};

const sampleClassification: ClassificationResponse = {
  document_id: "doc-uuid-12345",
  sensitivity_label: "CONFIDENTIAL",
  confidence: 0.85,
  model_version: "stub-keyword-rules-0.1.0",
  is_defaulted: false,
  base_label: "CONFIDENTIAL",
  confidence_threshold: 0.6,
  matched_keywords: ["confidential"],
  rationale: "Keyword rules suggested CONFIDENTIAL.",
  classified_at: "2026-09-05T12:00:01Z",
};

const sampleHealth: HealthResponse = {
  status: "ok",
  service: "q-aegis-shield-backend",
  version: "0.1.0",
};

describe("DashboardPage workbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the returned document id, sensitivity badge, and confidence on happy path", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: sampleClassification,
    });

    render(<DashboardPage />);

    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    });
    await user.click(classifyButton);

    // Assert Step 1 document details
    expect(screen.getByText("Step 1 — Document Registered")).toBeDefined();
    expect(screen.getByText("doc-uuid-12345")).toBeDefined();

    // Assert Step 2 classification details
    expect(screen.getByText("Step 2 — Classification Result")).toBeDefined();
    expect(screen.getByText("CONFIDENTIAL")).toBeDefined();
    expect(screen.getByText("85.0%")).toBeDefined();

    expect(mockRegisterAndClassify).toHaveBeenCalledTimes(1);
    expect(mockRegisterAndClassify).toHaveBeenCalledWith(
      "quarterly-report.pdf",
      expect.stringContaining("confidential"),
      "data_owner"
    );
  });

  it("renders fail-safe escalation row when is_defaulted is true, and omits it when false", async () => {
    const user = userEvent.setup();

    // 1. When is_defaulted is true:
    const defaultedClassification: ClassificationResponse = {
      ...sampleClassification,
      sensitivity_label: "CONFIDENTIAL",
      is_defaulted: true,
      base_label: "PUBLIC",
      confidence: 0.42,
    };
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: defaultedClassification,
    });

    const { unmount } = render(<DashboardPage />);

    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    });
    await user.click(classifyButton);

    expect(screen.getByText("Escalated from")).toBeDefined();
    expect(screen.getByText("PUBLIC")).toBeDefined();
    expect(screen.getByText(/fail-safe/i)).toBeDefined();

    unmount();

    // 2. When is_defaulted is false:
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: { ...sampleClassification, is_defaulted: false },
    });

    render(<DashboardPage />);
    const classifyButton2 = screen.getByRole("button", {
      name: /register & classify/i,
    });
    await user.click(classifyButton2);

    expect(screen.queryByText("Escalated from")).toBeNull();
    expect(screen.queryByText(/fail-safe/i)).toBeNull();
  });

  it("renders error message and leaves results panel empty on ApiError", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockRejectedValueOnce(
      new ApiError(404, "Not Found", {
        detail: "No document registered with that id",
      })
    );

    render(<DashboardPage />);

    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    });
    await user.click(classifyButton);

    // Error text is rendered
    expect(
      screen.getByText(/API 404: No document registered with that id/i)
    ).toBeDefined();

    // Results panel remains empty
    expect(screen.queryByText("Step 1 — Document Registered")).toBeNull();
    expect(screen.queryByText("Step 2 — Classification Result")).toBeNull();
  });

  it("disables classify button when filename or content is blank or whitespace-only, and enables when both are present", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    const filenameInput = screen.getByLabelText(/^filename/i);
    const contentInput = screen.getByLabelText(/^document content/i);
    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    }) as HTMLButtonElement;

    // Initially both fields have default values, so button is enabled
    expect(classifyButton.disabled).toBe(false);

    // Blank out filename
    await user.clear(filenameInput);
    expect(classifyButton.disabled).toBe(true);

    // Whitespace only filename
    await user.type(filenameInput, "   ");
    expect(classifyButton.disabled).toBe(true);

    // Restore filename
    await user.clear(filenameInput);
    await user.type(filenameInput, "report.docx");
    expect(classifyButton.disabled).toBe(false);

    // Blank out content
    await user.clear(contentInput);
    expect(classifyButton.disabled).toBe(true);

    // Whitespace only content
    await user.type(contentInput, "   \n  \t ");
    expect(classifyButton.disabled).toBe(true);

    // Restore content
    await user.clear(contentInput);
    await user.type(contentInput, "Some classified data.");
    expect(classifyButton.disabled).toBe(false);
  });

  it("passes the newly selected role through to the client call", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: sampleClassification,
    });

    render(<DashboardPage />);

    const roleSelect = screen.getByLabelText(/caller role/i);
    await user.selectOptions(roleSelect, "compliance_officer");

    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    });
    await user.click(classifyButton);

    expect(mockRegisterAndClassify).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(String),
      "compliance_officer"
    );
  });

  it("renders status, service, and version on health check success, and error message on failure", async () => {
    const user = userEvent.setup();

    // 1. Success case
    mockCheckHealth.mockResolvedValueOnce(sampleHealth);
    const { unmount } = render(<DashboardPage />);

    const healthButton = screen.getByRole("button", {
      name: /check health/i,
    });
    await user.click(healthButton);

    expect(screen.getByText("ok")).toBeDefined();
    expect(screen.getByText("q-aegis-shield-backend")).toBeDefined();
    expect(screen.getByText("0.1.0")).toBeDefined();
    expect(screen.getByText("v0.1.0")).toBeDefined();

    unmount();

    // 2. Failure case
    mockCheckHealth.mockRejectedValueOnce(
      new ApiError(503, "Service Unavailable", {
        detail: "Postgres connection refused",
      })
    );
    render(<DashboardPage />);

    const healthButton2 = screen.getByRole("button", {
      name: /check health/i,
    });
    await user.click(healthButton2);

    expect(
      screen.getByText(/API 503: Postgres connection refused/i)
    ).toBeDefined();
  });
});
