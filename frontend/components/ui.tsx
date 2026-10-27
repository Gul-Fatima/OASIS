/**
 * Presentational building blocks shared by every dashboard.
 *
 * These are deliberately hook-free so they can be rendered from either server
 * or client components. Anything interactive (buttons with handlers) gets its
 * behaviour from the client component that uses it.
 */

import type { ReactNode } from "react";

export const inputClass =
  "w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink " +
  "placeholder:text-muted/60 outline-none transition focus:border-accent focus:ring-2 " +
  "focus:ring-accent/20 disabled:opacity-50";

export const labelClass = "block text-xs font-medium text-muted mb-1.5";

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 " +
  "text-sm font-semibold text-canvas transition hover:brightness-110 " +
  "disabled:cursor-not-allowed disabled:opacity-40";

export const buttonGhost =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-line " +
  "bg-surface-2 px-4 py-2 text-sm font-medium text-ink transition " +
  "hover:border-accent/50 hover:bg-surface-3 disabled:cursor-not-allowed disabled:opacity-40";

export const buttonDanger =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-danger/40 " +
  "bg-danger-soft px-4 py-2 text-sm font-medium text-danger transition " +
  "hover:border-danger disabled:cursor-not-allowed disabled:opacity-40";

/* ============================================================
   LAYOUT
   ============================================================ */

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface p-5 shadow-lg shadow-black/20 ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionHeader({
  overline,
  title,
  description,
  actions,
}: {
  overline?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {overline ? <p className="overline mb-1">{overline}</p> : null}
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function PageHeader({
  overline,
  title,
  description,
  actions,
}: {
  overline?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        {overline ? <p className="overline mb-1.5">{overline}</p> : null}
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/* ============================================================
   DATA DISPLAY
   ============================================================ */

export type Tone = "ink" | "accent" | "info" | "warn" | "danger" | "muted" | "violet";

const toneText: Record<Tone, string> = {
  ink: "text-ink",
  accent: "text-accent",
  info: "text-info",
  warn: "text-warn",
  danger: "text-danger",
  muted: "text-muted",
  violet: "text-violet",
};

const toneBadge: Record<Tone, string> = {
  ink: "border-line bg-surface-2 text-ink",
  accent: "border-accent/40 bg-accent-soft text-accent",
  info: "border-info/40 bg-info-soft text-info",
  warn: "border-warn/40 bg-warn-soft text-warn",
  danger: "border-danger/40 bg-danger-soft text-danger",
  muted: "border-line bg-surface-2 text-muted",
  violet: "border-violet/40 bg-surface-2 text-violet",
};

export function Badge({
  children,
  tone = "muted",
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${toneBadge[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/**
 * The one card used for every headline number.
 * `value` should already be formatted; `unit` is rendered smaller beside it.
 */
export function MetricCard({
  label,
  value,
  unit,
  hint,
  tone = "ink",
  emphasized = false,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  tone?: Tone;
  emphasized?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 transition ${
        emphasized
          ? "border-accent/35 bg-accent-soft/30"
          : "border-line bg-surface hover:border-line/80"
      }`}
    >
      <p className="overline mb-2">{label}</p>
      <div className="flex items-baseline gap-1.5">
        <span className={`text-2xl font-semibold leading-none ${toneText[tone]}`}>
          {value}
        </span>
        {unit ? <span className="text-xs font-medium text-muted">{unit}</span> : null}
      </div>
      {hint ? <p className="mt-2 text-xs leading-relaxed text-muted">{hint}</p> : null}
    </div>
  );
}

export function Grid({
  children,
  columns = 4,
  className = "",
}: {
  children: ReactNode;
  columns?: 2 | 3 | 4 | 5;
  className?: string;
}) {
  const cols = {
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-2 lg:grid-cols-3",
    4: "sm:grid-cols-2 lg:grid-cols-4",
    5: "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5",
  }[columns];

  return <div className={`grid grid-cols-1 gap-3 ${cols} ${className}`}>{children}</div>;
}

export function KeyValue({
  items,
  columns = 2,
}: {
  items: { label: string; value: ReactNode }[];
  columns?: 1 | 2 | 3;
}) {
  const cols = { 1: "", 2: "sm:grid-cols-2", 3: "sm:grid-cols-2 lg:grid-cols-3" }[columns];

  return (
    <dl className={`grid grid-cols-1 gap-x-6 gap-y-2.5 ${cols}`}>
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">
            {item.label}
          </dt>
          <dd className="truncate text-sm text-ink" title={typeof item.value === "string" ? item.value : undefined}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ProgressBar({
  percent,
  tone = "accent",
}: {
  percent: number;
  tone?: "accent" | "info" | "warn";
}) {
  const safe = Math.max(0, Math.min(100, percent));
  const bar = { accent: "bg-accent", info: "bg-info", warn: "bg-warn" }[tone];

  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
      <div
        className={`h-full rounded-full ${bar} transition-[width] duration-300`}
        style={{ width: `${safe}%` }}
      />
    </div>
  );
}

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn" | "danger" | "accent";
  title?: string;
  children: ReactNode;
}) {
  const styles = {
    info: "border-info/40 bg-info-soft/50 text-info",
    accent: "border-accent/40 bg-accent-soft/50 text-accent",
    warn: "border-warn/40 bg-warn-soft/50 text-warn",
    danger: "border-danger/40 bg-danger-soft/50 text-danger",
  }[tone];

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${styles}`}>
      {title ? <p className="mb-1 font-semibold">{title}</p> : null}
      <div className="leading-relaxed text-ink/90">{children}</div>
    </div>
  );
}

export function EmptyState({
  title,
  message,
  icon = "◎",
}: {
  title: string;
  message: string;
  icon?: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface/50 px-6 py-10 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface-2 text-lg text-muted">
        {icon}
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">{message}</p>
    </div>
  );
}

export function CodeBlock({
  code,
  language,
  maxHeight = 320,
}: {
  code: string;
  language?: string;
  maxHeight?: number;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-canvas">
      {language ? (
        <div className="flex items-center justify-between border-b border-line bg-surface-2 px-3 py-1.5">
          <span className="overline">{language}</span>
        </div>
      ) : null}
      <pre
        className="overflow-auto p-3 font-mono text-xs leading-relaxed text-ink/90"
        style={{ maxHeight }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className={labelClass} htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint ? <p className="mt-1.5 text-xs leading-relaxed text-muted">{hint}</p> : null}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label ?? "Working…"}
    </span>
  );
}
