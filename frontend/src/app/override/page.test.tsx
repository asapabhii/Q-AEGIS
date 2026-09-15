import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OverrideScreen } from "./page";
import { ApiError, getDocument, overrideClassification } from "@/lib/api/client";
import type { DocumentSnapshot, ManualOverrideResponse } from "@/lib/api/types";
import { RoleProvider, useRole } from "@/lib/context/RoleContext";

function RoleWrapper({ children }: { children: React.ReactNode }) {
  const { role, setRole } = useRole();
  return (
    <>
      <select 
        value={role} 
        onChange={(e) => setRole(e.target.value as any)} 
        aria-label="Role"
      >
        <option value="security_analyst">security_analyst</option>
        <option value="security_admin">security_admin</option>
      </select>
      {children}
    </>
  );
}

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    getDocument: vi.fn(),
    overrideClassification: vi.fn(),
  };
});

const mockGetDocument = vi.mocked(getDocument);
const mockOverride = vi.mocked(overrideClassification);

const sampleSnapshot: DocumentSnapshot = {
  id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  filename: "payroll.pdf",
  storage_path: null,
  current_status: "classified",
  uploaded_by: "11111111-2222-3333-4444-555555555555",
  uploaded_at: "2026-09-10T00:00:00Z",
  sensitivity_label: "RESTRICTED",
  label_source: "classification",
  override_id: null,
  classification_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
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

const sampleResult: ManualOverrideResponse = {
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  document_id: sampleSnapshot.id,
  overridden_by: "11111111-2222-3333-4444-555555555555",
  original_label: "RESTRICTED",
  new_label: "INTERNAL",
  justification: "Reviewed with the data owner and reclassified.",
  overridden_at: "2026-09-10T12:00:00Z",
};

const longJustification = "Reviewed with the data owner and reclassified.";

async function fillReadyForm(
  user: ReturnType<typeof userEvent.setup>,
  options?: { confirm?: boolean }
) {
  mockGetDocument.mockResolvedValueOnce(sampleSnapshot);
  const input = screen.getByPlaceholderText(/Enter document UUID/i);
  fireEvent.change(input, { target: { value: sampleSnapshot.id } });
  await user.click(screen.getByRole("button", { name: /^load$/i }));
  expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /^INTERNAL$/i }));
  await user.type(screen.getByPlaceholderText(/Explain why this classification/i), longJustification);
  if (options?.confirm !== false) {
    await user.click(
      screen.getByLabelText(/i understand and confirm this action will be permanently logged/i)
    );
  }
}

