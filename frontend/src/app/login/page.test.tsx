import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "./page";
import { login, ApiError } from "@/lib/api/client";
import type { UserRole } from "@/lib/api/types";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    login: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// LoginPage reads identity from RoleContext; the redirect logic under test does
// not depend on provider state, so a lightweight stub keeps each test isolated
// from storage/hydration side effects. signIn is a spy the page calls post-auth.
vi.mock("@/lib/context/RoleContext", () => ({
  useRole: () => ({
    role: "security_admin",
    setRole: vi.fn(),
    user: null,
    isAuthenticated: false,
    hydrated: true,
    signIn: vi.fn(),
    signOut: vi.fn(),
  }),
}));

const mockLogin = vi.mocked(login);

async function signInAs(role: UserRole): Promise<void> {
  const user = userEvent.setup();
  mockLogin.mockResolvedValueOnce({
    access_token: "tok",
    token_type: "bearer",
    user_id: `u-${role}`,
    email: `${role}@dev.qaegis.local`,
    role,
    name: role,
  });
  render(<LoginPage />);
  await user.clear(screen.getByLabelText(/^email$/i));
  await user.type(screen.getByLabelText(/^email$/i), `${role}@dev.qaegis.local`);
  await user.clear(screen.getByLabelText(/^password$/i));
  await user.type(screen.getByLabelText(/^password$/i), "local-dev-only-password");
  await user.click(screen.getByRole("button", { name: /sign in/i }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("submits email and password to login", async () => {
    await signInAs("security_admin");
    expect(mockLogin).toHaveBeenCalledWith({
      email: "security_admin@dev.qaegis.local",
      password: "local-dev-only-password",
    });
  });

  it("shows an API error", async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error("Some random error"));
    render(<LoginPage />);
    await user.type(screen.getByLabelText(/^email$/i), "user@dev.qaegis.local");
    await user.type(screen.getByLabelText(/^password$/i), "wrong-password");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/Network error/i)).toBeInTheDocument();
  });

  // Role-aware landing: the old fixed "/dashboard" push dropped data_owner and
  // compliance_officer onto a "not permitted" wall (that route is gated to the
  // inventory readers). Each role must land somewhere it can actually see.
  it("routes data_owner to the classify home, not the gated dashboard", async () => {
    await signInAs("data_owner");
    expect(pushMock).toHaveBeenCalledWith("/");
  });

  it("routes compliance_officer to the policy rules studio", async () => {
    await signInAs("compliance_officer");
    expect(pushMock).toHaveBeenCalledWith("/rules");
  });

  it("still routes security_admin to the dashboard", async () => {
    await signInAs("security_admin");
    expect(pushMock).toHaveBeenCalledWith("/dashboard");
  });
});
