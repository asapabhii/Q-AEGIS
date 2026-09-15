"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useRole } from "@/lib/context/RoleContext";
import {
  Shield,
  FileSearch,
  LayoutDashboard,
  Repeat,
  Gavel,
  Link2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import type { UserRole } from "@/lib/api/types";
import StatusDot from "@/components/ui/StatusDot";

const NAV_ITEMS = [
  { href: "/", label: "Classify", icon: FileSearch },
  { href: "/dashboard", label: "Risk Dashboard", icon: LayoutDashboard },
  { href: "/override", label: "Override", icon: Repeat },
  { href: "/rules", label: "Rules", icon: Gavel },
  { href: "/audit", label: "Audit Viewer", icon: Link2 },
];

const ROLE_OPTIONS: Array<{ value: UserRole; label: string }> = [
  { value: "data_owner", label: "Data Owner" },
  { value: "security_analyst", label: "Security Analyst" },
  { value: "security_admin", label: "Security Admin" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "auditor", label: "Auditor" },
  { value: "ciso", label: "CISO" },
  { value: "engineer", label: "Engineer" },
];

interface AppShellProps {
  children: ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const { role, setRole } = useRole();
  const [collapsed, setCollapsed] = useState(false);

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
        <div className={`flex items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-4 ${collapsed ? "justify-center" : ""}`}>
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
              <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
                Quantum governance
              </p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav aria-label="Primary" className="flex-1 px-3 py-4 overflow-y-auto">
          <ul className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={`group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                      active
                        ? "bg-[var(--surface-3)] text-[var(--text-primary)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
                    } ${collapsed ? "justify-center" : ""}`}
                  >
                    {/* Active indicator bar */}
                    {active && (
                      <span
                        className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-[3px] rounded-r-full bg-gradient-to-b from-[var(--accent-teal)] to-[var(--accent-violet)]"
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
        </nav>

        {/* Role Selector + Collapse */}
        <div className="border-t border-[var(--border-subtle)] px-3 py-3 space-y-3">
          {!collapsed && (
            <div>
              <label
                htmlFor="app-shell-role"
                className="block text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)] mb-1.5"
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
            </div>
          )}

          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text-secondary)] transition-colors ${collapsed ? "justify-center" : ""}`}
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
        {/* Top bar */}
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

            {/* Status indicator */}
            <div className="hidden items-center gap-3 md:flex">
              <StatusDot variant="online" label="Local environment" />
            </div>

            {/* Mobile role selector */}
            <div className="flex items-center gap-3 md:hidden">
              <select
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
            </div>

            {/* Desktop: page title derived from current route */}
            <div className="hidden items-center gap-2 text-xs text-[var(--text-muted)] md:flex">
              <Shield className="h-3.5 w-3.5 text-[var(--accent-violet)]" />
              <span>SPEC.md 3.13</span>
              <span className="text-[var(--border-default)]">·</span>
              <span>Server decides access; the interface reflects that decision</span>
            </div>
          </div>

          {/* Mobile nav */}
          <nav
            aria-label="Primary mobile"
            className="border-t border-[var(--border-subtle)] px-4 py-2 md:hidden"
          >
            <ul className="flex gap-1.5 overflow-x-auto">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active =
                  pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <li key={item.href} className="shrink-0">
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
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
