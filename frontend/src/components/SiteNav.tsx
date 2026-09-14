import Link from "next/link";

const LINKS = [
  { href: "/", label: "Classify" },
  { href: "/override", label: "Override" },
  { href: "/rules", label: "Rules" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/audit", label: "Audit" },
  { href: "/summary", label: "Summary" },
  { href: "/migration", label: "Migration" },
] as const;

export type SiteNavHref = (typeof LINKS)[number]["href"];

export function SiteNav({ active }: { active: SiteNavHref }) {
  return (
    <nav
      aria-label="Screens"
      className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm"
    >
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={active === link.href ? "page" : undefined}
          className={
            active === link.href
              ? "text-cyan-400 font-medium"
              : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
          }
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
