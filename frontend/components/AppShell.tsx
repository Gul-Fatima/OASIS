"use client";

/**
 * Application shell: sidebar navigation plus a live backend status indicator.
 *
 * The health probe is the one piece of shared state in the UI — every page
 * depends on the FastAPI backend being reachable, so it is surfaced globally
 * rather than repeating the same error on each dashboard.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { API_BASE, apiGet } from "@/lib/api";

// const NAV: { href: string; label: string; icon: string }[] = [
//   { href: "/", label: "Optimize", icon: "M13 2 4 14h6l-1 8 9-12h-6z" },
//   { href: "/history", label: "History", icon: "M12 7v5l3 2M21 12a9 9 0 1 1-3-6.7" },
//   { href: "/settings", label: "Settings", icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a7.9 7.9 0 0 0 0-6l2-1-2-3.4-2 1a8 8 0 0 0-5-3l-.4-2h-4l-.4 2a8 8 0 0 0-5 3l-2-1L2.6 8l2 1a7.9 7.9 0 0 0 0 6l-2 1 2 3.4 2-1a8 8 0 0 0 5 3l.4 2h4l.4-2a8 8 0 0 0 5-3l2 1 2-3.4z" },
// ];

const NAV: { href: string; label: string; icon: string }[] = [
  {
    href: "/home",
    label: "Dashboard",
    icon: "M3 3h8v8H3z M13 3h8v5h-8z M13 10h8v11h-8z M3 13h8v8H3z",
  },
  {
    href: "/optimize",
    label: "Optimize",
    icon: "M13 2 4 14h6l-1 8 9-12h-6z",
  },
  {
    href: "/analyze",
    label: "Analyze",
    icon: "M4 19V5 M4 19h16 M8 15l3-4 3 2 5-7",
  },
  {
    href: "/energy",
    label: "Energy",
    icon: "M13 2 5 13h6l-1 9 9-12h-6z",
  },
  {
    href: "/detect",
    label: "Detect",
    icon: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  },
  {
    href: "/candidates",
    label: "Candidates",
    icon: "M9 12l2 2 4-4 M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z",
  },
  {
    href: "/history",
    label: "History",
    icon: "M12 7v5l3 2M21 12a9 9 0 1 1-3-6.7",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a7.9 7.9 0 0 0 0-6l2-1-2-3.4-2 1a8 8 0 0 0-5-3l-.4-2h-4l-.4 2a8 8 0 0 0-5 3l-2-1L2.6 8l2 3.4 2-1a7.9 7.9 0 0 0 0 6l-2 1 2 3.4 2-1a8 8 0 0 0 5 3l.4 2h4l.4-2a8 8 0 0 0 5-3l2 1 2-3.4z",
  },
];

const THEME_KEY = "oasis-theme";

type Theme = "dark" | "light";

const SUN = "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4";
const MOON = "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z";

function Icon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4 shrink-0"
      aria-hidden
    >
      <path d={path} />
    </svg>
  );
}

type Health = "checking" | "online" | "offline";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [health, setHealth] = useState<Health>("checking");
  const [navOpen, setNavOpen] = useState(false);
  // Initial value must match the server render (dark); the real value is
  // read after mount, from the attribute the root layout script already set.
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    let cancelled = false;

    async function probe() {
      try {
        await apiGet<{ status: string }>("/api/health");
        if (!cancelled) setHealth("online");
      } catch {
        if (!cancelled) setHealth("offline");
      }
    }

    void probe();
    const timer = window.setInterval(probe, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  // Close the drawer whenever the route changes.
  useEffect(() => setNavOpen(false), [pathname]);

  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  }, []);

  function toggleTheme() {
    const next: Theme = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      /* private mode: the toggle still works for this session */
    }
  }

  const statusDot =
    health === "online"
      ? "bg-accent"
      : health === "offline"
        ? "bg-danger"
        : "bg-warn animate-pulse";

  const statusText =
    health === "online"
      ? "Backend online"
      : health === "offline"
        ? "Backend offline"
        : "Checking backend…";

  return (
    <div className="flex min-h-screen">
      {/* ---------------- SIDEBAR ---------------- */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-surface transition-transform lg:static lg:translate-x-0 ${
          navOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-2.5 border-b border-line px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-base font-bold text-canvas">
            O
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">OASIS</p>
            <p className="text-[11px] text-muted">Energy Intelligence</p>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {NAV.map((item) => {
            // const active =
            //   item.href === "/"
            //     ? pathname === "/"
            //     : pathname.startsWith(item.href);
            
            const active =
            pathname === item.href ||
            pathname.startsWith(`${item.href}/`);


            return (
              <Link
                key={item.href}
                href={item.href}
                className={`mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-accent-soft font-semibold text-accent"
                    : "text-muted hover:bg-surface-2 hover:text-ink"
                }`}
              >
                <Icon path={item.icon} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-line px-4 py-3">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className="mb-2.5 flex w-full items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[11px] text-ink transition hover:border-accent/50 hover:text-accent"
          >
            <Icon path={theme === "dark" ? SUN : MOON} />
            <span>{theme === "dark" ? "Light theme" : "Dark theme"}</span>
          </button>

          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${statusDot}`} />
            <span className="text-[11px] text-muted">{statusText}</span>
          </div>
          <p className="mt-1 truncate text-[10px] text-muted/70" title={API_BASE}>
            {API_BASE}
          </p>
        </div>
      </aside>

      {navOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
        />
      ) : null}

      {/* ---------------- MAIN ---------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-canvas/90 px-4 py-2.5 backdrop-blur lg:hidden">
          <button
            type="button"
            onClick={() => setNavOpen((open) => !open)}
            className="rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-xs text-ink"
          >
            ☰ Menu
          </button>
          <span className="text-sm font-semibold">OASIS</span>
        </div>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {health === "offline" ? (
            <div className="mb-5 rounded-lg border border-warn/40 bg-warn-soft/50 px-4 py-3 text-sm text-ink">
              <p className="font-semibold text-warn">Backend not reachable</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted">
                Start it from the <code className="text-ink">OASIS</code> directory:{" "}
                <code className="text-ink">uvicorn backend.main:app --port 8000</code>
              </p>
            </div>
          ) : null}

          {children}
        </main>

        <footer className="border-t border-line px-6 py-4 text-[11px] text-muted">
          OASIS — Optimizing Algorithms for Sustainable Intelligent Systems ·
          Prediction is not measurement.
        </footer>
      </div>
    </div>
  );
}
