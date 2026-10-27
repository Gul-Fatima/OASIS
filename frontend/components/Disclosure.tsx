/**
 * Collapsible section built on native <details>, so it works without any
 * JavaScript and stays keyboard accessible.
 *
 * This is what keeps the dashboards summary-first: headline numbers stay on
 * the page and the deep tables live inside a collapsed Disclosure.
 */

import type { ReactNode } from "react";

export function Disclosure({
  title,
  summary,
  overline,
  defaultOpen = false,
  children,
}: {
  title: string;
  /** Short one-line hint shown next to the title while collapsed. */
  summary?: ReactNode;
  overline?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-xl border border-line bg-surface open:shadow-lg open:shadow-black/20"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3.5">
        <div className="min-w-0">
          {overline ? <p className="overline mb-0.5">{overline}</p> : null}
          <p className="text-sm font-semibold text-ink">{title}</p>
          {summary ? (
            <p className="mt-0.5 truncate text-xs text-muted">{summary}</p>
          ) : null}
        </div>
        <span
          aria-hidden
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-[10px] text-muted transition-transform group-open:rotate-180"
        >
          ▼
        </span>
      </summary>
      <div className="border-t border-line px-5 py-4">{children}</div>
    </details>
  );
}

/** A row of Disclosures, used for the "everything else" area of a page. */
export function DisclosureStack({ children }: { children: ReactNode }) {
  return <div className="space-y-3">{children}</div>;
}
