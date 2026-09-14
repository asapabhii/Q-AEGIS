import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import EngineerPage from "./page";
import { checkHealth, listDocuments } from "@/lib/api/client";

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

  it("renders ops heading and health", async () => {
    render(<EngineerPage />);
    expect(screen.getByText(/engineer ops/i)).toBeInTheDocument();
    expect(await screen.findByText(/ok · q-aegis-shield-backend · 0\.1\.0/i)).toBeInTheDocument();
  });
});
