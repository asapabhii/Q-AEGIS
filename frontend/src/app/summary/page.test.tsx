import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { SummaryScreen } from "./page";
import {
  ApiError,
  downloadDocumentSummary,
  shredDocument,
} from "@/lib/api/client";
import { RoleProvider } from "@/lib/context/RoleContext";
import { setDevRole } from "@/lib/auth/session";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    downloadDocumentSummary: vi.fn(),
    shredDocument: vi.fn(),
  };
});

const mockDownload = vi.mocked(downloadDocumentSummary);
const mockShred = vi.mocked(shredDocument);

// SummaryScreen reads the caller's role from RoleContext and threads it into
// every export/shred call. Render inside a real RoleProvider and seed the
// dev-role fallback to data_owner so the provider resolves to that role — the
// role the export/shred assertions below expect the page to forward.
function renderScreen(ui: ReactElement) {
  return render(<RoleProvider>{ui}</RoleProvider>);
}

describe("SummaryScreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setDevRole("data_owner");
  });

  afterEach(() => {
    cleanup();
  });

  it("exports CSV for data_owner when a document id is set", async () => {
    const user = userEvent.setup();
    mockDownload.mockResolvedValueOnce(undefined);
    renderScreen(<SummaryScreen initialDocumentId="doc-1" />);

    await user.click(screen.getByRole("button", { name: /^csv$/i }));
    expect(mockDownload).toHaveBeenCalledWith("doc-1", "csv", "data_owner");
  });

  it("keeps shred disabled until confirmation is checked", async () => {
    const user = userEvent.setup();
    renderScreen(<SummaryScreen initialDocumentId="doc-1" />);

    const shredBtn = screen.getByRole("button", { name: /shred keys/i });
    expect(shredBtn).toBeDisabled();

    await user.click(
      screen.getByRole("checkbox", {
        name: /permanently destroys decryption keys/i,
      })
    );
    expect(shredBtn).toBeEnabled();

    mockShred.mockResolvedValueOnce({
      document_id: "doc-1",
      ciphertext_count: 1,
      newly_destroyed: 1,
      already_shredded: false,
      irreversible: true,
    });
    await user.click(shredBtn);
    expect(mockShred).toHaveBeenCalledWith(
      { document_id: "doc-1", confirmed: true },
      "data_owner"
    );
    expect(await screen.findByText(/newly destroyed 1/i)).toBeInTheDocument();
  });

  it("surfaces shred API errors", async () => {
    const user = userEvent.setup();
    mockShred.mockRejectedValueOnce(
      new ApiError(422, "Unprocessable", { detail: "No ciphertext" })
    );
    renderScreen(<SummaryScreen initialDocumentId="doc-1" />);
    await user.click(
      screen.getByRole("checkbox", {
        name: /permanently destroys decryption keys/i,
      })
    );
    await user.click(screen.getByRole("button", { name: /shred keys/i }));
    expect(await screen.findByText(/API 422: No ciphertext/i)).toBeInTheDocument();
  });
});
