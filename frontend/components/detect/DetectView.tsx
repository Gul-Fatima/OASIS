"use client";

/**
 * Energy smell detection — static, rule-based, mapped onto the taxonomy.
 *
 * Presented summary-first: totals and severity split on top, the individual
 * findings grouped by category inside collapsed Disclosures.
 */

import { useState } from "react";

import { Disclosure, DisclosureStack } from "@/components/Disclosure";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  Field,
  Grid,
  MetricCard,
  PageHeader,
  SectionHeader,
  Spinner,
  buttonPrimary,
  inputClass,
} from "@/components/ui";
import { apiPost } from "@/lib/api";
import { formatInteger, severityTone } from "@/lib/format";
import type { Detection, DetectionSummary } from "@/lib/types";

type DetectResponse = {
  file_path: string;
  language: string;
  line_count: number;
  function_count: number;
  class_count: number;
  loop_count: number;
  detections: Detection[];
  detection_count: number;
  detection_summary?: DetectionSummary;
  taxonomy_summary?: { categories_detected: string[]; total_categories: number };
};

const LANGUAGES = [
  { value: "auto", label: "Auto-detect" },
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "javascript", label: "JavaScript" },
  { value: "c", label: "C" },
  { value: "cpp", label: "C++" },
];

export function DetectView() {
  const [filePath, setFilePath] = useState("");
  const [language, setLanguage] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DetectResponse | null>(null);

  async function handleDetect() {
    if (!filePath.trim()) {
      setError("Enter the path to a file to analyse.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiPost<DetectResponse>("/api/detect", {
        file_path: filePath.trim(),
        language,
      });
      setResult(response);
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  // Group detections by taxonomy category for the collapsed detail sections.
  const grouped = new Map<string, { name: string; items: Detection[] }>();
  for (const detection of result?.detections ?? []) {
    const key = detection.category_id;
    const bucket = grouped.get(key) ?? {
      name: `${key} — ${detection.category_name}`,
      items: [],
    };
    bucket.items.push(detection);
    grouped.set(key, bucket);
  }

  const severity = result?.detection_summary?.by_severity ?? {};
  const high = severity.high ?? 0;
  const medium = severity.medium ?? 0;
  const low = severity.low ?? 0;

  return (
    <>
      <PageHeader
        overline="Static analysis"
        title="Energy Smell Detection"
        description="Identify code patterns that commonly waste energy, labelled with the energy smell taxonomy they belong to."
      />

      <div className="mb-5">
        <Alert tone="warn" title="A detection is a hypothesis, not proof">
          Detection is pattern matching over parsed code. It measures nothing. A
          detected smell means the code is worth investigating — the optimization
          pipeline is what turns that into evidence.
        </Alert>
      </div>

      <Card className="mb-5">
        <SectionHeader overline="New scan" title="Detect smells in a file" />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[2fr_1fr]">
          <Field label="File path" htmlFor="filePath">
            <input
              id="filePath"
              className={inputClass}
              value={filePath}
              onChange={(event) => setFilePath(event.target.value)}
              placeholder="D:/projects/my_project/main.py"
              disabled={loading}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleDetect();
              }}
            />
          </Field>

          <Field label="Language" htmlFor="language">
            <select
              id="language"
              className={inputClass}
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              disabled={loading}
            >
              {LANGUAGES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <button
            type="button"
            className={buttonPrimary}
            onClick={handleDetect}
            disabled={loading}
          >
            ⚠ Detect energy smells
          </button>
          {loading ? <Spinner label="Scanning file…" /> : null}
        </div>
      </Card>

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Detection failed">
            {error}
          </Alert>
        </div>
      ) : null}

      {!result && !loading ? (
        <EmptyState
          icon="⚠"
          title="No scan yet"
          message="Point at a file to see which energy smells the detector finds. Every finding names the taxonomy subcategory it maps to."
        />
      ) : null}

      {result ? (
        <>
          <section className="mb-5">
            <SectionHeader
              overline="Summary"
              title="Detection results"
              actions={<Badge tone="info">{result.language.toUpperCase()}</Badge>}
            />

            <Grid columns={4}>
              <MetricCard
                label="Detections"
                value={formatInteger(result.detection_count)}
                tone={result.detection_count > 0 ? "warn" : "accent"}
                emphasized
                hint={`${result.taxonomy_summary?.categories_detected?.length ?? 0} categor${
                  (result.taxonomy_summary?.categories_detected?.length ?? 0) === 1
                    ? "y"
                    : "ies"
                } involved`}
              />
              <MetricCard
                label="High severity"
                value={formatInteger(high)}
                tone={high > 0 ? "danger" : "muted"}
                hint="Likely to matter; inspect first"
              />
              <MetricCard
                label="Medium / low"
                value={`${medium} / ${low}`}
                tone="info"
                hint="Worth reviewing when measuring"
              />
              <MetricCard
                label="File size"
                value={formatInteger(result.line_count)}
                unit="lines"
                hint={`${result.function_count} functions · ${result.class_count} classes · ${result.loop_count} loops`}
              />
            </Grid>
          </section>

          {result.detection_count === 0 ? (
            <EmptyState
              icon="✓"
              title="No energy smells detected"
              message="The detector found none of its known patterns in this file. That is not proof the code is efficient — it only means it does not match these rules."
            />
          ) : (
            <section className="mb-8">
              <SectionHeader
                overline="Findings"
                title="Grouped by category"
                description="Collapsed by default. Each finding names the rule that matched, its location and a suggested direction."
              />

              <DisclosureStack>
                {[...grouped.entries()].map(([categoryId, bucket]) => (
                  <Disclosure
                    key={categoryId}
                    overline={categoryId}
                    title={bucket.name.split(" — ")[1] ?? bucket.name}
                    summary={`${bucket.items.length} finding(s)`}
                  >
                    <div className="space-y-3">
                      {bucket.items.map((detection, index) => (
                        <div
                          key={`${detection.subcategory_id}-${index}`}
                          className="rounded-lg border border-line bg-surface-2/60 p-4"
                        >
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <Badge tone="violet">{detection.subcategory_id}</Badge>
                            <span className="text-sm font-semibold text-ink">
                              {detection.subcategory_name}
                            </span>
                            <span
                              className={`text-[11px] font-semibold uppercase ${severityTone(
                                detection.severity,
                              )}`}
                            >
                              {detection.severity}
                            </span>
                            <span className="ml-auto font-mono text-[11px] text-muted">
                              {detection.location?.function
                                ? `${detection.location.function}:`
                                : ""}
                              {detection.location?.line ?? "—"}
                            </span>
                          </div>

                          <p className="text-xs leading-relaxed text-ink/90">
                            {detection.description}
                          </p>

                          {detection.suggestion ? (
                            <p className="mt-2 rounded border border-accent/25 bg-accent-soft/40 px-3 py-2 text-xs leading-relaxed text-ink/90">
                              <span className="font-semibold text-accent">
                                Suggested direction:{" "}
                              </span>
                              {detection.suggestion}
                            </p>
                          ) : null}

                          {detection.evidence ? (
                            <p className="mt-2 text-[11px] text-muted">
                              Evidence: {detection.evidence} — no energy was measured
                              for this finding.
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </Disclosure>
                ))}
              </DisclosureStack>
            </section>
          )}
        </>
      ) : null}
    </>
  );
}
