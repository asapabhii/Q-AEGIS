import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { SiteNav } from "./SiteNav";

describe("SiteNav", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders all navigation links", () => {
    render(<SiteNav active="/" />);
    expect(screen.getByText("Classify")).toBeInTheDocument();
    expect(screen.getByText("Override")).toBeInTheDocument();
    expect(screen.getByText("Rules")).toBeInTheDocument();
  });

  it("marks the active link correctly", () => {
    render(<SiteNav active="/rules" />);
    
    const classifyLink = screen.getByText("Classify");
    const overrideLink = screen.getByText("Override");
    const rulesLink = screen.getByText("Rules");

    // The active link should have aria-current="page"
    expect(rulesLink).toHaveAttribute("aria-current", "page");
    expect(rulesLink).toHaveClass("text-cyan-400");

    // Inactive links should not have aria-current="page"
    expect(classifyLink).not.toHaveAttribute("aria-current");
    expect(classifyLink).toHaveClass("text-[var(--color-text-secondary)]");
    
    expect(overrideLink).not.toHaveAttribute("aria-current");
    expect(overrideLink).toHaveClass("text-[var(--color-text-secondary)]");
  });
});
