import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import AppShell from "@/components/layout/AppShell";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Q-AEGIS Shield",
  description:
    "Quantum-Adaptive Encryption Governance & Intelligent Security — " +
    "classify data sensitivity, score risk, and select post-quantum encryption.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[var(--surface-0)] font-sans text-[var(--text-primary)]">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

