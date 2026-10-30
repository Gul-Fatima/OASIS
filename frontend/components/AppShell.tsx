"use client";

/**
 * Application shell.
 *
 * The sidebar is a workflow, not a feature list: four numbered stages whose
 * state comes from the shared workspace, followed by quieter utility links.
 * Any stage can still be opened directly — a developer who only wants to
 * measure something can jump straight to Step 2 instead of walking the flow.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { API_BASE, apiGet } from "@/lib/api";
import {
  STAGES,
  targetName,
  useWorkspace,
  type StageProgress,
} from "@/components/workspace/WorkspaceContext";

type NavItem = { href: string; label: string; icon: string; hint: string };

const UTILITY_NAV: NavItem[] = [
  {
    href: "/analyze",
    label: "Project structure",
    hint: "Parse a whole folder",
    icon: "M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  },
  {
    href: "/optimize",
    label: "Prompt lab",
    hint: "Copy an LLM prompt",
    icon: "M8 8l-4 4 4 4m8-8 4 4-4 4m-3-11-2 14",
  },
  {
    href: "/taxonomy",
    label: "Taxonomy",
    hint: "The 12 smell categories",
    icon: "M4 6h16M4 12h16M4 18h10",
  },
  {
    href: "/history",
    label: "Decision history",
    hint: "Recorded accept / reject",
    icon: "M12 7v5l3 2M21 12a9 9 0 1 1-3-6.7",
  },
];

const SETTINGS_NAV: NavItem = {
  href: "/settings",
  label: "Settings",
  hint: "Backend, LLM, language",
  icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a7.9 7.9 0 0 0 0-6l2-1-2-3.4-2 1a8 8 0 0 0-5-3l-.4-2h-4l-.4 2a8 8 0 0 0-5 3l-2-1L2.6 8l2 1a7.9 7.9 0 0 0 0 6l-2 1 2 3.4 2-1a8 8 0 0 0 5 3l.4 2h4l.4-2a8 8 0 0 0 5-3l2 1 2-3.4z",
};

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

function ThemeButton({
  theme,
  onToggle,
  compact = false,
}: {
  theme: Theme;
  onToggle: () => void;
  compact?: boolean;
}) {
  const label = `Switch to ${theme === "dark" ? "light" : "dark"} theme`;

  if (compact) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label={label}
        title={label}
        className="rounded-lg border border-line bg-surface-2 p-2 text-ink transition hover:border-accent/50 hover:text-accent"
      >
        <Icon path={theme === "dark" ? SUN : MOON} />
      </button>
    );
  }

  return (
    <div className="mb-2.5">
      <p className="overline mb-1">Theme</p>
      <div className="flex rounded-lg border border-line bg-surface-2 p-0.5" role="group" aria-label="Theme">
        <button
          type="button"
          onClick={() => theme !== "dark" && onToggle()}
          aria-pressed={theme === "dark"}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium transition ${
            theme === "dark" ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
          }`}
        >
          <Icon path={MOON} />
          Dark
        </button>
        <button
          type="button"
          onClick={() => theme !== "light" && onToggle()}
          aria-pressed={theme === "light"}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium transition ${
            theme === "light" ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
          }`}
        >
          <Icon path={SUN} />
          Light
        </button>
      </div>
    </div>
  );
}

type Health = "checking" | "online" | "offline";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function StageNavItem({
  href,
  number,
  label,
  hint,
  progress,
  active,
  recommended,
}: {
  href: string;
  number: number;
  label: string;
  hint: string;
  progress: StageProgress;
  active: boolean;
  recommended: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`group relative mb-0.5 flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition ${
        active
          ? "bg-accent-soft/70 text-ink"
          : "text-muted hover:bg-surface-2 hover:text-ink"
      }`}
    >
      <span
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
          progress.state === "done"
            ? "bg-accent text-canvas"
            : active
              ? "bg-accent-soft text-accent ring-1 ring-accent/50"
              : "bg-surface-3 text-muted group-hover:text-ink"
        }`}
      >
        {progress.state === "done" ? "✓" : number}
      </span>

      <span className="min-w-0 flex-1">
        <span className={`block truncate text-sm ${active ? "font-semibold" : "font-medium"}`}>
          {label}
        </span>
        <span className="block truncate text-[10px] text-muted">{hint}</span>
      </span>

      {progress.state === "done" && progress.badge ? (
        <span className="shrink-0 rounded-full border border-line bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted">
          {progress.badge}
        </span>
      ) : recommended && progress.state !== "done" ? (
        <span className="shrink-0 rounded-full bg-accent px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-canvas">
          Next
        </span>
      ) : null}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { progress, recommendedStage, settings } = useWorkspace();
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

  const file = targetName(settings.filePath) || targetName(settings.projectPath);

  return (
    <div className="flex min-h-screen">
      {/* ---------------- SIDEBAR ---------------- */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-surface transition-transform lg:static lg:translate-x-0 ${
          navOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Link
          href="/home"
          className="flex items-center gap-2.5 border-b border-line px-5 py-4 transition hover:bg-surface-2/60"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-base font-bold text-canvas">
            O
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">OASIS</p>
            <p className="text-[11px] text-muted">Energy Intelligence</p>
          </div>
        </Link>

        <div className="border-b border-line px-3 py-2.5">
          <p className="overline mb-1">Current target</p>
          <p className="truncate text-xs font-medium text-ink" title={settings.filePath}>
            {file || <span className="text-muted">No file selected</span>}
          </p>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3">
          <Link
            href="/home"
            aria-current={pathname === "/home" ? "page" : undefined}
            className={`mb-3 flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition ${
              pathname === "/home"
                ? "bg-accent-soft/70 font-semibold text-ink"
                : "text-muted hover:bg-surface-2 hover:text-ink"
            }`}
          >
            <Icon path="M3 3h8v8H3z M13 3h8v5h-8z M13 10h8v11h-8z M3 13h8v8H3z" />
            <span>Overview</span>
          </Link>

          <p className="overline mb-2 px-2">Workflow</p>
          {STAGES.map((stage) => (
            <StageNavItem
              key={stage.id}
              href={stage.href}
              number={stage.number}
              label={stage.title}
              hint={progress[stage.id].hint}
              progress={progress[stage.id]}
              active={isActive(pathname, stage.href)}
              recommended={recommendedStage === stage.id}
            />
          ))}

          <p className="overline mb-2 mt-4 px-2">Tools</p>
          {UTILITY_NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`mb-0.5 flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition ${
                  active
                    ? "bg-accent-soft/70 font-semibold text-ink"
                    : "text-muted hover:bg-surface-2 hover:text-ink"
                }`}
                title={item.hint}
              >
                <Icon path={item.icon} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-line px-4 py-3">
          <Link
            href={SETTINGS_NAV.href}
            className={`mb-2.5 flex items-center gap-2 rounded-lg px-2 py-1.5 text-[11px] transition ${
              isActive(pathname, SETTINGS_NAV.href)
                ? "bg-accent-soft/70 font-semibold text-ink"
                : "text-muted hover:text-ink"
            }`}
          >
            <Icon path={SETTINGS_NAV.icon} />
            {SETTINGS_NAV.label}
          </Link>

          <ThemeButton theme={theme} onToggle={toggleTheme} />

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
          <div className="ml-auto">
            <ThemeButton theme={theme} onToggle={toggleTheme} compact />
          </div>
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
          OASIS — Optimizing Algorithms for Sustainable Intelligent Systems · Prediction is not
          measurement.
        </footer>
      </div>
    </div>
  );
}
