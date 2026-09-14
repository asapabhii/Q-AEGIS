import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AskPage from "./page";
import { askRag, ingestRagDocument } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    askRag: vi.fn(),
    ingestRagDocument: vi.fn(),
  };
});

describe("AskPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("ingests then asks a grounded question", async () => {
    const user = userEvent.setup();
    vi.mocked(ingestRagDocument).mockResolvedValueOnce({
      document_id: "doc-1",
      chunks_written: 2,
      embedding_model: "stub-hash-v1",
    });
    vi.mocked(askRag).mockResolvedValueOnce({
      question: "What is the status?",
      answer: "Grounded summary…",
      verified: true,
      plan: "Retrieve…",
      citations: [
        {
          chunk_id: "c1",
          source_type: "inventory_snapshot",
          source_id: "doc-1",
          document_id: "doc-1",
          content: "status=classified",
          score: 0.9,
        },
      ],
      embedding_model: "stub-hash-v1",
      refusal_reason: null,
    });

    render(<AskPage />);
    await user.type(screen.getByLabelText(/document id/i), "doc-1");
    await user.click(
      screen.getByRole("button", { name: /ingest document records/i })
    );
    expect(await screen.findByText(/Indexed 2 chunk/i)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^question$/i));
    await user.type(screen.getByLabelText(/^question$/i), "What is the status?");
    await user.click(screen.getByRole("button", { name: /ask \(verified\)/i }));
    expect(await screen.findByText(/Grounded summary/i)).toBeInTheDocument();
  });
});
