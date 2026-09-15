import type React from "react";
import { SiteNav, type SiteNavHref } from "@/components/SiteNav";

type AppShellProps = {
  active: SiteNavHref;
  eyebrow: string;
  title: string;
  summary: string;
  status?: string;
  children: React.ReactNode;
};

export function AppShell({
  active,
  eyebrow,
  title,
  summary,
  status,
  children,
}: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-bg-primary)]">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <div
                aria-hidden="true"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-teal-300/40 bg-teal-300/10 text-sm font-bold text-teal-200"
              >
                Q
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase text-teal-200">
                  Q-AEGIS Shield
                </p>
                <h1 className="truncate text-xl font-semibold tracking-normal">
                  {title}
                </h1>
              </div>
            </div>
            <SiteNav active={active} />
          </div>
          <div className="flex flex-col gap-3 border-t border-[var(--color-border)] pt-4 md:flex-row md:items-end md:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">
                {eyebrow}
              </p>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                {summary}
              </p>
            </div>
            {status ? (
              <div className="inline-flex w-fit items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-panel)] px-3 py-2 text-sm text-[var(--color-text-secondary)]">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                {status}
              </div>
            ) : null}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
}
