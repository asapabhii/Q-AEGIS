import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MetricCard from "./MetricCard";

// Mock setInterval and clearInterval for animation testing

describe("MetricCard", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
  });

  it("renders the label and string value without animation", () => {
    render(<MetricCard label="Total Items" value="N/A" tone="teal" />);
    expect(screen.getByText("Total Items")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("renders description and icon when provided", () => {
    const icon = <svg data-testid="test-icon" />;
    render(
      <MetricCard
        label="Users"
        value={100}
        description="Active users this month"
        icon={icon}
        animated={false}
      />
    );
    expect(screen.getByText("Active users this month")).toBeInTheDocument();
    expect(screen.getByTestId("test-icon")).toBeInTheDocument();
  });

  it("renders trend up icon and value", () => {
    render(
      <MetricCard
        label="Growth"
        value="5%"
        trend="up"
        trendValue="+2%"
        animated={false}
      />
    );
    expect(screen.getByText("↗")).toBeInTheDocument();
    expect(screen.getByText("+2%")).toBeInTheDocument();
  });

  it("renders trend down icon", () => {
    render(
      <MetricCard
        label="Loss"
        value="10%"
        trend="down"
        animated={false}
      />
    );
    expect(screen.getByText("↘")).toBeInTheDocument();
  });

  it("renders trend stable icon", () => {
    render(
      <MetricCard
        label="Flat"
        value="0%"
        trend="stable"
        animated={false}
      />
    );
    expect(screen.getByText("→")).toBeInTheDocument();
  });

  it("animates numerical value from 0 to target", () => {
    vi.useFakeTimers();
    render(<MetricCard label="Animated Value" value={100} animated={true} />);
    expect(screen.getByText("0")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(screen.getByText("100")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("handles mouse enter and leave events for hover styling", async () => {
    vi.useRealTimers();
    const user = userEvent.setup({ delay: null });
    const { container } = render(
      <MetricCard label="Hover Me" value={42} animated={false} tone="red" />
    );
    const card = container.firstChild as HTMLElement;
    
    // Initial state: not hovered
    expect(card).toHaveStyle({
      boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)",
    });

    // Hover
    await user.hover(card);
    expect(card).toHaveStyle({
      boxShadow: "0 0 30px -8px rgba(239, 68, 68, 0.4), 0 0 60px -12px rgba(239, 68, 68, 0.2)",
    });

    // Unhover
    await user.unhover(card);
    expect(card).toHaveStyle({
      boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)",
    });
  });

  it("uses neutral tone by default", () => {
    const { container } = render(<MetricCard label="Default Tone" value={10} animated={false} />);
    const card = container.firstChild as HTMLElement;
    
    // Test hover box-shadow for neutral tone to verify it is used
    const user = userEvent.setup({ delay: null });
    // But since it's a synchronous assertion, we can just check the initial styling
    // neutral tone border is rgba(139, 92, 246, 0.15)
    expect(card.style.border).toBe("1px solid rgba(139, 92, 246, 0.15)");
  });
});
