/** Display helpers. Kept dumb so components stay readable. */

const KWH_TO_JOULES = 3.6e6;

export function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatNumber(
  value: unknown,
  options: Intl.NumberFormatOptions = {},
): string {
  if (!isNumber(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
}

export function formatInteger(value: unknown): string {
  return formatNumber(value, { maximumFractionDigits: 0 });
}

/**
 * Energy is reported by CodeCarbon in kWh, which is tiny per run. Show kWh for
 * anything meaningful and fall back to joules so a run is never displayed as
 * a flat "0".
 */
export function formatEnergy(kwh: unknown): string {
  if (!isNumber(kwh)) return "—";
  const joules = kwh * KWH_TO_JOULES;

  if (joules === 0) return "0 J";
  if (joules < 1) {
    return `${formatNumber(joules * 1000, { maximumFractionDigits: 4 })} mJ`;
  }
  if (joules < 1000) {
    return `${formatNumber(joules, { maximumFractionDigits: 3 })} J`;
  }
  if (kwh >= 0.001) {
    return `${formatNumber(kwh, { maximumFractionDigits: 6 })} kWh`;
  }
  return `${formatNumber(joules, { maximumFractionDigits: 1 })} J`;
}

export function formatWatts(value: unknown): string {
  if (!isNumber(value)) return "—";
  if (value >= 1000) return `${formatNumber(value / 1000, { maximumFractionDigits: 2 })} kW`;
  if (value < 1) return `${formatNumber(value * 1000, { maximumFractionDigits: 1 })} mW`;
  return `${formatNumber(value, { maximumFractionDigits: 2 })} W`;
}

/** Energy given in joules (benchmark comparisons). */
export function formatJoules(joules: unknown): string {
  if (!isNumber(joules)) return "—";
  return formatEnergy(joules / KWH_TO_JOULES);
}

export function formatDuration(seconds: unknown): string {
  if (!isNumber(seconds)) return "—";
  if (seconds < 1) return `${formatNumber(seconds * 1000, { maximumFractionDigits: 0 })} ms`;
  if (seconds < 60) return `${formatNumber(seconds, { maximumFractionDigits: 2 })} s`;

  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes}m ${rest}s`;

  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export function formatPercent(value: unknown, digits = 2): string {
  if (!isNumber(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

/** Signed percentage, for before/after deltas. */
export function formatSignedPercent(value: unknown, digits = 2): string {
  if (!isNumber(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatCo2(kg: unknown): string {
  if (!isNumber(kg)) return "—";
  if (kg === 0) return "0 kg";
  if (kg < 1e-6) return `${formatNumber(kg * 1e6, { maximumFractionDigits: 3 })} mg CO₂e`;
  if (kg < 1e-3) return `${formatNumber(kg * 1e6, { maximumFractionDigits: 1 })} mg CO₂e`;
  if (kg < 1) return `${formatNumber(kg * 1000, { maximumFractionDigits: 3 })} g CO₂e`;
  return `${formatNumber(kg, { maximumFractionDigits: 4 })} kg CO₂e`;
}

export function truncate(text: unknown, limit = 80): string {
  if (typeof text !== "string") return "—";
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}

export function shortId(id: unknown, length = 10): string {
  if (typeof id !== "string") return "—";
  return id.length > length ? `${id.slice(0, length)}…` : id;
}

/** Tailwind text colour for a final optimization status. */
export function statusTone(status?: string | null): string {
  switch ((status ?? "").toUpperCase()) {
    case "IMPROVED":
    case "VERIFIED":
    case "MEASURED":
    case "SUCCESS":
    case "ACCEPTED":
      return "text-accent";
    case "NEUTRAL":
    case "BENCHMARK_PENDING":
    case "VERIFICATION_PENDING":
    case "PREDICTED":
    case "GENERATED":
    case "MONITORING":
      return "text-warn";
    case "REGRESSED":
    case "FAILED":
    case "VERIFICATION_FAILED":
    case "BENCHMARK_FAILED":
    case "REJECTED":
      return "text-danger";
    default:
      return "text-muted";
  }
}

export function severityTone(severity?: string | null): string {
  switch ((severity ?? "").toLowerCase()) {
    case "high":
      return "text-danger";
    case "medium":
      return "text-warn";
    case "low":
      return "text-info";
    default:
      return "text-muted";
  }
}
