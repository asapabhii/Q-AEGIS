import Link from "next/link";

const LINKS = [
  { href: "/", label: "Classify" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/ciso", label: "CISO" },
  { href: "/engineer", label: "Engineer" },
  { href: "/override", label: "Override" },
  { href: "/rules", label: "Rules" },
  { href: "/audit", label: "Audit" },
  { href: "/summary", label: "Summary" },
  { href: "/migration", label: "Migration" },
  { href: "/graph", label: "Graph" },
  { href: "/ask", label: "Ask" },
  { href: "/login", label: "Login" },
] as const;

export type SiteNavHref = (typeof LINKS)[number]["href"];

export function SiteNav({ active }: { active: SiteNavHref }) {
  return (
    <nav
      aria-label="Screens"
      className="flex flex-wrap items-center gap-1 text-sm"
    >
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={active === link.href ? "page" : undefined}
          className={
            active === link.href
              ? "rounded-lg border border-teal-300/40 bg-teal-300/10 px-3 py-2 font-medium text-teal-100"
              : "rounded-lg px-3 py-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-card)] hover:text-[var(--color-text-primary)]"
          }
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
