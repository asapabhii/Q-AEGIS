import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  // Kept for backwards compatibility but ignored
  variant?: string;
  accent?: string;
  className?: string;
}

export default function Card({
  title,
  description,
  actions,
  children,
  className = "",
}: CardProps) {
  return (
    <section className={`card p-6 ${className}`.trim()}>
      {title || description || actions ? (
        <header className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div>
            {title && (
              <h2 className="font-semibold text-base" style={{ color: "var(--color-text-primary)" }}>
                {title}
              </h2>
            )}
            {description && (
              <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
                {description}
              </p>
            )}
          </div>
          {actions}
        </header>
      ) : null}
      <div>{children}</div>
    </section>
  );
}
