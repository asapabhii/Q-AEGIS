import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import AppShell from "./AppShell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/rules",
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

  it("marks the active section, exposes caller roles, and renders content", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <p>Shell content</p>
      </AppShell>,
    );

    const activeLinks = screen.getAllByRole("link", { name: "Rules" });
    expect(activeLinks).toHaveLength(2);
    activeLinks.forEach((link) => {
      expect(link).toHaveAttribute("aria-current", "page");
    });

    const roleSelect = screen.getByRole("combobox", { name: /caller role/i });
    await user.selectOptions(roleSelect, "auditor");
    expect(roleSelect).toHaveValue("auditor");
    expect(screen.getByText("Shell content")).toBeInTheDocument();
  });
});