describe("OverrideScreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("keeps submit disabled until the confirmation checkbox is checked", async () => {
    const user = userEvent.setup();
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    await fillReadyForm(user, { confirm: false });

    const submit = screen.getByRole("button", { name: /submit override/i });
    expect(submit).toBeDisabled();
    expect(mockOverride).not.toHaveBeenCalled();

    await user.click(
      screen.getByLabelText(/i understand and confirm this action will be permanently logged/i)
    );
    expect(submit).toBeEnabled();
  }, 10000);

  it("keeps submit disabled when justification is under 20 characters after trim", async () => {
    const user = userEvent.setup();
    mockGetDocument.mockResolvedValueOnce(sampleSnapshot);
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    fireEvent.change(screen.getByPlaceholderText(/Enter document UUID/i), { target: { value: sampleSnapshot.id } });
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    await user.click(screen.getByRole("button", { name: /^INTERNAL$/i }));
    await user.type(screen.getByPlaceholderText(/Explain why this classification/i), "   too short   ");
    await user.click(
      screen.getByLabelText(/i understand and confirm this action will be permanently logged/i)
    );
    expect(screen.getByRole("button", { name: /submit override/i })).toBeDisabled();
  });

  it("does not send confirmed and posts only document_id, new_label, justification", async () => {
    const user = userEvent.setup();
    mockOverride.mockResolvedValueOnce(sampleResult);
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    await fillReadyForm(user);
    mockGetDocument.mockResolvedValueOnce({
      ...sampleSnapshot,
      sensitivity_label: "INTERNAL",
      label_source: "manual_override",
    });

    await user.click(screen.getByRole("button", { name: /submit override/i }));

    expect(mockOverride).toHaveBeenCalledTimes(1);
    expect(mockOverride).toHaveBeenCalledWith(
      {
        document_id: sampleSnapshot.id,
        new_label: "INTERNAL",
        justification: longJustification,
      },
      "security_analyst"
    );
    expect(mockOverride.mock.calls[0][0]).not.toHaveProperty("confirmed");
    expect(mockOverride.mock.calls[0][0]).not.toHaveProperty("original_label");
    expect(await screen.findByText(/Override Successfully Recorded/i)).toBeInTheDocument();
    expect(screen.getByText(sampleResult.id)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/i understand and confirm this action will be permanently logged/i)
    ).not.toBeChecked();
  });

  it("disables submit when the document id no longer matches the loaded snapshot", async () => {
    const user = userEvent.setup();
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    await fillReadyForm(user);
    const submit = screen.getByRole("button", { name: /submit override/i });
    expect(submit).toBeEnabled();
    fireEvent.change(screen.getByPlaceholderText(/Enter document UUID/i), {
      target: { value: "ffffffff-ffff-ffff-ffff-ffffffffffff" },
    });
    expect(screen.queryByRole("button", { name: /submit override/i })).not.toBeInTheDocument();
    expect(screen.queryByText("payroll.pdf")).not.toBeInTheDocument();
    expect(mockOverride).not.toHaveBeenCalled();
  });

  it("unchecking confirmation disables submit again", async () => {
    const user = userEvent.setup();
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    await fillReadyForm(user);
    const box = screen.getByLabelText(
      /i understand and confirm this action will be permanently logged/i
    );
    const submit = screen.getByRole("button", { name: /submit override/i });
    expect(submit).toBeEnabled();
    await user.click(box);
    expect(submit).toBeDisabled();
  });

  it("shows a load error and does not enable submit", async () => {
    const user = userEvent.setup();
    mockGetDocument.mockRejectedValueOnce(
      new ApiError(404, "Not Found", { detail: "Document was not found." })
    );
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    fireEvent.change(screen.getByPlaceholderText(/Enter document UUID/i), { target: { value: sampleSnapshot.id } });
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    expect(
      await screen.findByText(/API 404: Document was not found/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit override/i })).not.toBeInTheDocument();
  });

  it("loads the initial document id and shows the effective label", async () => {
    mockGetDocument.mockResolvedValue(sampleSnapshot);
    render(<RoleProvider><OverrideScreen initialDocumentId={sampleSnapshot.id} /></RoleProvider>);
    expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /RESTRICTED.*Current/i })).toBeDisabled();
    expect(mockGetDocument).toHaveBeenCalledWith(
      sampleSnapshot.id,
      "security_analyst"
    );
  });

  it("shows a load error when the initial document id cannot be fetched", async () => {
    mockGetDocument.mockRejectedValue(
      new ApiError(404, "Not Found", { detail: "Document was not found." })
    );
    render(<RoleProvider><OverrideScreen initialDocumentId={sampleSnapshot.id} /></RoleProvider>);
    expect(
      await screen.findByText(/API 404: Document was not found/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit override/i })).not.toBeInTheDocument();
  });

  it("disables the current label and keeps submit disabled until a different one is chosen", async () => {
    const user = userEvent.setup();
    mockGetDocument.mockResolvedValueOnce(sampleSnapshot);
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    fireEvent.change(screen.getByPlaceholderText(/Enter document UUID/i), { target: { value: sampleSnapshot.id } });
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /RESTRICTED.*Current/i })
    ).toBeDisabled();
    await user.type(screen.getByPlaceholderText(/Explain why this classification/i), longJustification);
    await user.click(
      screen.getByLabelText(/i understand and confirm this action will be permanently logged/i)
    );
    expect(screen.getByRole("button", { name: /submit override/i })).toBeDisabled();
  });

  it("keeps submit disabled for an unclassified document", async () => {
    const user = userEvent.setup();
    mockGetDocument.mockResolvedValueOnce({
      ...sampleSnapshot,
      sensitivity_label: null,
      label_source: null,
      classification_id: null,
    });
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    fireEvent.change(screen.getByPlaceholderText(/Enter document UUID/i), { target: { value: sampleSnapshot.id } });
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    expect(
      await screen.findByText(/not classified/i)
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^INTERNAL$/i }));
    await user.type(screen.getByPlaceholderText(/Explain why this classification/i), longJustification);
    await user.click(
      screen.getByLabelText(/i understand and confirm this action will be permanently logged/i)
    );
    expect(screen.getByRole("button", { name: /submit override/i })).toBeDisabled();
    expect(mockOverride).not.toHaveBeenCalled();
  });

  it("renders a submit error and does not show a recorded override", async () => {
    const user = userEvent.setup();
    mockOverride.mockRejectedValueOnce(
      new ApiError(403, "Forbidden", {
        detail: "Role security_analyst is not permitted.",
      })
    );
    render(<RoleProvider><OverrideScreen /></RoleProvider>);
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /submit override/i }));
    expect(
      await screen.findByText(/API 403: Role security_analyst is not permitted/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Override Successfully Recorded/i)).not.toBeInTheDocument();
  });

  it("passes the selected role to load and to persist", async () => {
    const user = userEvent.setup();
    mockOverride.mockResolvedValueOnce(sampleResult);
    render(<RoleProvider><RoleWrapper><OverrideScreen /></RoleWrapper></RoleProvider>);
    await user.selectOptions(
      screen.getByRole("combobox"),
      "security_admin"
    );
    await fillReadyForm(user);
    mockGetDocument.mockResolvedValueOnce({
      ...sampleSnapshot,
      sensitivity_label: "INTERNAL",
      label_source: "manual_override",
    });
    expect(mockGetDocument).toHaveBeenCalledWith(
      sampleSnapshot.id,
      "security_admin"
    );
    await user.click(screen.getByRole("button", { name: /submit override/i }));
    expect(mockOverride).toHaveBeenCalledWith(
      {
        document_id: sampleSnapshot.id,
        new_label: "INTERNAL",
        justification: longJustification,
      },
      "security_admin"
    );
  });
});

