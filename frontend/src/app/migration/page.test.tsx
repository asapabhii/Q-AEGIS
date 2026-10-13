import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MigrationPage from "./page";
import { ApiError, rankMigration } from "@/lib/api/client";
import { RoleProvider } from "@/lib/context/RoleContext";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    rankMigration: vi.fn(),
  };
});

const mockRank = vi.mocked(rankMigration);

describe("MigrationPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("ranks with QAOA and shows baseline totals", async () => {
    const user = userEvent.setup();
    mockRank.mockResolvedValueOnce({
      schedule: [
        {
          id: "sched-1",
          document_id: "doc-1",
          priority_rank: 1,
          status: "pending",
          scheduled_upgrade_date: "2026-10-14",
          constraint_snapshot: { budget: 2 },
        },
      ],
      primary: {
        method: "qaoa_numpy",
        selected_ids: ["doc-1"],
        total_score: 0.9,
        total_cost: 1,
      },
      baselines: [
        {
          method: "greedy",
          selected_ids: ["doc-1"],
          total_score: 0.9,
          total_cost: 1,
        },
        {
          method: "simulated_annealing",
          selected_ids: ["doc-1"],
          total_score: 0.9,
          total_cost: 1,
        },
      ],
      constraint_snapshot: { budget: 2, window_days: 30 },
      ranked_at: "2026-09-14T00:00:00Z",
    });

    render(
      <RoleProvider>
        <MigrationPage />
      </RoleProvider>
    );
    await user.click(
      screen.getByRole("button", { name: /rank with qaoa \+ baselines/i })
    );

    expect(mockRank).toHaveBeenCalledWith(
      { budget: 2, window_days: 30, seed: 42 },
      "security_admin"
    );
    expect(await screen.findByText(/qaoa_numpy/i)).toBeInTheDocument();
    expect(screen.getByText("greedy")).toBeInTheDocument();
    const scheduleRow = screen.getByText("doc-1").closest("li");
    expect(scheduleRow).not.toBeNull();
    expect(
      within(scheduleRow as HTMLElement).getByText("1")
    ).toBeInTheDocument();
  });

  it("shows API errors from ranking", async () => {
    const user = userEvent.setup();
    mockRank.mockRejectedValueOnce(
      new ApiError(403, "Forbidden", { detail: "not permitted" })
    );
    render(
      <RoleProvider>
        <MigrationPage />
      </RoleProvider>
    );
    await user.click(
      screen.getByRole("button", { name: /rank with qaoa \+ baselines/i })
    );
    expect(
      await screen.findByText(/API 403: not permitted/i)
    ).toBeInTheDocument();
  });
});
