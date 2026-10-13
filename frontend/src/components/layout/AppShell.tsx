"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ComponentType, type ReactNode } from "react";
import { useRole } from "@/lib/context/RoleContext";
import {
  Activity,
  Anchor,
  ArrowRightLeft,
  Bot,
  ChevronLeft,
  ChevronRight,
  FileSearch,
  FileText,
  Gavel,
  LayoutDashboard,
  Link2,
  LogIn,
  LogOut,
  MessageSquare,
  Network,
  Repeat,
  ShieldCheck,
} from "lucide-react";
import type { UserRole } from "@/lib/api/types";
import { canAccess, ROLE_LABELS, ROLE_OPTIONS } from "@/lib/auth/roles";
import StatusDot from "@/components/ui/StatusDot";

type NavIcon = ComponentType<{ className?: string }>;
type NavItem = { href: string; label: string; icon: NavIcon };
type NavGroup = { title: string; items: NavItem[] };

/**
 * Guided workflow, grouped by the operator's mental model rather than by API
 * surface. Every item's visibility is gated by {@link canAccess}, which mirrors
 * the backend role matrix — the sidebar shows only what the current role can
 * actually use, so it never advertises a page that 403s on entry.
 */
const NAV_GROUPS: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { href: "/ciso", label: "Fleet Posture", icon: ShieldCheck },
      { href: "/dashboard", label: "Risk Dashboard", icon: LayoutDashboard },
      { href: "/engineer", label: "System Health", icon: Activity },
    ],
  },
  {
    title: "Classify & Protect",
    items: [
      { href: "/", label: "Classification", icon: FileSearch },
      { href: "/override", label: "Overrides", icon: Repeat },
      { href: "/rules", label: "Policy Rules", icon: Gavel },
    ],
  },
  {
    title: "Investigate",
    items: [
      { href: "/agents", label: "Agent Analysis", icon: Bot },
      { href: "/graph", label: "Attack Graph", icon: Network },
      { href: "/ask", label: "Assistant", icon: MessageSquare },
    ],
  },
  {
    title: "Evidence",
    items: [
      { href: "/audit", label: "Audit Trail", icon: Link2 },
      { href: "/audit/checkpoints", label: "Checkpoints", icon: Anchor },
    ],
  },
  {
    title: "Operate",
    items: [
      { href: "/migration", label: "Migration", icon: ArrowRightLeft },
      { href: "/summary", label: "Export & Shred", icon: FileText },
    ],
  },
];

const ALL_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/**
 * The single active nav href for a pathname: the longest item href that the
 * path equals or sits under. Longest-match means /audit/checkpoints wins over
 * /audit for its own page, while /audit/{id} still lights up Audit Trail.
 * /documents/* detail pages are reached by deep-link and map to Risk Dashboard.
 */
