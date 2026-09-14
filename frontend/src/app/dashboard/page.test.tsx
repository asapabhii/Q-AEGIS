import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardScreen } from "./page";
import { ApiError, listDocuments } from "@/lib/api/client";
import type { DocumentSnapshot } from "@/lib/api/types";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    listDocuments: vi.fn(),
  };
});

const mockList = vi.mocked(listDocuments);

const unlabeled: DocumentSnapshot = {
  id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  filename: "notes.txt",
  storage_path: null,
  current_status: "registered",
  uploaded_by: "11111111-2222-3333-4444-555555555555",
  uploaded_at: "2026-09-10T00:00:00Z",
  sensitivity_label: null,
  label_source: null,
  override_id: null,
  classification_id: null,
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

const labeled: DocumentSnapshot = {
  ...unlabeled,
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  filename: "payroll.pdf",
  current_status: "classified",
  sensitivity_label: "RESTRICTED",
  label_source: "classification",
  classification_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
};

describe("DashboardScreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders inventory rows and dashes for stages that have not run", async () => {
    mockList.mockResolvedValue({
      count: 2,
      documents: [labeled, unlabeled],
    });
    render(<DashboardScreen />);
    expect(await screen.findByText("payroll.pdf")).toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText("RESTRICTED")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(mockList).toHaveBeenCalledWith("security_admin");
    const rowAudit = screen
      .getAllByRole("link", { name: /^audit$/i })
      .find((link) => link.getAttribute("href")?.includes(labeled.id));
    expect(rowAudit).toHaveAttribute(
      "href",
      `/audit?document_id=${labeled.id}`
    );
  });

  it("shows the empty inventory copy when the fleet is empty", async () => {
    mockList.mockResolvedValue({ count: 0, documents: [] });
    render(<DashboardScreen />);
    expect(
      await screen.findByText(/no documents registered/i)
    ).toBeInTheDocument();
  });

  it("renders a load error", async () => {
    mockList.mockRejectedValue(
      new ApiError(403, "Forbidden", {
        detail: "Role data_owner is not permitted.",
      })
    );
    render(<DashboardScreen />);
    expect(
      await screen.findByText(/API 403: Role data_owner is not permitted/i)
    ).toBeInTheDocument();
  });

  it("passes the selected role on refresh", async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValue({ count: 0, documents: [] });
    render(<DashboardScreen />);
    await screen.findByText(/no documents registered/i);
    await user.selectOptions(
      screen.getByLabelText(/^caller role/i),
      "auditor"
    );
    await user.click(screen.getByRole("button", { name: /refresh/i }));
    expect(mockList).toHaveBeenCalledWith("auditor");
  });
});
