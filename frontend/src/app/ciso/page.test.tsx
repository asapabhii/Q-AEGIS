import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import CisoPage from "./page";
import { listDocuments } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    listDocuments: vi.fn(),
  };
});

const mockList = vi.mocked(listDocuments);

describe("CisoPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockList.mockResolvedValue({ count: 0, documents: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders posture heading and loads inventory", async () => {
    render(<CisoPage />);
    expect(screen.getByText(/ciso posture/i)).toBeInTheDocument();
    expect(mockList).toHaveBeenCalled();
    expect(await screen.findByText(/fleet risk and protection summary/i)).toBeInTheDocument();
  });
});
