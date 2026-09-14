"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SiteNav } from "@/components/SiteNav";
import { ApiError, login } from "@/lib/api/client";
import { clearSession, getSessionUser } from "@/lib/auth/session";

export default function LoginPage() {
  const router = useRouter();
  const existing = typeof window !== "undefined" ? getSessionUser() : null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login({ email, password });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold"
            >
              Q
            </Link>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Sign in</h1>
              <p className="text-xs text-[var(--color-text-muted)]">
                Local JWT · seeded accounts
              </p>
            </div>
          </div>
          <SiteNav active="/login" />
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-md px-6 py-10">
        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 space-y-4"
        >
          {existing && (
            <p className="text-sm text-[var(--color-text-secondary)]">
              Signed in as {existing.email} ({existing.role}).{" "}
              <button
                type="button"
                className="text-cyan-400 hover:underline"
                onClick={() => {
                  clearSession();
                  window.location.reload();
                }}
              >
                Sign out
              </button>
            </p>
          )}
          <div>
            <label htmlFor="email" className="block text-xs mb-1.5">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs mb-1.5">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-[var(--color-accent-blue)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-xs text-[var(--color-text-muted)]">
            Use a seeded account from local setup (
            <code className="text-[var(--color-text-secondary)]">
              QAEGIS_DEV_SEED_PASSWORD
            </code>
            ). Role header remains a DEV-ONLY bypass when no JWT is stored.
          </p>
        </form>
      </main>
    </div>
  );
}
