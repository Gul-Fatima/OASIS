"use client";

/**
 * Stage 2 — Measure.
 *
 * The live board: while the tracker streams snapshots, the numbers, chart and
 * power bars move. When the run finishes the baseline is kept in the shared
 * workspace so later stages can refer to it without re-running anything.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Disclosure, DisclosureStack } from "@/components/Disclosure";
import { Sparkline } from "@/components/workspace/Sparkline";
import { GuidanceBar, StageHeader, StageSteps, WorkspaceBar } from "@/components/workspace/StageChrome";
import { useWorkspace, targetName } from "@/components/workspace/WorkspaceContext";
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  KeyValue,
  Spinner,
  buttonDanger,
  buttonGhost,
  buttonPrimary,
  inputClass,
} from "@/components/ui";
import { apiPost, streamPost, type StreamEvent } from "@/lib/api";
import {
  formatCo2,
  formatDuration,
  formatElapsed,
  formatEnergy,
  formatWatts,
} from "@/lib/format";
import type { EnergySnapshot } from "@/lib/types";

export function MeasureView() {
  const { settings, updateSettings, scan, measure, setMeasure, improve } = useWorkspace();

  const [running, setRunning] = useState(false);
  const [percent, setPercent] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [statusText, setStatusText] = useState("Ready to measure");
  const [log, setLog] = useState<string[]>([]);
  const [snapshots, setSnapshots] = useState<EnergySnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  // Sensible default: the folder containing the file that was scanned.
  useEffect(() => {
    if (settings.projectPath || !scan?.filePath) return;
    const folder = scan.filePath.replace(/[\\/][^\\/]*$/, "");
    if (folder && folder !== scan.filePath) updateSettings({ projectPath: folder });
  }, [scan?.filePath, settings.projectPath, updateSettings]);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [log]);

  function appendLog(message: string) {
    if (!message) return;
    setLog((previous) => [...previous, message].slice(-200));
  }

  async function handleRun() {
    if (!settings.projectPath.trim() || !settings.command.trim()) {
      setError("A project path and an execution command are both required.");
      return;
    }

    setRunning(true);
    setError(null);
    setPercent(0);
    setElapsed(0);
    setLog([]);
    setSnapshots([]);
    setStatusText(settings.continuous ? "Starting monitored run…" : "Starting measurement…");

    const controller = new AbortController();
    controllerRef.current = controller;
    const collected: EnergySnapshot[] = [];

    try {
      await streamPost(
        "/api/energy/estimate/stream",
        {
          project_path: settings.projectPath.trim(),
          command: settings.command.trim(),
          timeout: Number(settings.timeout) || 300,
          continuous: settings.continuous,
          interval_seconds: 10,
        },
        (event: StreamEvent) => {
          const snapshot = event as EnergySnapshot;

          if (snapshot.error) throw new Error(String(snapshot.error));

          if (snapshot.execution_status === "measuring" && !snapshot.final) {
            setPercent((value) => Math.min(95, Math.max(value, 5) + 2));
            setStatusText(
              snapshot.process_running
                ? "Process is running — measuring…"
                : "Waiting for the process to finish…",
            );
            return;
          }

          collected.push(snapshot);
          setSnapshots([...collected]);

          if (snapshot.final) {
            setPercent(100);
            setStatusText("Measurement complete");
            setMeasure({
              baseline: snapshot,
              snapshots: [...collected],
              measuredAt: new Date().toISOString(),
            });
            appendLog(
              `Final: ${formatEnergy(snapshot.energy_consumed)} · ` +
                `${formatCo2(snapshot.emissions)} · ` +
                `${formatDuration(snapshot.execution_time_seconds)}`,
            );
          } else {
            setPercent((value) => Math.min(92, Math.max(value, 10) + 5));
            setStatusText(`Monitoring — snapshot #${snapshot.snapshot_index ?? "?"}`);
            appendLog(
              `Snapshot #${snapshot.snapshot_index ?? "?"}: ` +
                `${formatEnergy(snapshot.energy_consumed)} · ` +
                `${formatDuration(snapshot.execution_time_seconds)}`,
            );
          }
        },
        controller.signal,
      );
    } catch (caught) {
      if (controller.signal.aborted) {
        setStatusText("Stopped");
        appendLog("Run stopped by user.");
      } else {
        const message = caught instanceof Error ? caught.message : String(caught);
        setError(message);
        setStatusText("Measurement failed");
        appendLog(`ERROR: ${message}`);
      }
    } finally {
      controllerRef.current = null;
      setRunning(false);
    }
  }

  async function handleStop() {
    try {
      await apiPost("/api/energy/stop");
      appendLog("Stop requested — waiting for the tracker to flush…");
    } catch (caught) {
      appendLog(`Stop failed: ${caught instanceof Error ? caught.message : String(caught)}`);
    }
  }

  const baseline = measure?.baseline ?? null;
  const chartSnapshots = running ? snapshots : (measure?.snapshots ?? snapshots);
  const latest = chartSnapshots[chartSnapshots.length - 1] ?? baseline;

  const series = pickSeries(chartSnapshots);

  return (
    <>
      <StageHeader
        stage="measure"
        title="Measure real energy use"
        description="Run the project under CodeCarbon. This baseline is what candidates are compared against."
      />
      <StageSteps current="measure" />
      <WorkspaceBar disabled={running} />

      {baseline && !running ? (
        <GuidanceBar
          message={
            <>
              Baseline: <strong>{formatEnergy(baseline.energy_consumed)}</strong> over{" "}
              <strong>{formatDuration(baseline.execution_time_seconds)}</strong>. Generate
              candidate fixes next.
            </>
          }
          action={
            <Link href="/workspace/improve" className={buttonPrimary}>
              Generate candidates →
            </Link>
          }
        />
      ) : (
        <GuidanceBar
          tone={running ? "info" : "muted"}
          eyebrow={running ? "Measuring" : "Before you start"}
          message={
            running
              ? "Leave the machine idle where possible — background load is measured too."
              : "Choose the project and the command that runs it."
          }
          action={
            scan ? (
              <Link href="/workspace/scan" className={buttonGhost}>
                Back to scan
              </Link>
            ) : undefined
          }
        />
      )}

      <Card className="mb-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-muted">Project path</span>
            <input
              className={inputClass}
              value={settings.projectPath}
              onChange={(event) => updateSettings({ projectPath: event.target.value })}
              placeholder="D:/projects/my_project"
              disabled={running}
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-muted">Execution command</span>
            <input
              className={inputClass}
              value={settings.command}
              onChange={(event) => updateSettings({ command: event.target.value })}
              placeholder="python main.py"
              disabled={running}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !running) void handleRun();
              }}
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-muted">
              Timeout / monitor duration (s)
            </span>
            <input
              type="number"
              min={10}
              className={inputClass}
              value={settings.timeout}
              onChange={(event) => updateSettings({ timeout: Number(event.target.value) })}
              disabled={running}
            />
          </label>

          <label className="flex cursor-pointer items-start gap-2.5 self-end text-sm text-ink">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
              checked={settings.continuous}
              onChange={(event) => updateSettings({ continuous: event.target.checked })}
              disabled={running}
            />
            <span>
              Continuous mode
              <span className="mt-0.5 block text-xs text-muted">
                For servers and processes that never exit.
              </span>
            </span>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={buttonPrimary}
            onClick={() => void handleRun()}
            disabled={running}
          >
            {running ? "Measuring…" : baseline ? "Re-measure" : "Run measurement"}
          </button>
          <button
            type="button"
            className={buttonDanger}
            onClick={() => void handleStop()}
            disabled={!running || !settings.continuous}
            title={settings.continuous ? "Stop the run" : "Stop is available in continuous mode"}
          >
            ■ Stop
          </button>
          {running ? (
            <Spinner label={statusText} />
          ) : (
            <span className="text-xs text-muted">{statusText}</span>
          )}
        </div>

        {running || log.length > 0 ? (
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between text-[11px] text-muted">
              <span>{statusText}</span>
              <span className="font-mono">
                {Math.round(percent)}% · {formatElapsed(elapsed)}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-300"
                style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
              />
            </div>
          </div>
        ) : null}
      </Card>

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Measurement failed">
            {error}
          </Alert>
        </div>
      ) : null}

      {/* ---------------- LIVE / BASELINE BOARD ---------------- */}
      {!baseline && !running ? (
        <EmptyState
          icon="⚡"
          title="Nothing measured yet"
          message="Start a measurement to see live energy and power."
        />
      ) : (
        <Card className="mb-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="overline mb-0.5">{running ? "Live measurement" : "Recorded baseline"}</p>
              <p className="text-sm font-semibold text-ink">
                {targetName(settings.projectPath) || settings.projectPath || "Current run"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {running ? (
                <Badge tone="accent">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                  Live
                </Badge>
              ) : (
                <Badge
                  tone={
                    baseline?.execution_status === "success"
                      ? "accent"
                      : baseline?.execution_status === "failed"
                        ? "danger"
                        : "warn"
                  }
                >
                  {(baseline?.execution_status ?? "recorded").toUpperCase()}
                </Badge>
              )}
              <span className="font-mono text-[11px] text-muted">
                {chartSnapshots.length} snapshot{chartSnapshots.length === 1 ? "" : "s"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <div>
              <p className="overline">Energy consumed</p>
              <div className="mt-1 flex items-baseline gap-2">
                <span
                  className={`text-4xl font-semibold tracking-tight ${
                    running ? "animate-pulse text-accent" : "text-accent"
                  }`}
                >
                  {running && latest?.energy_consumed == null
                    ? "—"
                    : formatEnergy(latest?.energy_consumed ?? baseline?.energy_consumed)}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted">
                {formatCo2(latest?.emissions ?? baseline?.emissions)} ·{" "}
                {formatDuration(latest?.execution_time_seconds ?? baseline?.execution_time_seconds)}{" "}
                elapsed
                {running ? ` · ${formatElapsed(elapsed)} watching` : ""}
              </p>

              <div className="mt-4 space-y-2">
                <PowerRow
                  label="CPU"
                  value={latest?.cpu_power ?? 0}
                  max={Math.max(
                    latest?.cpu_power ?? 0,
                    latest?.gpu_power ?? 0,
                    latest?.ram_power ?? 0,
                    1,
                  )}
                  className="bg-accent"
                />
                <PowerRow
                  label="GPU"
                  value={latest?.gpu_power ?? 0}
                  max={Math.max(
                    latest?.cpu_power ?? 0,
                    latest?.gpu_power ?? 0,
                    latest?.ram_power ?? 0,
                    1,
                  )}
                  className="bg-info"
                />
                <PowerRow
                  label="RAM"
                  value={latest?.ram_power ?? 0}
                  max={Math.max(
                    latest?.cpu_power ?? 0,
                    latest?.gpu_power ?? 0,
                    latest?.ram_power ?? 0,
                    1,
                  )}
                  className="bg-violet"
                />
              </div>
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <p className="overline">{series.label}</p>
                <p className="text-[11px] text-muted">{series.hint}</p>
              </div>
              <Sparkline values={series.values} live={running} height={112} />
            </div>
          </div>
        </Card>
      )}

      {log.length > 0 ? (
        <DisclosureStack>
          <Disclosure
            title="Measurement log"
            overline="Event stream"
            summary={`${log.length} line(s) from this run`}
          >
            <div
              ref={logRef}
              className="max-h-60 overflow-y-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-muted"
            >
              {log.map((line, index) => (
                <div key={`${index}-${line.slice(0, 12)}`}>{line}</div>
              ))}
            </div>
          </Disclosure>

          {baseline ? (
            <>
              <Disclosure
                title="Power & resource breakdown"
                overline="CPU · GPU · RAM"
                summary={`CPU ${formatWatts(baseline.cpu_power)} · RAM ${formatWatts(
                  baseline.ram_power,
                )} · GPU ${formatWatts(baseline.gpu_power)}`}
              >
                <KeyValue
                  columns={3}
                  items={[
                    { label: "CPU energy", value: formatEnergy(baseline.cpu_energy) },
                    { label: "GPU energy", value: formatEnergy(baseline.gpu_energy) },
                    { label: "RAM energy", value: formatEnergy(baseline.ram_energy) },
                    { label: "CPU power", value: formatWatts(baseline.cpu_power) },
                    { label: "GPU power", value: formatWatts(baseline.gpu_power) },
                    { label: "RAM power", value: formatWatts(baseline.ram_power) },
                    { label: "Water", value: baseline.water_consumed != null ? `${baseline.water_consumed} L` : "—" },
                    { label: "Run id", value: baseline.run_id ?? "—" },
                    { label: "Timestamp", value: baseline.timestamp ?? "—" },
                  ]}
                />
              </Disclosure>

              <Disclosure
                title="Process output"
                overline="stdout / stderr"
                summary="Console output captured during execution"
              >
                <div className="space-y-3">
                  <div>
                    <p className="overline mb-1.5">stdout</p>
                    <pre className="max-h-52 overflow-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-ink/90">
                      {baseline.stdout?.trim() || "(empty)"}
                    </pre>
                  </div>
                  <div>
                    <p className="overline mb-1.5">stderr</p>
                    <pre className="max-h-52 overflow-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-ink/90">
                      {baseline.stderr?.trim() || "(empty)"}
                    </pre>
                  </div>
                </div>
              </Disclosure>
            </>
          ) : null}
        </DisclosureStack>
      ) : null}

      {baseline && improve ? (
        <p className="mt-4 text-xs text-muted">
          Candidates already exist for this workspace —{" "}
          <Link href="/workspace/improve" className="font-medium text-accent hover:underline">
            review them
          </Link>
          .
        </p>
      ) : null}
    </>
  );
}

