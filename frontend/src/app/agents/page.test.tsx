import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import AgentsPage from "./page";
import { getDocumentAgents } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    getDocumentAgents: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("document_id=doc-1"),
}));

const mockAgents = vi.mocked(getDocumentAgents);

describe("AgentsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockAgents.mockResolvedValue({
      document_id: "doc-1",
      risk_score_id: null,
      assessed_at: null,
      agents: [],
      missing_agents: ["security"],
      note: "No risk assessment has been recorded for this document yet.",
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("loads agent deep-dive for the query document", async () => {
    render(<AgentsPage />);
    expect(screen.getByText(/agent deep-dive/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/no risk assessment has been recorded/i)
    ).toBeInTheDocument();
    expect(mockAgents).toHaveBeenCalledWith("doc-1", expect.anything());
  });
});
