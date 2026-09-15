import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { useRef } from "react";
import gsap from "gsap";
import { useGsapFadeIn, useGsapReveal } from "./useGsapReveal";

const mocks = vi.hoisted(() => {
  const kill = vi.fn();
  const revert = vi.fn();
  return {
    kill,
    revert,
    fromTo: vi.fn(() => ({ kill })),
    set: vi.fn(),
    context: vi.fn((callback: () => void) => {
      callback();
      return { revert };
    }),
  };
});

vi.mock("gsap", () => ({
  default: {
    context: mocks.context,
    fromTo: mocks.fromTo,
    set: mocks.set,
  },
}));

const gsapContext = vi.mocked(gsap.context);
const gsapFromTo = vi.mocked(gsap.fromTo);
const gsapSet = vi.mocked(gsap.set);

function RevealHarness() {
  const ref = useGsapReveal<HTMLDivElement>();
  return (
    <div ref={ref}>
      <span data-reveal>First</span>
      <span data-reveal>Second</span>
    </div>
  );
}

function FadeHarness() {
  const ref = useRef<HTMLDivElement | null>(null);
  useGsapFadeIn(ref);
  return <div ref={ref}>Single</div>;
}

describe("GSAP reveal hooks", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("animates marked children and reverts the animation context", () => {
    const { unmount } = render(<RevealHarness />);

    expect(gsapContext).toHaveBeenCalledTimes(1);
    expect(gsapFromTo).toHaveBeenCalledTimes(1);
    expect(gsapFromTo.mock.calls[0]?.[1]).toMatchObject({
      opacity: 0,
      y: 20,
    });

    unmount();
    expect(mocks.revert).toHaveBeenCalledTimes(1);
  });

  it("animates a single element and kills its tween", () => {
    const { unmount } = render(<FadeHarness />);

    expect(screen.getByText("Single")).toBeInTheDocument();
    expect(gsapFromTo).toHaveBeenCalledTimes(1);

    unmount();
    expect(mocks.kill).toHaveBeenCalledTimes(1);
  });

  it("applies the final state immediately for reduced motion", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)",
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    try {
      render(<FadeHarness />);
      expect(gsapSet).toHaveBeenCalledTimes(1);
      expect(gsapFromTo).not.toHaveBeenCalled();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });
});
