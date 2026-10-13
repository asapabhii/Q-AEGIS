import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import EngineerPage from "./page";
import { checkHealth, listDocuments } from "@/lib/api/client";
import { RoleProvider } from "@/lib/context/RoleContext";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    checkHealth: vi.fn(),
    listDocuments: vi.fn(),
  };
});

const mockHealth = vi.mocked(checkHealth);
const mockList = vi.mocked(listDocuments);

describe("EngineerPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockHealth.mockResolvedValue({
      status: "ok",
      service: "q-aegis-shield-backend",
      version: "0.1.0",
    });
    mockList.mockResolvedValue({ count: 0, documents: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the system health heading and backend health details", async () => {
    render(
      <RoleProvider>
        <EngineerPage />
      </RoleProvider>
    );
    // The page renders its heading immediately (the caller is permitted).
    expect(screen.getByText(/system health/i)).toBeInTheDocument();
    // After the health probe resolves it surfaces the backend status, service,
    // and version across the metric cards.
    expect(await screen.findByText(/q-aegis-shield-backend/i)).toBeInTheDocument();
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
    expect(screen.getByText(/online/i)).toBeInTheDocument();
  });
});