function resolveActiveHref(pathname: string): string | undefined {
  const matches = ALL_ITEMS.filter((item) =>
    item.href === "/"
      ? pathname === "/"
      : pathname === item.href || pathname.startsWith(`${item.href}/`)
  );
  if (matches.length > 0) {
    return matches.sort((a, b) => b.href.length - a.href.length)[0].href;
  }
  if (pathname.startsWith("/documents/")) return "/dashboard";
  return undefined;
}

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const { role, setRole, user, isAuthenticated } = useRole();
  const [collapsed, setCollapsed] = useState(false);

  // Login is a full-bleed page: no sidebar, no chrome. Rendering it inside the
  // shell would double the header and offer nav for a session that isn't
  // authenticated yet.
  if (pathname === "/login") {
    return (
      <div className="min-h-screen bg-[var(--surface-0)] font-sans text-[var(--text-primary)]">
        {children}
      </div>
    );
  }

  const activeHref = resolveActiveHref(pathname);
  const activeLabel =
    ALL_ITEMS.find((item) => item.href === activeHref)?.label ?? "Q-AEGIS Shield";

  // Only show groups with at least one item this role may use.
  const visibleGroups = NAV_GROUPS.map((group) => ({
    title: group.title,
    items: group.items.filter((item) => canAccess(item.href, role)),
  })).filter((group) => group.items.length > 0);

  const sidebarWidth = collapsed ? "w-[72px]" : "w-[260px]";
  const mainOffset = collapsed ? "md:pl-[72px]" : "md:pl-[260px]";

  return (
    <div className="min-h-screen bg-[var(--surface-0)] font-sans text-[var(--text-primary)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-[var(--surface-1)] focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to main content
      </a>

      {/* ── Sidebar ── */}
      <aside
        className={`fixed inset-y-0 left-0 z-20 hidden flex-col border-r border-[var(--border-default)] bg-[var(--surface-1)] transition-all duration-300 md:flex ${sidebarWidth}`}
      >
        {/* Logo */}
        <div
          className={`flex items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-4 ${collapsed ? "justify-center" : ""}`}
        >
          <div className="relative flex h-9 w-9 shrink-0 items-center justify-center">
            <Image
              src="/qaegis-icon.svg"
              alt="Q-AEGIS Shield"
              width={36}
              height={36}
              className="h-full w-full object-contain"
              priority
            />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight">
                <span className="gradient-text">Q-AEGIS</span>{" "}
                <span className="text-[var(--text-primary)]">Shield</span>
              </p>
              <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">
                Quantum governance
              </p>
            </div>
          )}
        </div>

        {/* Grouped, role-filtered navigation */}
        <nav aria-label="Primary" className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
          {visibleGroups.map((group) => (
            <div key={group.title}>
              {!collapsed && (
                <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  {group.title}
                </p>
              )}
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = item.href === activeHref;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        aria-label={item.label}
                        title={collapsed ? item.label : undefined}
                        className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                          active
                            ? "bg-[var(--surface-3)] text-[var(--text-primary)]"
                            : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
                        } ${collapsed ? "justify-center" : ""}`}
                      >
                        {active && (
                          <span
                            className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-[var(--accent-teal)] to-[var(--accent-violet)]"
                            aria-hidden="true"
                          />
                        )}
                        <Icon
                          className={`h-4 w-4 shrink-0 ${
                            active
                              ? "text-[var(--accent-teal)]"
                              : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]"
                          }`}
                        />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Identity + role + collapse */}
        <div className="space-y-3 border-t border-[var(--border-subtle)] px-3 py-3">
          {!collapsed && (
            <IdentityPanel
              role={role}
              setRole={setRole}
              user={user}
              isAuthenticated={isAuthenticated}
            />
          )}

          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-secondary)] ${collapsed ? "justify-center" : ""}`}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className={`flex min-h-screen flex-col transition-all duration-300 ${mainOffset}`}>
        <header className="sticky top-0 z-10 border-b border-[var(--border-subtle)] bg-[var(--surface-0)]/80 backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
            {/* Mobile logo */}
            <div className="flex items-center gap-2 text-sm md:hidden">
              <div className="relative flex h-7 w-7 shrink-0 items-center justify-center">
                <Image
                  src="/qaegis-icon.svg"
                  alt=""
                  width={28}
                  height={28}
                  className="h-full w-full object-contain"
                  priority
                />
              </div>
              <span className="font-semibold">
                <span className="gradient-text">Q-AEGIS</span>
              </span>
            </div>

            {/* Desktop: route-derived page title */}
            <div className="hidden items-center gap-2 md:flex">
              <h1 className="text-sm font-semibold text-[var(--text-primary)]">
                {activeLabel}
              </h1>
              <span className="text-[var(--border-default)]">·</span>
              <StatusDot variant="online" label="Local environment" />
            </div>

            {/* Mobile role control */}
            <div className="flex items-center gap-2 md:hidden">
              {isAuthenticated ? (
                <span className="rounded-md border border-[var(--border-default)] bg-[var(--surface-2)] px-2 py-1 text-xs text-[var(--text-secondary)]">
                  {ROLE_LABELS[role]}
                </span>
              ) : (
                <>
                  <label htmlFor="mobile-role" className="sr-only">
                    Caller role
                  </label>
                  <select
                    id="mobile-role"
                    value={role}
                    onChange={(event) => setRole(event.target.value as UserRole)}
                    className="rounded-lg border border-[var(--border-default)] bg-[var(--surface-2)] px-2 py-1.5 text-xs text-[var(--text-primary)] focus:border-[var(--border-focus)] focus:outline-none"
                  >
                    {ROLE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </>
              )}
            </div>
          </div>

          {/* Mobile nav (role-filtered, flat) */}
          <nav
            aria-label="Primary mobile"
            className="border-t border-[var(--border-subtle)] px-4 py-2 md:hidden"
          >
            <ul className="flex gap-1.5 overflow-x-auto">
              {ALL_ITEMS.filter((item) => canAccess(item.href, role)).map((item) => {
                const Icon = item.icon;
                const active = item.href === activeHref;
                return (
                  <li key={item.href} className="shrink-0">
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      aria-label={item.label}
                      className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                        active
                          ? "border-[var(--accent-indigo)]/40 bg-[var(--surface-2)] text-[var(--text-primary)]"
                          : "border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]"
                      }`}
                    >
                      <Icon className="h-3 w-3" />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </header>

        <main id="main-content" className="flex-1 px-4 py-6 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}

/** Sidebar footer: who you are, the role you're acting as, and sign in/out. */
function IdentityPanel({
  role,
  setRole,
  user,
  isAuthenticated,
}: {
  role: UserRole;
  setRole: (role: UserRole) => void;
  user: { name: string; email: string } | null;
  isAuthenticated: boolean;
}) {
  const { signOut } = useRole();

  if (isAuthenticated && user) {
    return (
      <div className="space-y-2">
        <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface-2)] px-3 py-2">
          <p className="truncate text-xs font-medium text-[var(--text-primary)]">
            {user.name}
          </p>
          <p className="truncate text-[11px] text-[var(--text-muted)]">{user.email}</p>
          <p className="mt-1 text-[10px] uppercase tracking-wider text-[var(--accent-teal)]">
            {ROLE_LABELS[role]}
          </p>
        </div>
        <button
          type="button"
          onClick={signOut}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-secondary)]"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign out</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div>
        <label
          htmlFor="app-shell-role"
          className="mb-1.5 block text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]"
        >
          Caller role
        </label>
        <select
          id="app-shell-role"
          value={role}
          onChange={(event) => setRole(event.target.value as UserRole)}
          className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--surface-3)] px-2.5 py-2 text-xs text-[var(--text-primary)] focus:border-[var(--border-focus)] focus:outline-none"
        >
          {ROLE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-[10px] leading-tight text-[var(--text-muted)]">
          Dev header bypass. Sign in for a real JWT session.
        </p>
      </div>
      <Link
        href="/login"
        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-secondary)]"
      >
        <LogIn className="h-4 w-4" />
        <span>Sign in</span>
      </Link>
    </div>
  );
}
