import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPage from "./page";
import {
  checkHealth,
  registerUploadAndClassify,
  ApiError,
} from "@/lib/api/client";
import type {
  ClassificationResponse,
  DocumentResponse,
  HealthResponse,
  UploadResponse,
} from "@/lib/api/types";
import { RoleProvider } from "@/lib/context/RoleContext";
import { setDevRole } from "@/lib/auth/session";

// Mock the API client module — we test the component here, not the client.
// The page registers, uploads the file, then classifies via
// registerUploadAndClassify (server-side extraction is authoritative; the
// pasted preview is only a fallback), so that is the function we intercept.
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    checkHealth: vi.fn(),
    registerUploadAndClassify: vi.fn(),
  };
});

const mockCheckHealth = vi.mocked(checkHealth);
const mockRegisterUploadAndClassify = vi.mocked(registerUploadAndClassify);

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

const DEFAULT_UPLOAD_TEXT =
  "This document contains confidential financial projections and restricted trade secrets.";

// The upload leg returns the server's extraction result; the page reads
// `extracted_text_chars` from it, so a resolved mock must carry a real upload.
const sampleUpload: UploadResponse = {
  document_id: "doc-uuid-12345",
  filename: "quarterly-report.pdf",
  storage_path: "/storage/quarterly-report.pdf",
  current_status: "registered",
  size_bytes: DEFAULT_UPLOAD_TEXT.length,
  extracted_text_chars: DEFAULT_UPLOAD_TEXT.length,
  extracted_text_preview: DEFAULT_UPLOAD_TEXT,
  extracted_text: DEFAULT_UPLOAD_TEXT,
};

/**
 * The upload page starts with a clean, empty state. Selecting a file reveals
 * the content preview + classify controls (content is read via FileReader).
 * This helper drops a file through the hidden file input and waits until the
 * FileReader has populated the content textarea.
 */
async function uploadSampleFile(
  user: ReturnType<typeof userEvent.setup>,
  { name = "quarterly-report.pdf", text = DEFAULT_UPLOAD_TEXT }: { name?: string; text?: string } = {},
) {
  const input = document.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  const file = new File([text], name, { type: "text/plain" });
  await user.upload(input, file);
  await waitFor(() => {
    const textarea = screen.getByPlaceholderText(
      /Paste text here only to override/i,
    ) as HTMLTextAreaElement;
    expect(textarea.value).toContain("confidential");
  });
}

