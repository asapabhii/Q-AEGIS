import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OverrideScreen } from "./page";
import { ApiError, getDocument, overrideClassification } from "@/lib/api/client";
import type { DocumentSnapshot, ManualOverrideResponse } from "@/lib/api/types";

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
  await user.type(
    screen.getByLabelText(/^document id/i),
    sampleSnapshot.id
  );
  await user.click(screen.getByRole("button", { name: /^load$/i }));
  expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText(/^new label/i), "INTERNAL");
  await user.type(screen.getByLabelText(/^justification/i), longJustification);
  if (options?.confirm !== false) {
    await user.click(
      screen.getByLabelText(/i confirm this action will be permanently logged/i)
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
    render(<OverrideScreen />);
    await fillReadyForm(user, { confirm: false });

    const submit = screen.getByRole("button", { name: /submit override/i });
    expect(submit).toBeDisabled();
    expect(mockOverride).not.toHaveBeenCalled();

    await user.click(
      screen.getByLabelText(/i confirm this action will be permanently logged/i)
    );
    expect(submit).toBeEnabled();
  });

  it("keeps submit disabled when justification is under 20 characters after trim", async () => {
    const user = userEvent.setup();
    mockGetDocument.mockResolvedValueOnce(sampleSnapshot);
    render(<OverrideScreen />);
    await user.type(screen.getByLabelText(/^document id/i), sampleSnapshot.id);
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    await user.selectOptions(screen.getByLabelText(/^new label/i), "INTERNAL");
    await user.type(screen.getByLabelText(/^justification/i), "   too short   ");
    await user.click(
      screen.getByLabelText(/i confirm this action will be permanently logged/i)
    );
    expect(screen.getByRole("button", { name: /submit override/i })).toBeDisabled();
  });

  it("does not send confirmed and posts only document_id, new_label, justification", async () => {
    const user = userEvent.setup();
    mockOverride.mockResolvedValueOnce(sampleResult);
    render(<OverrideScreen />);
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
    expect(await screen.findByText("Override recorded")).toBeInTheDocument();
    expect(screen.getByText(sampleResult.id)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/i confirm this action will be permanently logged/i)
    ).not.toBeChecked();
  });

  it("unchecking confirmation disables submit again", async () => {
    const user = userEvent.setup();
    render(<OverrideScreen />);
    await fillReadyForm(user);
    const box = screen.getByLabelText(
      /i confirm this action will be permanently logged/i
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
    render(<OverrideScreen />);
    await user.type(screen.getByLabelText(/^document id/i), sampleSnapshot.id);
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    expect(
      await screen.findByText(/API 404: Document was not found/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit override/i })).toBeDisabled();
  });

  it("loads the initial document id and shows the effective label", async () => {
    mockGetDocument.mockResolvedValue(sampleSnapshot);
    render(<OverrideScreen initialDocumentId={sampleSnapshot.id} />);
    expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
    expect(screen.getByText("RESTRICTED")).toBeInTheDocument();
    expect(mockGetDocument).toHaveBeenCalledWith(
      sampleSnapshot.id,
      "security_analyst"
    );
  });

  it("shows a load error when the initial document id cannot be fetched", async () => {
    mockGetDocument.mockRejectedValue(
      new ApiError(404, "Not Found", { detail: "Document was not found." })
    );
    render(<OverrideScreen initialDocumentId={sampleSnapshot.id} />);
    expect(
      await screen.findByText(/API 404: Document was not found/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit override/i })).toBeDisabled();
  });

  it("disables the current label and keeps submit disabled until a different one is chosen", async () => {
    const user = userEvent.setup();
    mockGetDocument.mockResolvedValueOnce(sampleSnapshot);
    render(<OverrideScreen />);
    await user.type(screen.getByLabelText(/^document id/i), sampleSnapshot.id);
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: /RESTRICTED \(current\)/i })
    ).toBeDisabled();
    await user.type(screen.getByLabelText(/^justification/i), longJustification);
    await user.click(
      screen.getByLabelText(/i confirm this action will be permanently logged/i)
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
    render(<OverrideScreen />);
    await user.type(screen.getByLabelText(/^document id/i), sampleSnapshot.id);
    await user.click(screen.getByRole("button", { name: /^load$/i }));
    expect(
      await screen.findByText(/not classified — cannot override/i)
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/^new label/i), "INTERNAL");
    await user.type(screen.getByLabelText(/^justification/i), longJustification);
    await user.click(
      screen.getByLabelText(/i confirm this action will be permanently logged/i)
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
    render(<OverrideScreen />);
    await fillReadyForm(user);
    await user.click(screen.getByRole("button", { name: /submit override/i }));
    expect(
      await screen.findByText(/API 403: Role security_analyst is not permitted/i)
    ).toBeInTheDocument();
    expect(screen.queryByText("Override recorded")).not.toBeInTheDocument();
  });

  it("passes the selected role to load and to persist", async () => {
    const user = userEvent.setup();
    mockOverride.mockResolvedValueOnce(sampleResult);
    render(<OverrideScreen />);
    await user.selectOptions(
      screen.getByLabelText(/^caller role/i),
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
