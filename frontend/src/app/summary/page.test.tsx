import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SummaryScreen } from "./page";
import {
  ApiError,
  downloadDocumentSummary,
  shredDocument,
} from "@/lib/api/client";

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

describe("SummaryScreen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("exports CSV for data_owner when a document id is set", async () => {
    const user = userEvent.setup();
    mockDownload.mockResolvedValueOnce(undefined);
    render(<SummaryScreen initialDocumentId="doc-1" />);

    await user.click(screen.getByRole("button", { name: /download csv/i }));
    expect(mockDownload).toHaveBeenCalledWith("doc-1", "csv", "data_owner");
  });

  it("keeps shred disabled until confirmation is checked", async () => {
    const user = userEvent.setup();
    render(<SummaryScreen initialDocumentId="doc-1" />);

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
    render(<SummaryScreen initialDocumentId="doc-1" />);
    await user.click(
      screen.getByRole("checkbox", {
        name: /permanently destroys decryption keys/i,
      })
    );
    await user.click(screen.getByRole("button", { name: /shred keys/i }));
    expect(await screen.findByText(/API 422: No ciphertext/i)).toBeInTheDocument();
  });
});
