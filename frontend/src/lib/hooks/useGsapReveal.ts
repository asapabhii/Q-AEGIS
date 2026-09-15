import { useEffect, useRef, type RefObject } from "react";
import gsap from "gsap";

export interface GsapRevealOptions {
  duration?: number;
  stagger?: number;
  y?: number;
  ease?: string;
  selector?: string;
}

const DEFAULTS = {
  duration: 0.45,
  stagger: 0.08,
  y: 20,
  ease: "power2.out",
  selector: "[data-reveal]",
} as const;

function motionIsReduced(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Animate a container's marked children once on mount.
 *
 * Children selected by `selector` fade from `{ opacity: 0, y }` to visible.
 * Reduced-motion users receive the final state without animation.
 */
export function useGsapReveal<T extends HTMLElement = HTMLDivElement>(
  options: GsapRevealOptions = {},
): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  const duration = options.duration ?? DEFAULTS.duration;
  const stagger = options.stagger ?? DEFAULTS.stagger;
  const y = options.y ?? DEFAULTS.y;
  const ease = options.ease ?? DEFAULTS.ease;
  const selector = options.selector ?? DEFAULTS.selector;

  useEffect(() => {
    const root = ref.current;
    if (!root) return;

    const targets = root.querySelectorAll(selector);
    if (targets.length === 0) return;

    if (motionIsReduced()) {
      gsap.set(targets, { opacity: 1, y: 0 });
      return;
    }

    const context = gsap.context(() => {
      gsap.fromTo(
        targets,
        { opacity: 0, y },
        {
          opacity: 1,
          y: 0,
          duration,
          stagger,
          ease,
          overwrite: "auto",
        },
      );
    }, root);

    return () => {
      context.revert();
    };
  }, [duration, ease, selector, stagger, y]);

  return ref;
}

/**
 * Fade a single element from `{ opacity: 0, y }` to visible.
 *
 * The caller owns the ref. Reduced-motion users receive the final state
 * without animation.
 */
export function useGsapFadeIn<T extends HTMLElement = HTMLDivElement>(
  ref: RefObject<T | null>,
  options: Omit<GsapRevealOptions, "selector" | "stagger"> = {},
): void {
  const duration = options.duration ?? DEFAULTS.duration;
  const y = options.y ?? DEFAULTS.y;
  const ease = options.ease ?? DEFAULTS.ease;

  useEffect(() => {
    const target = ref.current;
    if (!target) return;

    if (motionIsReduced()) {
      gsap.set(target, { opacity: 1, y: 0 });
      return;
    }

    const tween = gsap.fromTo(
      target,
      { opacity: 0, y },
      {
        opacity: 1,
        y: 0,
        duration,
        ease,
        overwrite: "auto",
      },
    );

    return () => {
      tween.kill();
    };
  }, [ref, duration, ease, y]);
}
