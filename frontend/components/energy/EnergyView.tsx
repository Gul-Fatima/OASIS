"use client";

/**
 * Energy measurement dashboard (CodeCarbon).
 *
 * Same layout rule as the analysis page: measured headline numbers on top,
 * tracker internals and raw payloads behind Disclosures.
 */

import { useEffect, useRef, useState } from "react";

import { Disclosure, DisclosureStack } from "@/components/Disclosure";
import {
  Alert,
  Badge,
  Card,
  CodeBlock,
  EmptyState,
  Field,
  Grid,
  KeyValue,
  MetricCard,
  PageHeader,
  ProgressBar,
  SectionHeader,
  Spinner,
  buttonDanger,
  buttonPrimary,
  inputClass,
} from "@/components/ui";
import { apiPost, streamPost, type StreamEvent } from "@/lib/api";
import {
  formatCo2,
  formatDuration,
  formatElapsed,
  formatEnergy,
  formatNumber,
  formatWatts,
} from "@/lib/format";
import type { EnergySnapshot } from "@/lib/types";

export function EnergyView() {
  const [projectPath, setProjectPath] = useState("");
  const [command, setCommand] = useState("");
  const [timeout, setTimeoutSeconds] = useState(300);
  const [continuous, setContinuous] = useState(false);

  const [running, setRunning] = useState(false);
  const [percent, setPercent] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [statusText, setStatusText] = useState("Ready to measure");
  const [log, setLog] = useState<string[]>([]);

  const [snapshots, setSnapshots] = useState<EnergySnapshot[]>([]);
  const [result, setResult] = useState<EnergySnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

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
    if (!projectPath.trim() || !command.trim()) {
      setError("A project path and an execution command are both required.");
      return;
    }

    setRunning(true);
    setError(null);
    setPercent(0);
    setElapsed(0);
    setLog([]);
    setSnapshots([]);
    setResult(null);
    setStatusText(continuous ? "Starting monitored run…" : "Starting measurement…");

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await streamPost(
        "/api/energy/estimate/stream",
        {
          project_path: projectPath.trim(),
          command: command.trim(),
          timeout: Number(timeout) || 300,
          continuous,
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

          setSnapshots((previous) => [...previous, snapshot]);

          if (snapshot.final) {
            setResult(snapshot);
            setPercent(100);
            setStatusText("Measurement complete");
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
      appendLog(
        `Stop failed: ${caught instanceof Error ? caught.message : String(caught)}`,
      );
    }
  }

  return (
    <>
      <PageHeader
        overline="CodeCarbon"
        title="Energy Measurement"
        description="Execute a project under a controlled command and measure what it actually consumes: energy, CO₂, execution time, and CPU / GPU / RAM power."
      />

      <div className="mb-5">
        <Alert tone="info" title="Measurements are experimental data">
          A single run is affected by machine state and background load. Use the
          optimization pipeline when you need a noise-aware original-vs-candidate
          comparison instead of a one-off number.
        </Alert>
      </div>

      <Card className="mb-5">
        <SectionHeader overline="New measurement" title="Run a project under the tracker" />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Field label="Project path" htmlFor="projectPath">
            <input
              id="projectPath"
              className={inputClass}
              value={projectPath}
              onChange={(event) => setProjectPath(event.target.value)}
              placeholder="D:/projects/my_project"
              disabled={running}
            />
          </Field>

          <Field
            label="Execution command"
            htmlFor="command"
            hint="Run from the project directory, e.g. python main.py or php -S localhost:8000"
          >
            <input
              id="command"
              className={inputClass}
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              placeholder="python main.py"
              disabled={running}
            />
          </Field>

          <Field label="Timeout / monitor duration" htmlFor="timeout">
            <input
              id="timeout"
              type="number"
              min={10}
              className={inputClass}
              value={timeout}
              onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
              disabled={running}
            />
          </Field>

          <div className="flex items-end">
            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
                checked={continuous}
                onChange={(event) => setContinuous(event.target.checked)}
                disabled={running}
              />
              <span>
                Continuous mode
                <span className="mt-0.5 block text-xs text-muted">
                  For servers and other processes that never exit.
                </span>
              </span>
            </label>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={buttonPrimary}
            onClick={handleRun}
            disabled={running}
          >
            ⚡ Run energy analysis
          </button>
          <button
            type="button"
            className={buttonDanger}
            onClick={handleStop}
            disabled={!running || !continuous}
            title={continuous ? "Stop the run" : "Stop is available in continuous mode"}
          >
            ■ Stop
          </button>
          {running ? <Spinner label={statusText} /> : (
            <span className="text-xs text-muted">{statusText}</span>
          )}
        </div>

        {running || log.length > 0 ? (
          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between text-xs text-muted">
              <span>{statusText}</span>
              <span className="font-mono">
                {Math.round(percent)}% · {formatElapsed(elapsed)}
              </span>
            </div>
            <ProgressBar percent={percent} />
            {log.length > 0 ? (
              <div
                ref={logRef}
                className="mt-3 max-h-40 overflow-y-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-muted"
              >
                {log.map((line, index) => (
                  <div key={`${index}-${line.slice(0, 12)}`}>{line}</div>
                ))}
              </div>
            ) : null}
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

      {!result && !running ? (
        <EmptyState
          icon="⚡"
          title="Nothing measured yet"
          message="Enter a project path and the command that runs it, then start the measurement. Results appear here as summary cards."
        />
      ) : null}

      {result ? (
        <>
          <section className="mb-5">
            <SectionHeader
              overline="Measured"
              title="Energy summary"
              actions={
                <Badge
                  tone={
                    result.execution_status === "success"
                      ? "accent"
                      : result.execution_status === "failed"
                        ? "danger"
                        : "warn"
                  }
                >
                  {(result.execution_status ?? "unknown").toUpperCase()}
                </Badge>
              }
            />

            <Grid columns={4}>
              <MetricCard
                label="Energy consumed"
                value={formatEnergy(result.energy_consumed)}
                tone="accent"
                emphasized
                hint="Measured by CodeCarbon (CPU + GPU + RAM)"
              />
              <MetricCard
                label="CO₂ equivalent"
                value={formatCo2(result.emissions)}
                hint="Emissions attributed to this run"
              />
              <MetricCard
                label="Execution time"
                value={formatDuration(result.execution_time_seconds)}
                hint={`Return code: ${result.return_code ?? "—"}`}
              />
              <MetricCard
                label={continuous ? "Snapshots captured" : "Tracker duration"}
                value={
                  continuous ? snapshots.length : formatDuration(result.duration)
                }
                hint={
                  result.stop_reason
                    ? `Stop reason: ${result.stop_reason}`
                    : "Completed normally"
                }
              />
            </Grid>
          </section>

          <section className="mb-8">
            <SectionHeader
              overline="Details"
              title="Tracker internals"
              description="Collapsed by default — open only what you need to audit the run."
            />

            <DisclosureStack>
              <Disclosure
                title="Power & resource breakdown"
                overline="CPU · GPU · RAM"
                summary={`CPU ${formatWatts(result.cpu_power)} · RAM ${formatWatts(
                  result.ram_power,
                )} · GPU ${formatWatts(result.gpu_power)}`}
              >
                <KeyValue
                  columns={3}
                  items={[
                    { label: "CPU energy", value: formatEnergy(result.cpu_energy) },
                    { label: "GPU energy", value: formatEnergy(result.gpu_energy) },
                    { label: "RAM energy", value: formatEnergy(result.ram_energy) },
                    { label: "CPU power", value: formatWatts(result.cpu_power) },
                    { label: "GPU power", value: formatWatts(result.gpu_power) },
                    { label: "RAM power", value: formatWatts(result.ram_power) },
                    {
                      label: "Emissions rate",
                      value:
                        result.emissions_rate != null
                          ? `${formatNumber(result.emissions_rate, {
                              maximumFractionDigits: 10,
                            })} kg/s`
                          : "—",
                    },
                    {
                      label: "Water consumed",
                      value:
                        result.water_consumed != null
                          ? `${formatNumber(result.water_consumed, {
                              maximumFractionDigits: 6,
                            })} L`
                          : "—",
                    },
                    { label: "Tracker duration", value: formatDuration(result.duration) },
                  ]}
                />
              </Disclosure>

              {continuous && snapshots.length > 1 ? (
                <Disclosure
                  title="Snapshot history"
                  overline="Continuous mode"
                  summary={`${snapshots.length} snapshots captured`}
                >
                  <div className="overflow-x-auto rounded-lg border border-line">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead>
                        <tr className="border-b border-line bg-surface-2">
                          {["#", "Energy", "CO₂", "Elapsed", "Status"].map((column) => (
                            <th
                              key={column}
                              className="whitespace-nowrap px-3 py-2 font-semibold text-muted"
                            >
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {snapshots.map((snapshot, index) => (
                          <tr
                            key={index}
                            className="border-b border-line/50 last:border-b-0"
                          >
                            <td className="px-3 py-1.5">{snapshot.snapshot_index ?? index + 1}</td>
                            <td className="px-3 py-1.5">
                              {formatEnergy(snapshot.energy_consumed)}
                            </td>
                            <td className="px-3 py-1.5">
                              {formatCo2(snapshot.emissions)}
                            </td>
                            <td className="px-3 py-1.5">
                              {formatDuration(snapshot.execution_time_seconds)}
                            </td>
                            <td className="px-3 py-1.5">
                              {snapshot.final ? "final" : (snapshot.execution_status ?? "—")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Disclosure>
              ) : null}

              <Disclosure
                title="Environment & metadata"
                overline="Reproducibility"
                summary="Hardware, tracking mode and identifiers for this measurement"
              >
                <KeyValue
                  columns={3}
                  items={[
                    { label: "Project path", value: result.project_path ?? "—" },
                    { label: "Files in project", value: result.file_count ?? "—" },
                    { label: "CPU count", value: result.cpu_count ?? "—" },
                    { label: "GPU count", value: result.gpu_count ?? "—" },
                    {
                      label: "RAM total (GB)",
                      value:
                        result.ram_total_size != null
                          ? formatNumber(result.ram_total_size, {
                              maximumFractionDigits: 2,
                            })
                          : "—",
                    },
                    { label: "Tracking mode", value: result.tracking_mode ?? "—" },
                    {
                      label: "On cloud",
                      value: result.on_cloud == null ? "—" : String(result.on_cloud),
                    },
                    { label: "PUE", value: result.pue ?? "—" },
                    { label: "WUE", value: result.wue ?? "—" },
                    { label: "Region", value: result.country_name ?? "—" },
                    { label: "Run id", value: result.run_id ?? "—" },
                    { label: "Timestamp", value: result.timestamp ?? "—" },
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
                    <CodeBlock code={result.stdout?.trim() || "(empty)"} maxHeight={220} />
                  </div>
                  <div>
                    <p className="overline mb-1.5">stderr</p>
                    <CodeBlock code={result.stderr?.trim() || "(empty)"} maxHeight={220} />
                  </div>
                </div>
              </Disclosure>

              <Disclosure
                title="Raw response"
                overline="JSON"
                summary="The exact payload returned by the tracker API"
              >
                <CodeBlock
                  code={JSON.stringify(result, null, 2)}
                  language="json"
                  maxHeight={320}
                />
              </Disclosure>
            </DisclosureStack>
          </section>
        </>
      ) : null}
    </>
  );
}
