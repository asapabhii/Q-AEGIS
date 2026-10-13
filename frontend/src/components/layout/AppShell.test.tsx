import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import AppShell from "./AppShell";
import { RoleProvider } from "@/lib/context/RoleContext";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
  });

  it("marks the active section, exposes the caller role, and renders content", async () => {
    const user = userEvent.setup();
    render(
      <RoleProvider>
        <AppShell>
          <p>Shell content</p>
        </AppShell>
      </RoleProvider>,
    );

    // The default dev role (security_admin) may use Risk Dashboard, so the link
    // is present in both the desktop and mobile navs and is the active section.
    const activeLinks = screen.getAllByRole("link", { name: "Risk Dashboard" });
    expect(activeLinks.length).toBeGreaterThanOrEqual(1);
    activeLinks.forEach((link) => {
      expect(link).toHaveAttribute("aria-current", "page");
    });

    // A compliance-officer-only page is hidden from security_admin's nav.
    expect(
      screen.queryByRole("link", { name: "Policy Rules" }),
    ).not.toBeInTheDocument();

    // The dev-header role selector is present (no JWT session) and settable.
    const [roleSelect] = screen.getAllByRole("combobox", { name: /caller role/i });
    await user.selectOptions(roleSelect, "auditor");
    expect(roleSelect).toHaveValue("auditor");

    expect(screen.getByText("Shell content")).toBeInTheDocument();
  });
});
