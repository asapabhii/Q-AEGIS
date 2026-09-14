import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPage from "./page";
import {
  checkHealth,
  registerAndClassify,
  runAssessment,
  ApiError,
} from "@/lib/api/client";
import type {
  AssessmentResponse,
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
    runAssessment: vi.fn(),
  };
});

const mockCheckHealth = vi.mocked(checkHealth);
const mockRegisterAndClassify = vi.mocked(registerAndClassify);
const mockRunAssessment = vi.mocked(runAssessment);

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

const sampleAssessment: AssessmentResponse = {
  document_id: "doc-uuid-12345",
  risk_score_id: "risk-uuid-1",
  trust_score_id: "trust-uuid-1",
  consensus_value: "0.720",
  ai_recommendation: "force_pqc",
  policy_decision_id: "policy-uuid-1",
  final_decision: "force_pqc",
  overridden: false,
  crypto_profile_id: "crypto-uuid-1",
  profile_type: "post_quantum",
  ciphertext_id: "cipher-uuid-1",
  encrypted: true,
  reselected: false,
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

    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(screen.getByText("Step 1 — Document Registered")).toBeInTheDocument();
    expect(screen.getByText("doc-uuid-12345")).toBeInTheDocument();
    expect(screen.getByText("Step 2 — Classification Result")).toBeInTheDocument();
    expect(screen.getByText("CONFIDENTIAL")).toBeInTheDocument();
    expect(screen.getByText("85.0%")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /override this classification/i })
    ).toHaveAttribute("href", "/override?document_id=doc-uuid-12345");
    expect(screen.getByRole("link", { name: /^override$/i })).toHaveAttribute(
      "href",
      "/override"
    );
    expect(screen.getByRole("link", { name: /^rules$/i })).toHaveAttribute(
      "href",
      "/rules"
    );
    expect(screen.getByRole("link", { name: /^dashboard$/i })).toHaveAttribute(
      "href",
      "/dashboard"
    );
    expect(screen.getByRole("link", { name: /^audit$/i })).toHaveAttribute(
      "href",
      "/audit"
    );

    expect(mockRegisterAndClassify).toHaveBeenCalledTimes(1);
    expect(mockRegisterAndClassify).toHaveBeenCalledWith(
      "quarterly-report.pdf",
      expect.stringContaining("confidential"),
      "data_owner"
    );
  });

  it("renders the fail-safe escalation row when is_defaulted is true", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: {
        ...sampleClassification,
        sensitivity_label: "CONFIDENTIAL",
        is_defaulted: true,
        base_label: "PUBLIC",
        confidence: 0.42,
      },
    });

    render(<DashboardPage />);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(screen.getByText("Escalated from")).toBeInTheDocument();
    expect(screen.getByText("PUBLIC")).toBeInTheDocument();
    expect(screen.getByText(/fail-safe/i)).toBeInTheDocument();
  });

  it("omits the fail-safe escalation row when is_defaulted is false", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: { ...sampleClassification, is_defaulted: false },
    });

    render(<DashboardPage />);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(screen.queryByText("Escalated from")).not.toBeInTheDocument();
    expect(screen.queryByText(/fail-safe/i)).not.toBeInTheDocument();
  });

  it("renders the error message and leaves the results panel empty on ApiError", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockRejectedValueOnce(
      new ApiError(404, "Not Found", {
        detail: "No document registered with that id",
      })
    );

    render(<DashboardPage />);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(
      screen.getByText(/API 404: No document registered with that id/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Step 1 — Document Registered")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Step 2 — Classification Result")
    ).not.toBeInTheDocument();
  });

  it("disables classify when filename or content is blank or whitespace-only", async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    const filenameInput = screen.getByLabelText(/^filename/i);
    const contentInput = screen.getByLabelText(/^document content/i);
    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    });

    expect(classifyButton).toBeEnabled();

    await user.clear(filenameInput);
    expect(classifyButton).toBeDisabled();

    await user.type(filenameInput, "   ");
    expect(classifyButton).toBeDisabled();

    await user.clear(filenameInput);
    await user.type(filenameInput, "report.docx");
    expect(classifyButton).toBeEnabled();

    await user.clear(contentInput);
    expect(classifyButton).toBeDisabled();

    await user.type(contentInput, "   \n  \t ");
    expect(classifyButton).toBeDisabled();

    await user.clear(contentInput);
    await user.type(contentInput, "Some classified data.");
    expect(classifyButton).toBeEnabled();
  });

  it("passes the newly selected role through to the client call", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: sampleClassification,
    });

    render(<DashboardPage />);

    // security_analyst is actually admitted by POST /classify. Do not use a
    // role the backend would 403, or this test locks that mismatch in.
    await user.selectOptions(
      screen.getByLabelText(/caller role/i),
      "security_analyst"
    );
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(mockRegisterAndClassify).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(String),
      "security_analyst"
    );
  });

  it("renders status, service, and version on a successful health check", async () => {
    const user = userEvent.setup();
    mockCheckHealth.mockResolvedValueOnce(sampleHealth);

    render(<DashboardPage />);
    await user.click(screen.getByRole("button", { name: /check health/i }));

    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("q-aegis-shield-backend")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
  });

  it("renders the error message when the health check fails", async () => {
    const user = userEvent.setup();
    mockCheckHealth.mockRejectedValueOnce(
      new ApiError(503, "Service Unavailable", {
        detail: "Postgres connection refused",
      })
    );

    render(<DashboardPage />);
    await user.click(screen.getByRole("button", { name: /check health/i }));

    expect(
      screen.getByText(/API 503: Postgres connection refused/i)
    ).toBeInTheDocument();
  });

  it("runs assessment with the selected analyst role and shows trust", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: sampleClassification,
    });
    mockRunAssessment.mockResolvedValueOnce(sampleAssessment);

    render(<DashboardPage />);
    await user.selectOptions(
      screen.getByLabelText(/caller role/i),
      "security_analyst"
    );
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );
    await user.click(
      screen.getByRole("button", { name: /run full assessment/i })
    );

    expect(mockRunAssessment).toHaveBeenCalledWith(
      expect.objectContaining({ document_id: "doc-uuid-12345" }),
      "security_analyst"
    );
    expect(screen.getByText("0.720")).toBeInTheDocument();
  });

  it("disables assessment for data_owner and never elevates the role", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: sampleClassification,
    });

    render(<DashboardPage />);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    const assessButton = screen.getByRole("button", {
      name: /run full assessment/i,
    });
    expect(assessButton).toBeDisabled();
    expect(mockRunAssessment).not.toHaveBeenCalled();
  });

  it("surfaces assessment API failures without elevating role", async () => {
    const user = userEvent.setup();
    mockRegisterAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      classification: sampleClassification,
    });
    mockRunAssessment.mockRejectedValueOnce(
      new ApiError(403, "Forbidden", {
        detail: "role security_admin required",
      })
    );

    render(<DashboardPage />);
    await user.selectOptions(
      screen.getByLabelText(/caller role/i),
      "security_admin"
    );
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );
    await user.click(
      screen.getByRole("button", { name: /run full assessment/i })
    );

    expect(mockRunAssessment).toHaveBeenCalledWith(
      expect.objectContaining({ document_id: "doc-uuid-12345" }),
      "security_admin"
    );
    expect(
      screen.getByText(/API 403: role security_admin required/i)
    ).toBeInTheDocument();
  });
});
