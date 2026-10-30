"use client";

/**
 * Stage 1 — Scan.
 *
 * Answers "where could this code waste energy?" with an interactive findings
 * list instead of a static report, and hands the user to Measure with the
 * result already stored.
 */

import Link from "next/link";
import { useState } from "react";

import { FindingsExplorer } from "@/components/workspace/FindingsExplorer";
import { StageHeader, StageSteps, GuidanceBar, WorkspaceBar } from "@/components/workspace/StageChrome";
import { useWorkspace, targetName } from "@/components/workspace/WorkspaceContext";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  Grid,
  MetricCard,
  Spinner,
  buttonPrimary,
  inputClass,
} from "@/components/ui";
import { apiPost } from "@/lib/api";
import { formatInteger } from "@/lib/format";
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

export function ScanView() {
  const { settings, updateSettings, scan, setScan } = useWorkspace();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleScan() {
    const target = settings.filePath.trim();
    if (!target) {
      setError("Enter the path to a file to scan.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiPost<DetectResponse>("/api/detect", {
        file_path: target,
        language: settings.language,
      });

      setScan({
        filePath: response.file_path,
        language: response.language,
        lineCount: response.line_count,
        functionCount: response.function_count,
        classCount: response.class_count,
        loopCount: response.loop_count,
        detections: response.detections ?? [],
        summary: response.detection_summary ?? null,
        scannedAt: new Date().toISOString(),
      });
      updateSettings({ filePath: response.file_path, language: response.language });
    } catch (caught) {
      setScan(null);
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  const severity = scan?.summary?.by_severity ?? {};
  const high = severity.high ?? 0;
  const medium = severity.medium ?? 0;
  const low = severity.low ?? 0;
  const count = scan?.detections.length ?? 0;

  return (
    <>
      <StageHeader
        stage="scan"
        title="Scan for energy smells"
        description="Static patterns that commonly waste energy. Nothing runs yet."
      />
      <StageSteps current="scan" />
      <WorkspaceBar disabled={loading} />

      {scan && count > 0 ? (
        <GuidanceBar
          message={
            <>
              <strong>{count}</strong> smell{count === 1 ? "" : "s"}, <strong>{high}</strong>{" "}
              high severity. Measure to see which ones cost real energy.
            </>
          }
          action={
            <Link href="/workspace/measure" className={buttonPrimary}>
              Measure energy →
            </Link>
          }
        />
      ) : scan ? (
        <GuidanceBar
          tone="warn"
          eyebrow="Nothing matched"
          message="No known pattern matched. You can still measure what this file consumes."
          action={
            <Link href="/workspace/measure" className={buttonPrimary}>
              Measure anyway →
            </Link>
          }
        />
      ) : (
        <GuidanceBar
          tone="info"
          eyebrow="Start here"
          message="Pick a file to get a list of energy smells."
        />
      )}

      <Card className="mb-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1">
            <span className="mb-1.5 block text-xs font-medium text-muted">File path</span>
            <input
              className={inputClass}
              value={settings.filePath}
              onChange={(event) => updateSettings({ filePath: event.target.value })}
              placeholder="D:/projects/my_project/main.py"
              disabled={loading}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleScan();
              }}
            />
          </label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className={buttonPrimary}
              onClick={() => void handleScan()}
              disabled={loading}
            >
              {scan ? "Re-scan" : "Run scan"}
            </button>
            <label className="sr-only" htmlFor="scan-language">
              Language
            </label>
            <select
              id="scan-language"
              className={`${inputClass} w-auto`}
              value={settings.language}
              onChange={(event) => updateSettings({ language: event.target.value })}
              disabled={loading}
            >
              <option value="auto">Auto-detect</option>
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="javascript">JavaScript</option>
              <option value="c">C</option>
              <option value="cpp">C++</option>
            </select>
          </div>
        </div>

      </Card>

      {loading ? (
        <div className="mb-5 rounded-xl border border-line bg-surface px-4 py-3">
          <Spinner label="Parsing the file and checking the rule base…" />
        </div>
      ) : null}

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Scan failed">
            {error}
          </Alert>
        </div>
      ) : null}

      {!scan && !loading ? (
        <EmptyState
          icon="◎"
          title="No scan yet"
          message="Run a scan to see energy smells by category."
        />
      ) : null}

      {scan ? (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="overline mb-0.5">Scan results</p>
              <h2 className="text-lg font-semibold text-ink">
                {targetName(scan.filePath) || scan.filePath}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="info">{scan.language.toUpperCase()}</Badge>
              <Badge tone={count > 0 ? "warn" : "accent"}>
                {count} detection{count === 1 ? "" : "s"}
              </Badge>
            </div>
          </div>

          <Grid columns={4} className="mb-5">
            <MetricCard
              label="Detections"
              value={formatInteger(count)}
              tone={count > 0 ? "warn" : "accent"}
              emphasized
              hint={`${scan.summary?.categories_detected?.length ?? 0} categories involved`}
            />
            <MetricCard
              label="High severity"
              value={formatInteger(high)}
              tone={high > 0 ? "danger" : "muted"}
              hint="Inspect these first"
            />
            <MetricCard
              label="Medium / low"
              value={`${medium} / ${low}`}
              tone="info"
              hint="Confirm with a measurement"
            />
            <MetricCard
              label="File size"
              value={formatInteger(scan.lineCount)}
              unit="lines"
              hint={`${scan.functionCount} functions · ${scan.classCount} classes · ${scan.loopCount} loops`}
            />
          </Grid>

          {count === 0 ? (
            <EmptyState
              icon="✓"
              title="No energy smells detected"
              message="No known pattern matched. The rules only cover known shapes."
            />
          ) : (
            <section>
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold text-ink">Findings</h2>
                </div>
                <Link
                  href="/taxonomy"
                  className="text-xs font-medium text-accent hover:underline"
                >
                  What do these categories mean? →
                </Link>
              </div>
              <FindingsExplorer
                detections={scan.detections}
                copySource={targetName(scan.filePath) || scan.filePath}
              />
            </section>
          )}
        </>
      ) : null}
    </>
  );
}
