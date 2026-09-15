"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface HashDisplayProps {
  hash: string;
  visibleChars?: number;
  className?: string;
}

/**
 * Render a cryptographic hash in abbreviated form and reveal the full value
 * on hover, keyboard focus, or selection. The complete hash remains available
 * to assistive technology. Includes a copy-to-clipboard button.
 */
export default function HashDisplay({
  hash,
  visibleChars = 8,
  className = "",
}: HashDisplayProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const safeVisibleChars =
    Number.isInteger(visibleChars) && visibleChars > 0 ? visibleChars : 8;
  const abbreviated =
    hash.length > safeVisibleChars
      ? `${hash.slice(0, safeVisibleChars)}…`
      : hash;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API may not be available in all environments
    }
  }

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`.trim()}>
      <button
        type="button"
        aria-expanded={expanded}
        aria-label={
          expanded ? "Show abbreviated hash" : `Show full hash ${hash}`
        }
        title={hash}
        onClick={() => setExpanded((current) => !current)}
        className="group inline-flex max-w-full items-center rounded px-1.5 py-0.5 text-left bg-[var(--surface-3)] hover:bg-[var(--surface-4)] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--border-focus)]"
      >
        <span
          aria-hidden="true"
          className={expanded ? "sr-only" : "mono-data text-xs text-[var(--accent-teal)]"}
        >
          {abbreviated}
        </span>
        <span
          aria-hidden="true"
          className={
            expanded
              ? "mono-data max-w-full text-xs break-all text-[var(--accent-teal)]"
              : "mono-data hidden max-w-full text-xs break-all text-[var(--accent-teal)] group-hover:inline group-focus-visible:inline"
          }
        >
          {/* Segment hash into 8-char groups for readability */}
          {hash.match(/.{1,8}/g)?.join(" ") ?? hash}
        </span>
        <span className="sr-only">Full hash: {hash}</span>
      </button>

      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[var(--text-muted)] hover:text-[var(--accent-teal)] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--border-focus)]"
        aria-label="Copy hash to clipboard"
        title="Copy to clipboard"
      >
        {copied ? (
          <Check className="h-3 w-3 text-[var(--accent-emerald)]" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </button>
    </span>
  );
}
