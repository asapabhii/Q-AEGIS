import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { LabelBadge } from "./LabelBadge";

describe("LabelBadge", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders PUBLIC label with correct styles", () => {
    render(<LabelBadge label="PUBLIC" />);
    const badge = screen.getByText("PUBLIC");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-emerald-500/15", "text-emerald-400", "border-emerald-500/30");
  });

  it("renders INTERNAL label with correct styles", () => {
    render(<LabelBadge label="INTERNAL" />);
    const badge = screen.getByText("INTERNAL");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-blue-500/15", "text-blue-400", "border-blue-500/30");
  });

  it("renders CONFIDENTIAL label with correct styles", () => {
    render(<LabelBadge label="CONFIDENTIAL" />);
    const badge = screen.getByText("CONFIDENTIAL");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-amber-500/15", "text-amber-400", "border-amber-500/30");
  });

  it("renders RESTRICTED label with correct styles", () => {
    render(<LabelBadge label="RESTRICTED" />);
    const badge = screen.getByText("RESTRICTED");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-red-500/15", "text-red-400", "border-red-500/30");
  });
});
