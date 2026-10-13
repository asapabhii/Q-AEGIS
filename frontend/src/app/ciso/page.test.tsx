import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import CisoPage from "./page";
import { listDocuments } from "@/lib/api/client";
import { RoleProvider } from "@/lib/context/RoleContext";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    listDocuments: vi.fn(),
  };
});

// The page threads router.push on row click; a mounted App Router is not
// available under jsdom, so stub the only next/navigation hook it imports.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

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
    // security_admin is the default role and is allowed the fleet view, so the
    // inventory read fires and the loaded fleet section renders.
    render(
      <RoleProvider>
        <CisoPage />
      </RoleProvider>
    );
    expect(screen.getByText(/fleet posture/i)).toBeInTheDocument();
    expect(mockList).toHaveBeenCalled();
    expect(await screen.findByText(/document fleet/i)).toBeInTheDocument();
  });
});
