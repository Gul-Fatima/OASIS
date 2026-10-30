"use client";

/**
 * Workspace launcher (the home dashboard).
 *
 * Replaces the previous mock project cards. It shows the real state of the
 * four-stage workflow, one obvious next action, and the recorded decisions —
 * so the user always knows where they are without reading a page of prose.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useWorkspace, STAGES, targetName } from "@/components/workspace/WorkspaceContext";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  PageHeader,
  Spinner,
  buttonGhost,
  buttonPrimary,
  inputClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatSignedPercent, shortId } from "@/lib/format";
import type { DecisionRecord } from "@/lib/types";

export function LauncherView() {
  const router = useRouter();
  const { settings, updateSettings, scan, measure, improve, decisions, progress, recommendedStage } =
    useWorkspace();
  const [path, setPath] = useState(settings.filePath);
  const [records, setRecords] = useState<DecisionRecord[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [recordsError, setRecordsError] = useState<string | null>(null);

  useEffect(() => {
    setPath(settings.filePath);
  }, [settings.filePath]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await apiGet<{ decisions: DecisionRecord[] }>(
          "/api/candidates/history?limit=5",
        );
        if (!cancelled) setRecords(response.decisions ?? []);
      } catch (caught) {
        if (!cancelled) {
          setRecordsError(caught instanceof Error ? caught.message : String(caught));
        }
      } finally {
        if (!cancelled) setLoadingRecords(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function startScan() {
    if (!path.trim()) return;
    updateSettings({ filePath: path.trim() });
    router.push("/workspace/scan");
  }

  const nextHref = STAGES.find((stage) => stage.id === recommendedStage)?.href ?? "/workspace/scan";
  const nextTitle = STAGES.find((stage) => stage.id === recommendedStage)?.title ?? "Scan";
  const hasHistory = Boolean(scan || measure || improve);

  return (
    <>
      <PageHeader
        overline="Energy-aware code optimization"
        title="Your workspace"
        description="Four steps from hypothesis to evidence. Open any step — results carry forward."
      />

      {/* ---------------- NEXT ACTION ---------------- */}
      <div className="mb-5 rounded-xl border border-accent/35 bg-accent-soft/25 p-5 shadow-[var(--elevation)]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="overline mb-1">
              {hasHistory ? "Continue where you left off" : "Get started"}
            </p>
            <p className="text-lg font-semibold text-ink">
              {hasHistory ? `Next: ${nextTitle}` : "Scan a file for energy smells"}
            </p>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted">
              {describeNext({
                hasScan: scan !== null,
                detectionCount: scan?.detections.length ?? 0,
                hasMeasure: measure !== null,
                candidateCount: improve?.candidates.length ?? 0,
                decidedCount: Object.keys(decisions).length,
              })}
            </p>
          </div>
          <Link href={nextHref} className={buttonPrimary}>
            {hasHistory ? `Go to ${nextTitle}` : "Open scan"} →
          </Link>
        </div>
      </div>

      {/* ---------------- QUICK SCAN ---------------- */}
      <Card className="mb-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1">
            <span className="mb-1.5 block text-xs font-medium text-muted">
              File to analyze
            </span>
            <input
              className={inputClass}
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="D:/projects/my_project/main.py"
              onKeyDown={(event) => {
                if (event.key === "Enter") startScan();
              }}
            />
          </label>
          <div className="flex items-center gap-2">
            <button type="button" className={buttonPrimary} onClick={startScan} disabled={!path.trim()}>
              Scan this file
            </button>
            {scan ? (
              <Link href="/workspace/measure" className={buttonGhost}>
                Measure instead
              </Link>
            ) : null}
          </div>
        </div>
        {settings.filePath ? (
          <p className="mt-2 text-[11px] text-muted">
            Target: <span className="font-mono text-ink">{targetName(settings.filePath)}</span>
            {scan ? ` · ${scan.detections.length} findings` : ""}
          </p>
        ) : null}
      </Card>

      {/* ---------------- FOUR STAGES ---------------- */}
      <section className="mb-6">
        <div className="mb-3">
          <h2 className="text-lg font-semibold text-ink">The loop</h2>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STAGES.map((stage) => {
            const info = progress[stage.id];
            const recommended = stage.id === recommendedStage;
            return (
              <Link
                key={stage.id}
                href={stage.href}
                className={`group relative flex flex-col rounded-xl border p-4 transition hover:border-accent/50 hover:shadow-sm ${
                  recommended
                    ? "border-accent/45 bg-accent-soft/20"
                    : "border-line bg-surface"
                }`}
              >
                <div className="mb-3 flex items-center justify-between">
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold ${
                      info.state === "done"
                        ? "bg-accent text-canvas"
                        : "bg-surface-3 text-muted group-hover:text-ink"
                    }`}
                  >
                    {info.state === "done" ? "✓" : stage.number}
                  </span>
                  {recommended ? (
                    <span className="rounded-full bg-accent px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-canvas">
                      Next
                    </span>
                  ) : (
                    <span className="text-[10px] text-muted">{info.badge ?? ""}</span>
                  )}
                </div>

                <h3 className="text-sm font-semibold text-ink">{stage.title}</h3>
                <p className="mt-1 flex-1 text-xs leading-relaxed text-muted">{stage.question}</p>

                <div className="mt-3 flex items-center justify-between border-t border-line/70 pt-2.5">
                  <span className="truncate text-[11px] text-muted">{info.hint}</span>
                  <span className="text-xs font-medium text-accent group-hover:underline">
                    Open →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ---------------- RECENT DECISIONS ---------------- */}
      <Card className="!p-0">
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div>
            <h2 className="text-base font-semibold text-ink">Recent decisions</h2>
          </div>
          <Link href="/history" className="text-xs font-medium text-accent hover:underline">
            Full history →
          </Link>
        </div>

        {loadingRecords ? (
          <div className="px-5 py-6">
            <Spinner label="Loading decisions…" />
          </div>
        ) : recordsError ? (
          <div className="p-4">
            <Alert tone="warn" title="History unavailable">
              {recordsError}
            </Alert>
          </div>
        ) : records.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon="◷"
              title="No decisions recorded yet"
              message="Accept or reject a candidate in Decide to see it here."
            />
          </div>
        ) : (
          <ul className="divide-y divide-line/70">
            {records.map((record, index) => (
              <li
                key={`${record.candidate_id}-${index}`}
                className="flex flex-wrap items-center gap-3 px-5 py-3"
              >
                <span className="font-mono text-[11px] text-muted">
                  {shortId(record.candidate_id, 12)}
                </span>
                <Badge
                  tone={
                    record.status === "IMPROVED"
                      ? "accent"
                      : record.status === "NEUTRAL"
                        ? "warn"
                        : "danger"
                  }
                >
                  {record.status}
                </Badge>
                <span className="font-mono text-xs text-ink">
                  {record.measured_improvement_percent != null
                    ? formatSignedPercent(record.measured_improvement_percent)
                    : "no measurement"}
                </span>
                <Badge
                  tone={record.developer_action === "ACCEPTED" ? "accent" : "danger"}
                  className="ml-auto"
                >
                  {record.developer_action}
                </Badge>
                <span className="text-[11px] text-muted">
                  {record.recorded_at ? new Date(record.recorded_at).toLocaleString() : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

function describeNext({
  hasScan,
  detectionCount,
  hasMeasure,
  candidateCount,
  decidedCount,
}: {
  hasScan: boolean;
  detectionCount: number;
  hasMeasure: boolean;
  candidateCount: number;
  decidedCount: number;
}): string {
  if (!hasScan) {
    return "Pick a file and scan for code that likely wastes energy.";
  }
  if (!hasMeasure) {
    return `${detectionCount} finding${detectionCount === 1 ? "" : "s"}. Measure to see which ones actually cost energy.`;
  }
  if (candidateCount === 0) {
    return "Baseline recorded. Generate and measure candidate fixes.";
  }
  if (decidedCount >= candidateCount) {
    return "All decisions recorded. Apply a change and scan again.";
  }
  return `${candidateCount} candidate${candidateCount === 1 ? "" : "s"}. Review the evidence and decide.`;
}
