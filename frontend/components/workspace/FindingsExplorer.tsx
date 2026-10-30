"use client";

/**
 * Interactive findings list.
 *
 * The detection page used to render a stack of collapsed cards — a report you
 * scrolled past. This is a work surface: filter by severity or category, search
 * by function, sort, open one finding at a time, and copy the whole set out.
 */

import { useMemo, useState } from "react";

import { Badge, inputClass } from "@/components/ui";
import { severityTone } from "@/lib/format";
import type { Detection } from "@/lib/types";

type SeverityFilter = "all" | "high" | "medium" | "low";
type SortKey = "severity" | "line" | "category";

const SEVERITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

function locationLabel(detection: Detection): string {
  const fn = detection.location?.function;
  const line = detection.location?.line;
  if (fn && line) return `${fn}():${line}`;
  if (fn) return `${fn}()`;
  if (line) return `line ${line}`;
  return "—";
}

export function FindingsExplorer({
  detections,
  copySource,
}: {
  detections: Detection[];
  copySource?: string;
}) {
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("severity");
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const [copied, setCopied] = useState(false);

  const counts = useMemo(() => {
    const base = { all: detections.length, high: 0, medium: 0, low: 0 };
    for (const detection of detections) {
      const key = (detection.severity ?? "").toLowerCase();
      if (key === "high" || key === "medium" || key === "low") base[key] += 1;
    }
    return base;
  }, [detections]);

  const categories = useMemo(() => {
    const map = new Map<string, string>();
    for (const detection of detections) {
      map.set(detection.category_id, detection.category_name);
    }
    return [...map.entries()];
  }, [detections]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = detections.filter((detection) => {
      if (severity !== "all" && (detection.severity ?? "").toLowerCase() !== severity) {
        return false;
      }
      if (category !== "all" && detection.category_id !== category) return false;
      if (!needle) return true;
      const haystack = [
        detection.subcategory_name,
        detection.subcategory_id,
        detection.category_name,
        detection.description,
        detection.location?.function,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });

    return filtered.sort((a, b) => {
      if (sort === "line") {
        return (a.location?.line ?? Infinity) - (b.location?.line ?? Infinity);
      }
      if (sort === "category") {
        return a.category_id.localeCompare(b.category_id);
      }
      return (
        (SEVERITY_RANK[(a.severity ?? "").toLowerCase()] ?? 9) -
        (SEVERITY_RANK[(b.severity ?? "").toLowerCase()] ?? 9)
      );
    });
  }, [detections, severity, category, query, sort]);

  async function copyReport() {
    const lines = visible.map((detection, index) => {
      const head = `${index + 1}. [${detection.severity.toUpperCase()}] ${detection.subcategory_id} — ${
        detection.subcategory_name
      } (${locationLabel(detection)})`;
      const body = [detection.description, detection.suggestion ? `Fix: ${detection.suggestion}` : null]
        .filter(Boolean)
        .join("\n   ");
      return `${head}\n   ${body}`;
    });

    const text = [
      `Energy smell report${copySource ? ` — ${copySource}` : ""}`,
      `${visible.length} finding(s), ${counts.high} high severity`,
      "",
      ...lines,
    ].join("\n");

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable; the list is still on screen */
    }
  }

  if (detections.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface">
      {/* ---------------- FILTER BAR ---------------- */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-surface-2/40 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {(["all", "high", "medium", "low"] as SeverityFilter[]).map((key) => {
            const active = severity === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setSeverity(key)}
                aria-pressed={active}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize transition ${
                  active
                    ? "border-accent/50 bg-accent-soft text-accent"
                    : "border-line bg-surface text-muted hover:text-ink"
                }`}
              >
                {key === "all" ? "All" : key}
                <span className="ml-1.5 opacity-70">{counts[key]}</span>
              </button>
            );
          })}
        </div>

        <select
          aria-label="Filter by category"
          className={`${inputClass} ml-auto w-auto max-w-[15rem] py-1.5 text-xs`}
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="all">All categories</option>
          {categories.map(([id, name]) => (
            <option key={id} value={id}>
              {id} — {name}
            </option>
          ))}
        </select>

        <input
          aria-label="Search findings"
          className={`${inputClass} w-40 py-1.5 text-xs`}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search…"
        />

        <select
          aria-label="Sort findings"
          className={`${inputClass} w-auto py-1.5 text-xs`}
          value={sort}
          onChange={(event) => setSort(event.target.value as SortKey)}
        >
          <option value="severity">Severity</option>
          <option value="line">Line number</option>
          <option value="category">Category</option>
        </select>

        <button
          type="button"
          onClick={() => void copyReport()}
          className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[11px] font-medium text-muted transition hover:border-accent/40 hover:text-accent"
        >
          {copied ? "✓ Copied" : "Copy report"}
        </button>
      </div>

      {/* ---------------- ROWS ---------------- */}
      <ul className="divide-y divide-line/70">
        {visible.map((detection, index) => {
          const expanded = openIndex === index;
          const tone = severityTone(detection.severity);
          const bar =
            (detection.severity ?? "").toLowerCase() === "high"
              ? "bg-danger"
              : (detection.severity ?? "").toLowerCase() === "medium"
                ? "bg-warn"
                : "bg-info";

          return (
            <li key={`${detection.subcategory_id}-${index}`} className="relative">
              <span className={`absolute inset-y-0 left-0 w-0.5 ${bar}`} aria-hidden />
              <button
                type="button"
                onClick={() => setOpenIndex(expanded ? null : index)}
                aria-expanded={expanded}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-surface-2/50"
              >
                <span className={`w-12 shrink-0 text-[10px] font-bold uppercase tracking-wide ${tone}`}>
                  {detection.severity}
                </span>
                <Badge tone="violet" className="shrink-0">
                  {detection.subcategory_id}
                </Badge>
                <span className="min-w-0 flex-1 truncate text-sm text-ink">
                  {detection.subcategory_name}
                </span>
                <span className="hidden shrink-0 font-mono text-[11px] text-muted sm:block">
                  {locationLabel(detection)}
                </span>
                <span
                  aria-hidden
                  className={`shrink-0 text-[10px] text-muted transition-transform ${expanded ? "rotate-180" : ""}`}
                >
                  ▼
                </span>
              </button>

              {expanded ? (
                <div className="border-t border-line/50 bg-surface-2/30 px-4 py-3 pl-5">
                  <p className="text-xs leading-relaxed text-ink/90">{detection.description}</p>
                  {detection.suggestion ? (
                    <div className="mt-2.5 rounded-lg border border-accent/25 bg-accent-soft/40 px-3 py-2">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-accent">
                        Suggested direction
                      </p>
                      <p className="mt-0.5 text-xs leading-relaxed text-ink/90">
                        {detection.suggestion}
                      </p>
                    </div>
                  ) : null}
                  {detection.evidence ? (
                    <p className="mt-2 rounded border border-line bg-canvas/60 px-3 py-1.5 font-mono text-[11px] leading-relaxed text-muted">
                      {detection.evidence}
                    </p>
                  ) : null}
                  <p className="mt-2 text-[11px] text-muted/80">
                    {detection.category_id} · {detection.category_name}
                  </p>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      {visible.length === 0 ? (
        <div className="px-4 py-8 text-center text-xs text-muted">
          No findings match this filter.{" "}
          <button
            type="button"
            className="font-semibold text-accent hover:underline"
            onClick={() => {
              setSeverity("all");
              setCategory("all");
              setQuery("");
            }}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="border-t border-line bg-surface-2/30 px-4 py-2 text-[11px] text-muted">
          Showing {visible.length} of {detections.length} findings
        </div>
      )}
    </div>
  );
}