describe("DashboardPage workbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the returned document id, sensitivity badge, and confidence on happy path", async () => {
    const user = userEvent.setup();
    mockRegisterUploadAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      upload: sampleUpload,
      classification: sampleClassification,
    });

    render(<RoleProvider><DashboardPage /></RoleProvider>);

    await uploadSampleFile(user);

    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(screen.getByText("Document Registered")).toBeInTheDocument();
    expect(screen.getByText("doc-uuid-12345")).toBeInTheDocument();
    expect(screen.getByText("Classification Analysis")).toBeInTheDocument();
    expect(screen.getByText("CONFIDENTIAL")).toBeInTheDocument();
    expect(screen.getByText("85.0%")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /override classification/i })
    ).toHaveAttribute("href", "/override?document_id=doc-uuid-12345");

    // The page hands the client the selected File (the server extracts text
    // authoritatively), the pasted preview as the fallback, and the caller's
    // role from context (security_admin by default). Assert those real args.
    expect(mockRegisterUploadAndClassify).toHaveBeenCalledTimes(1);
    expect(mockRegisterUploadAndClassify).toHaveBeenCalledWith(
      expect.any(File),
      expect.stringContaining("confidential"),
      "security_admin"
    );
    const [fileArg] = mockRegisterUploadAndClassify.mock.calls[0];
    expect((fileArg as File).name).toBe("quarterly-report.pdf");
  });

  it("renders the fail-safe escalation row when is_defaulted is true", async () => {
    const user = userEvent.setup();
    mockRegisterUploadAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      upload: sampleUpload,
      classification: {
        ...sampleClassification,
        sensitivity_label: "CONFIDENTIAL",
        is_defaulted: true,
        base_label: "PUBLIC",
        confidence: 0.42,
      },
    });

    render(<RoleProvider><DashboardPage /></RoleProvider>);
    await uploadSampleFile(user);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(screen.getByText(/fail-safe/i)).toBeInTheDocument();
  });

  it("omits the fail-safe escalation row when is_defaulted is false", async () => {
    const user = userEvent.setup();
    mockRegisterUploadAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      upload: sampleUpload,
      classification: { ...sampleClassification, is_defaulted: false },
    });

    render(<RoleProvider><DashboardPage /></RoleProvider>);
    await uploadSampleFile(user);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(screen.queryByText(/fail-safe/i)).not.toBeInTheDocument();
  });

  it("renders the error message and leaves the results panel empty on ApiError", async () => {
    const user = userEvent.setup();
    mockRegisterUploadAndClassify.mockRejectedValueOnce(
      new ApiError(404, "Not Found", {
        detail: "No document registered with that id",
      })
    );

    render(<RoleProvider><DashboardPage /></RoleProvider>);
    await uploadSampleFile(user);
    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(
      screen.getByText(/API 404: No document registered with that id/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Document Registered")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Classification Analysis")
    ).not.toBeInTheDocument();
  });

  it("gates classify on selecting a document, not on the pasted preview", async () => {
    const user = userEvent.setup();
    render(<RoleProvider><DashboardPage /></RoleProvider>);

    // Before a document is chosen the classify control does not exist at all —
    // the action is gated on selecting a file, not on typing preview text.
    expect(
      screen.queryByRole("button", { name: /register & classify/i })
    ).not.toBeInTheDocument();

    // Selecting a file reveals the classify control, enabled and ready.
    await uploadSampleFile(user);
    const classifyButton = screen.getByRole("button", {
      name: /register & classify/i,
    });
    expect(classifyButton).toBeEnabled();

    // The preview textarea is only an extraction fallback (the server re-reads
    // the uploaded file), so clearing or blanking it must NOT disable classify.
    const contentInput = screen.getByPlaceholderText(/Paste text here only to override/i);
    await user.clear(contentInput);
    expect(classifyButton).toBeEnabled();

    await user.type(contentInput, "   \n  \t ");
    expect(classifyButton).toBeEnabled();
  });

  it("passes the caller's role through to the client call", async () => {
    const user = userEvent.setup();
    mockRegisterUploadAndClassify.mockResolvedValueOnce({
      document: sampleDocument,
      upload: sampleUpload,
      classification: sampleClassification,
    });

    // The caller's role comes from RoleContext (the shell identity panel), not
    // an in-page selector. data_owner is admitted by the register+classify gate
    // (ACCESS.classify) and differs from the security_admin default, so seeing
    // it on the wire proves the role was threaded from context, not hardcoded.
    setDevRole("data_owner");

    render(<RoleProvider><DashboardPage /></RoleProvider>);

    await uploadSampleFile(user);

    await user.click(
      screen.getByRole("button", { name: /register & classify/i })
    );

    expect(mockRegisterUploadAndClassify).toHaveBeenCalledWith(
      expect.any(File),
      expect.any(String),
      "data_owner"
    );
  });

  it("renders status, service, and version on a successful health check", async () => {
    const user = userEvent.setup();
    mockCheckHealth.mockResolvedValueOnce(sampleHealth);

    render(<RoleProvider><DashboardPage /></RoleProvider>);
    await user.click(screen.getByRole("button", { name: /^check$/i }));

    expect(screen.getByText(/System Online/i)).toBeInTheDocument();
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
  });

  it("renders the error message when the health check fails", async () => {
    const user = userEvent.setup();
    mockCheckHealth.mockRejectedValueOnce(
      new ApiError(503, "Service Unavailable", {
        detail: "Postgres connection refused",
      })
    );

    render(<RoleProvider><DashboardPage /></RoleProvider>);
    await user.click(screen.getByRole("button", { name: /^check$/i }));

    expect(
      screen.getByText(/API 503: Postgres connection refused/i)
    ).toBeInTheDocument();
  });
});
