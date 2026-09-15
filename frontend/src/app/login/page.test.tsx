import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "./page";
import { login, ApiError } from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    login: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const mockLogin = vi.mocked(login);

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("submits email and password to login", async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce({
      access_token: "tok",
      token_type: "bearer",
      user_id: "u1",
      email: "security_admin@dev.qaegis.local",
      role: "security_admin",
      name: "Admin",
    });
    render(<LoginPage />);
    await user.clear(screen.getByLabelText(/^email$/i));
    await user.type(
      screen.getByLabelText(/^email$/i),
      "security_admin@dev.qaegis.local"
    );
    await user.clear(screen.getByLabelText(/^password$/i));
    await user.type(screen.getByLabelText(/^password$/i), "SET_LOCALLY");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(mockLogin).toHaveBeenCalledWith({
      email: "security_admin@dev.qaegis.local",
      password: "SET_LOCALLY",
    });
  });

  it("shows an API error", async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error("Some random error"));
    render(<LoginPage />);
    await user.type(screen.getByLabelText(/^email$/i), "user@dev.qaegis.local");
    await user.type(screen.getByLabelText(/^password$/i), "wrong-password");
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(
      await screen.findByText(/Network error/i)
    ).toBeInTheDocument();
  });
});