function pickSeries(snapshots: EnergySnapshot[]): {
  values: number[];
  label: string;
  hint: string;
} {
  const list = snapshots.slice(-60);

  if (list.some((snapshot) => typeof snapshot.cpu_power === "number")) {
    return { values: list.map((snapshot) => snapshot.cpu_power ?? 0), label: "CPU power", hint: "watts" };
  }
  if (list.some((snapshot) => typeof snapshot.energy_consumed === "number")) {
    return {
      values: list.map((snapshot) => snapshot.energy_consumed ?? 0),
      label: "Energy per snapshot",
      hint: "kWh",
    };
  }
  return {
    values: list.map((snapshot) => snapshot.execution_time_seconds ?? 0),
    label: "Elapsed per snapshot",
    hint: "seconds",
  };
}

function PowerRow({
  label,
  value,
  max,
  className,
}: {
  label: string;
  value: number;
  max: number;
  className: string;
}) {
  const width = Math.max(0, Math.min(100, (value / (max || 1)) * 100));
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-8 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-muted">
        {label}
      </span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
        <span
          className={`block h-full rounded-full transition-[width] duration-500 ${className}`}
          style={{ width: `${width}%` }}
        />
      </span>
      <span className="w-16 shrink-0 text-right font-mono text-[10px] text-muted">
        {formatWatts(value)}
      </span>
    </div>
  );
}
