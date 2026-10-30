"use client";

/**
 * Dependency-free sparkline / area chart for the live energy board.
 *
 * The backend streams one snapshot per measurement, so a real chart library
 * would be overkill. This draws a normalised polyline with a gradient fill and
 * keeps the stroke width constant at any container size.
 */

import { useId } from "react";

export function Sparkline({
  values,
  height = 72,
  live = false,
  className = "",
  emptyLabel = "Waiting for the first snapshot…",
}: {
  values: number[];
  height?: number;
  live?: boolean;
  className?: string;
  emptyLabel?: string;
}) {
  const gradientId = useId().replace(/:/g, "");
  const points = values.filter((value) => Number.isFinite(value));

  if (points.length === 0) {
    return (
      <div
        className={`flex items-center justify-center rounded-lg border border-dashed border-line bg-surface-2/40 text-[11px] text-muted ${className}`}
        style={{ height }}
      >
        {emptyLabel}
      </div>
    );
  }

  const width = 100;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const pad = 8;
  const usable = 100 - pad * 2;

  const coords = points.map((value, index) => {
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = pad + (1 - (value - min) / span) * usable;
    return { x, y };
  });

  const line =
    coords.length === 1
      ? `M0,${coords[0].y} L${width},${coords[0].y}`
      : coords.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join(" ");
  const area = `${line} L${width},100 L0,100 Z`;
  const last = coords[coords.length - 1];

  return (
    <div className={`relative overflow-hidden rounded-lg border border-line bg-canvas ${className}`}>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Trend across ${points.length} measurement snapshots`}
        style={{ height, width: "100%" }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.38" />
            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#${gradientId})`} />
        <path
          d={line}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={last.x} cy={last.y} r="2.5" fill="var(--color-accent)" vectorEffect="non-scaling-stroke" />
      </svg>

      {live ? (
        <span className="absolute right-2 top-2 inline-flex items-center gap-1.5 rounded-full bg-surface/80 px-2 py-0.5 text-[10px] font-semibold text-accent backdrop-blur">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          LIVE
        </span>
      ) : null}
    </div>
  );
}
