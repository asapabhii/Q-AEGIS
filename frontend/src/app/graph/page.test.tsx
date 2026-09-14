import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GraphPage from "./page";
import { getGraphStatus, seedGraph } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    getGraphStatus: vi.fn(),
    seedGraph: vi.fn(),
    getDocumentAttackPaths: vi.fn(),
  };
});

describe("GraphPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getGraphStatus).mockResolvedValue({ configured: true });
  });

  afterEach(() => {
    cleanup();
  });

  it("seeds the demo graph", async () => {
    const user = userEvent.setup();
    vi.mocked(seedGraph).mockResolvedValueOnce({
      nodes_upserted: 5,
      relationships_upserted: 6,
      demo: true,
    });
    render(<GraphPage />);
    expect(await screen.findByText(/Neo4j configured: yes/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /seed demo graph/i }));
    expect(await screen.findByText(/Seeded 5 nodes/i)).toBeInTheDocument();
  });
});
