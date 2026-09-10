import Link from "next/link";

const LINKS = [
  { href: "/", label: "Classify" },
  { href: "/override", label: "Override" },
  { href: "/rules", label: "Rules" },
] as const;

export type SiteNavHref = (typeof LINKS)[number]["href"];

export function SiteNav({ active }: { active: SiteNavHref }) {
  return (
    <nav aria-label="Screens" className="flex items-center gap-4 text-sm">
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
