"use client";

/**
 * Combined analysis: code understanding + energy measurement in one workflow.
 *
 * Layout rule for this page: the top shows a summary only — the same style of
 * headline cards as the energy dashboard. Every detailed table lives inside a
 * collapsed Disclosure so the page never opens on a wall of raw metrics.
 */

import { useEffect, useMemo, useRef, useState } from "react";

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
  formatInteger,
  formatNumber,
  formatWatts,
  truncate,
} from "@/lib/format";
import type { EnergySnapshot, FolderAnalysisResult } from "@/lib/types";

type Phase = "idle" | "parsing" | "measuring" | "done" | "error";

const LANGUAGES = [
  { value: "auto", label: "Auto-detect" },
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "javascript", label: "JavaScript" },
  { value: "c", label: "C" },
  { value: "cpp", label: "C++" },
];

const STEPS = [
  { key: "parsing", label: "1 · Parse code" },
  { key: "measuring", label: "2 · Measure energy" },
  { key: "done", label: "3 · Report" },
];

export function AnalyzeView() {
  const [targetPath, setTargetPath] = useState("");
  const [language, setLanguage] = useState("auto");
  const [command, setCommand] = useState("");
  const [timeout, setTimeoutSeconds] = useState(300);
  const [continuous, setContinuous] = useState(false);

  const [phase, setPhase] = useState<Phase>("idle");
  const [percent, setPercent] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [log, setLog] = useState<string[]>([]);
  const [statusText, setStatusText] = useState("Ready to analyze");

  const [structure, setStructure] = useState<FolderAnalysisResult | null>(null);
  const [energy, setEnergy] = useState<EnergySnapshot | null>(null);
  const [signals, setSignals] = useState<EnergySnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const running = phase === "parsing" || phase === "measuring";

  // Elapsed timer, only while a run is active.
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  // Keep the log pinned to the newest line.
  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [log]);

  function appendLog(message: string) {
    if (!message) return;
    setLog((previous) => {
      const next = [...previous, message];
      return next.length > 300 ? next.slice(-300) : next;
    });
  }

  function reset() {
    setPercent(0);
    setElapsed(0);
    setLog([]);
    setError(null);
    setWarnings([]);
    setStructure(null);
    setEnergy(null);
    setSignals([]);
  }

  async function handleRun() {
    if (!targetPath.trim()) {
      setError("Enter a file or folder path first.");
      return;
    }

    reset();
    setPhase("parsing");
    setStatusText("Parsing code…");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // ---------------- STEP 1: STATIC ANALYSIS ----------------
      // Held in an object because the value is produced inside a stream callback.
      const collected: { result: FolderAnalysisResult | null } = { result: null };

      await streamPost(
        "/api/code/analyze/stream",
        {
          project_path: targetPath.trim(),
          language,
          recursive: true,
          max_files: 500,
        },
        (event: StreamEvent) => {
          if (event.type === "progress") {
            const stagePercent = Number(event.percent ?? 0);
            setPercent(Math.max(0, Math.min(50, stagePercent * 0.5)));
            appendLog(
              `${event.message ?? event.stage ?? "progress"}${
                event.file ? ` — ${event.file}` : ""
              }`,
            );
          } else if (event.type === "result") {
            collected.result = event.result as FolderAnalysisResult;
          } else if (event.type === "error") {
            throw new Error(String(event.message ?? "Analysis failed"));
          }
        },
        controller.signal,
      );

      const parsed = collected.result;
      if (!parsed) {
        throw new Error("The backend returned no analysis result.");
      }

      setStructure(parsed);
      setPercent(50);
      appendLog(
        `Parsed ${parsed.analyzed_files ?? 0} file(s)` +
          (parsed.failed_files ? `, ${parsed.failed_files} failed` : ""),
      );

      if (parsed.notes?.length) setWarnings(parsed.notes);

      // ---------------- STEP 2: ENERGY MEASUREMENT ----------------
      if (!command.trim()) {
        setPercent(100);
        setPhase("done");
        setStatusText("Static analysis complete — no command given, so no energy was measured");
        appendLog("No execution command supplied: skipped energy measurement.");
        return;
      }

      setPhase("measuring");
      setStatusText(continuous ? "Monitoring running project…" : "Executing and measuring…");
      appendLog(`Running: ${command.trim()}`);

      await streamPost(
        "/api/energy/estimate/stream",
        {
          project_path: targetPath.trim(),
          command: command.trim(),
          timeout: Number(timeout) || 300,
          continuous,
          interval_seconds: 10,
        },
        (event: StreamEvent) => {
          const snapshot = event as EnergySnapshot;

          if (snapshot.error) {
            throw new Error(String(snapshot.error));
          }

          if (snapshot.execution_status === "measuring" && !snapshot.final) {
            setPercent((value) => Math.min(96, Math.max(value, 52) + 2));
            if (snapshot.execution_time_seconds) {
              setStatusText(
                `Measuring… ${formatDuration(snapshot.execution_time_seconds)} elapsed`,
              );
            }
            return;
          }

          setSignals((previous) => [...previous, snapshot]);

          if (snapshot.final) {
            setEnergy(snapshot);
            setPercent(100);
            appendLog(
              `Measured: ${formatEnergy(snapshot.energy_consumed)} · ` +
                `${formatCo2(snapshot.emissions)} · ${formatDuration(
                  snapshot.execution_time_seconds,
                )}`,
            );
          } else {
            setPercent((value) => Math.min(94, Math.max(value, 55) + 4));
            appendLog(
              `Snapshot #${snapshot.snapshot_index ?? "?"}: ` +
                `${formatEnergy(snapshot.energy_consumed)}`,
            );
          }
        },
        controller.signal,
      );

      setPhase("done");
      setStatusText("Analysis complete");
    } catch (caught) {
      if (controller.signal.aborted) {
        setPhase("done");
        setStatusText("Stopped");
        appendLog("Run stopped by user.");
        return;
      }
      const message = caught instanceof Error ? caught.message : String(caught);
      setError(message);
      setPhase("error");
      setStatusText("Analysis failed");
      appendLog(`ERROR: ${message}`);
    } finally {
      abortRef.current = null;
    }
  }

  async function handleStop() {
    try {
      await apiPost("/api/energy/stop");
      appendLog("Stop requested — waiting for final metrics…");
    } catch (caught) {
      appendLog(
        `Stop failed: ${caught instanceof Error ? caught.message : String(caught)}`,
      );
    }
  }

  const summary = useMemo(() => {
    const complexity = structure?.complexity ?? {};
    const languages = structure?.languages ?? {};
    return {
      files: structure?.analyzed_files ?? 0,
      failed: structure?.failed_files ?? 0,
      functions: structure?.functions?.length ?? 0,
      classes: structure?.classes?.length ?? 0,
      loops: structure?.loops?.length ?? 0,
      conditionals: structure?.conditionals ?? 0,
      lines: structure?.total_lines ?? 0,
      maxComplexity: complexity.max ?? null,
      languageCount: Object.keys(languages).length,
      languages: Object.entries(languages)
        .map(([name, count]) => `${name} (${count})`)
        .join(", "),
      calls: structure?.function_calls?.length ?? 0,
      io: structure?.io_operations?.length ?? 0,
      dependencies: structure?.dependencies?.length ?? 0,
      dataStructures: structure?.data_structures?.length ?? 0,
    };
  }, [structure]);

  const hasResult = structure !== null;

  return (
    <>
      <PageHeader
        overline="Code understanding + CodeCarbon"
        title="Combined Analysis"
        description="Point at a file or a whole project. OASIS parses the code into a structured representation, then optionally executes it to measure real energy consumption."
      />

      <div className="mb-5">
        <Alert tone="info" title="Static analysis and measurement are separate claims">
          Parsing tells you what the code looks like. Only the second step produces
          measured energy. If you leave the execution command empty, no energy value
          is produced or implied.
        </Alert>
      </div>

      {/* ================= INPUT ================= */}
      <Card className="mb-5">
        <SectionHeader overline="New analysis" title="Analyze a file or a folder" />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="lg:col-span-2">
            <Field
              label="File / folder path"
              htmlFor="targetPath"
              hint="A file analyzes just that file. A folder is scanned recursively; dependency and build folders are skipped."
            >
              <input
                id="targetPath"
                className={inputClass}
                value={targetPath}
                onChange={(event) => setTargetPath(event.target.value)}
                placeholder="D:/projects/my_project   or   D:/projects/my_project/main.py"
                disabled={running}
              />
            </Field>
          </div>

          <Field label="Language" htmlFor="language">
            <select
              id="language"
              className={inputClass}
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              disabled={running}
            >
              {LANGUAGES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Execution command"
            htmlFor="command"
            hint="Leave empty to run static analysis only."
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

          <Field
            label="Timeout"
            htmlFor="timeout"
            hint="In continuous mode this is how long the running process is monitored."
          >
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
                  For projects that never exit, e.g.{" "}
                  <code>php -S localhost:8000</code> or a Flask server. Metrics
                  stream in every 10 seconds until you press Stop.
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
            ⚡ Run analysis
          </button>
          <button
            type="button"
            className={buttonDanger}
            onClick={handleStop}
            disabled={!running || !continuous}
            title={
              continuous
                ? "Stop the running measurement"
                : "Stop is available in continuous mode"
            }
          >
            ■ Stop
          </button>
          {running ? <Spinner label={statusText} /> : (
            <span className="text-xs text-muted">{statusText}</span>
          )}
        </div>
      </Card>

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Analysis failed">
            {error}
          </Alert>
        </div>
      ) : null}

      {/* ================= PROGRESS ================= */}
      {running || (hasResult && phase !== "idle") ? (
        <Card className="mb-5">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="overline mb-1">Progress</p>
              <p className="text-sm font-semibold text-ink">{statusText}</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-lg font-semibold text-accent">
                {Math.round(percent)}%
              </span>
              <span className="font-mono text-xs text-muted">
                {formatElapsed(elapsed)}
              </span>
            </div>
          </div>

          <ProgressBar percent={percent} />

          <div className="mt-3 flex flex-wrap gap-2">
            {STEPS.map((step) => {
              const active = step.key === phase;
              const done =
                (step.key === "parsing" && percent >= 50) ||
                (step.key === "measuring" && percent >= 100) ||
                (step.key === "done" && phase === "done");

              return (
                <Badge
                  key={step.key}
                  tone={active ? "info" : done ? "accent" : "muted"}
                >
                  {step.label}
                </Badge>
              );
            })}
          </div>

          {log.length > 0 ? (
            <div
              ref={logRef}
              className="mt-4 max-h-40 overflow-y-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-muted"
            >
              {log.map((line, index) => (
                <div key={`${index}-${line.slice(0, 12)}`}>{line}</div>
              ))}
            </div>
          ) : null}
        </Card>
      ) : null}

      {!hasResult && !running ? (
        <EmptyState
          icon="🔍"
          title="No analysis yet"
          message="Enter a path and run the analysis. The summary appears here first; the detailed tables stay collapsed underneath."
        />
      ) : null}

      {/* ================= SUMMARY ================= */}
      {hasResult ? (
        <>
          <section className="mb-5">
            <SectionHeader
              overline="Summary"
              title="What was found"
              actions={
                <Badge tone="info">{(structure?.language ?? "mixed").toUpperCase()}</Badge>
              }
            />

            <Grid columns={4}>
              <MetricCard
                label="Files analyzed"
                value={formatInteger(summary.files)}
                tone="accent"
                emphasized
                hint={
                  summary.failed > 0
                    ? `${summary.failed} file(s) failed to parse`
                    : `${structure?.total_files_found ?? summary.files} found in total`
                }
              />
              <MetricCard
                label="Lines of code"
                value={formatInteger(summary.lines)}
                hint={`${summary.languageCount} language(s) detected`}
              />
              <MetricCard
                label="Functions"
                value={formatInteger(summary.functions)}
                hint={`${summary.classes} class(es)`}
              />
              <MetricCard
                label="Loops"
                value={formatInteger(summary.loops)}
                hint={`${summary.conditionals} conditional branch(es)`}
              />
              <MetricCard
                label="Max complexity"
                value={summary.maxComplexity ?? "—"}
                tone={summary.maxComplexity && summary.maxComplexity > 10 ? "warn" : "ink"}
                hint="Highest cyclomatic complexity seen"
              />
              <MetricCard
                label="Function calls"
                value={formatInteger(summary.calls)}
                hint={`${summary.dependencies} distinct dependency(ies)`}
              />
              <MetricCard
                label="I/O operations"
                value={formatInteger(summary.io)}
                hint="File, console and network access sites"
              />
              <MetricCard
                label="Allocations"
                value={formatInteger(structure?.allocations ?? 0)}
                hint="Allocation sites detected by the parser"
              />
            </Grid>
          </section>

          {energy ? (
            <section className="mb-5">
              <SectionHeader
                overline="Measured"
                title="Energy measurement"
                description="Produced by CodeCarbon while the project executed. These are measurements, not predictions."
                actions={
                  <Badge
                    tone={
                      energy.execution_status === "success"
                        ? "accent"
                        : energy.execution_status === "failed"
                          ? "danger"
                          : "warn"
                    }
                  >
                    {(energy.execution_status ?? "unknown").toUpperCase()}
                  </Badge>
                }
              />

              <Grid columns={4}>
                <MetricCard
                  label="Energy consumed"
                  value={formatEnergy(energy.energy_consumed)}
                  tone="accent"
                  emphasized
                  hint="CodeCarbon total across CPU, GPU and RAM"
                />
                <MetricCard
                  label="CO₂ equivalent"
                  value={formatCo2(energy.emissions)}
                  hint="Emissions for this run"
                />
                <MetricCard
                  label="Execution time"
                  value={formatDuration(energy.execution_time_seconds)}
                  hint={`Return code: ${energy.return_code ?? "—"}`}
                />
                <MetricCard
                  label={continuous ? "Snapshots" : "Runs"}
                  value={continuous ? signals.length : 1}
                  hint={
                    energy.stop_reason
                      ? `Stop reason: ${energy.stop_reason}`
                      : "Single measured execution"
                  }
                />
              </Grid>
            </section>
          ) : null}

          {/* ================= DETAILS (collapsed) ================= */}
          <section className="mb-8">
            <SectionHeader
              overline="Details"
              title="Everything else"
              description="Deep tables are collapsed by default so the summary above stays readable. Open only what you need."
            />

            <DisclosureStack>
              <Disclosure
                title="Detailed code structure"
                overline="Functions, classes, loops, calls"
                summary={`${summary.functions} functions · ${summary.classes} classes · ${summary.loops} loops · ${summary.calls} calls`}
              >
                <div className="space-y-3">
                  <Disclosure title="Functions" summary={`${summary.functions} entries`}>
                    {structure?.functions?.length ? (
                      <DetailTable
                        columns={["Name", "File", "Lines", "Complexity"]}
                        rows={structure.functions.map((item) => [
                          item.name,
                          truncate(item.file ?? "—", 48),
                          item.start_line
                            ? `${item.start_line}–${item.end_line ?? item.start_line}`
                            : "—",
                          item.complexity ?? "—",
                        ])}
                      />
                    ) : (
                      <p className="text-xs text-muted">No functions were found.</p>
                    )}
                  </Disclosure>

                  <Disclosure title="Classes" summary={`${summary.classes} entries`}>
                    {structure?.classes?.length ? (
                      <DetailTable
                        columns={["Name", "File", "Lines", "Methods"]}
                        rows={structure.classes.map((item) => [
                          item.name,
                          truncate(item.file ?? "—", 48),
                          item.start_line ? `${item.start_line}–${item.end_line ?? ""}` : "—",
                          item.methods?.length ?? 0,
                        ])}
                      />
                    ) : (
                      <p className="text-xs text-muted">No classes were found.</p>
                    )}
                  </Disclosure>

                  <Disclosure title="Loops" summary={`${summary.loops} entries`}>
                    {structure?.loops?.length ? (
                      <DetailTable
                        columns={["Kind", "File", "Line"]}
                        rows={structure.loops.map((loop) => [
                          loop.kind,
                          truncate(loop.file ?? "—", 48),
                          loop.line ?? "—",
                        ])}
                      />
                    ) : (
                      <p className="text-xs text-muted">No loops were found.</p>
                    )}
                  </Disclosure>

                  <Disclosure
                    title="Function calls"
                    summary={`${summary.calls} entries`}
                  >
                    {structure?.function_calls?.length ? (
                      <DetailTable
                        columns={["Function", "File", "Line", "Args"]}
                        rows={structure.function_calls.map((call) => [
                          call.name,
                          truncate(call.file ?? "—", 48),
                          call.line ?? "—",
                          call.argument_count ?? "—",
                        ])}
                      />
                    ) : (
                      <p className="text-xs text-muted">No calls were recorded.</p>
                    )}
                  </Disclosure>

                  <Disclosure
                    title="I/O operations"
                    summary={`${summary.io} entries`}
                  >
                    {structure?.io_operations?.length ? (
                      <DetailTable
                        columns={["File", "Operation"]}
                        rows={structure.io_operations.map((op) => [
                          truncate(op.file, 48),
                          truncate(op.operation, 90),
                        ])}
                      />
                    ) : (
                      <p className="text-xs text-muted">No I/O operations detected.</p>
                    )}
                  </Disclosure>

                  <Disclosure
                    title="Dependencies & data structures"
                    summary={`${summary.dependencies} dependencies · ${summary.dataStructures} data structures`}
                  >
                    <div className="space-y-4">
                      <TagList
                        label="Dependencies"
                        values={structure?.dependencies ?? []}
                      />
                      <TagList
                        label="Data structures"
                        values={structure?.data_structures ?? []}
                      />
                    </div>
                  </Disclosure>
                </div>
              </Disclosure>

              <Disclosure
                title="Per-file breakdown"
                overline="File table"
                summary={`${structure?.files?.length ?? 0} file rows`}
              >
                {structure?.files?.length ? (
                  <DetailTable
                    columns={[
                      "File",
                      "Lang",
                      "Func",
                      "Class",
                      "Loop",
                      "Cond",
                      "Calls",
                      "Deps",
                    ]}
                    rows={structure.files.map((file) => [
                      truncate(file.file, 60),
                      file.failed ? "—" : (file.language ?? "—"),
                      file.failed ? "failed" : (file.functions ?? 0),
                      file.failed ? "—" : (file.classes ?? 0),
                      file.failed ? "—" : (file.loops ?? 0),
                      file.failed ? "—" : (file.conditionals ?? 0),
                      file.failed ? "—" : (file.calls ?? 0),
                      file.failed ? "—" : (file.dependencies ?? 0),
                    ])}
                  />
                ) : (
                  <p className="text-xs text-muted">No per-file details available.</p>
                )}
              </Disclosure>

              <Disclosure
                title="Energy breakdown & resources"
                overline="CPU · GPU · RAM"
                summary={
                  energy
                    ? `CPU ${formatWatts(energy.cpu_power)} · RAM ${formatWatts(
                        energy.ram_power,
                      )} · GPU ${formatWatts(energy.gpu_power)}`
                    : "Not measured"
                }
              >
                {energy ? (
                  <div className="space-y-4">
                    <KeyValue
                      columns={3}
                      items={[
                        {
                          label: "CPU energy",
                          value: formatEnergy(energy.cpu_energy),
                        },
                        {
                          label: "GPU energy",
                          value: formatEnergy(energy.gpu_energy),
                        },
                        {
                          label: "RAM energy",
                          value: formatEnergy(energy.ram_energy),
                        },
                        { label: "CPU power", value: formatWatts(energy.cpu_power) },
                        { label: "GPU power", value: formatWatts(energy.gpu_power) },
                        { label: "RAM power", value: formatWatts(energy.ram_power) },
                        {
                          label: "Emissions rate",
                          value:
                            energy.emissions_rate != null
                              ? `${formatNumber(energy.emissions_rate, {
                                  maximumFractionDigits: 10,
                                })} kg/s`
                              : "—",
                        },
                        {
                          label: "Water consumed",
                          value:
                            energy.water_consumed != null
                              ? `${formatNumber(energy.water_consumed, {
                                  maximumFractionDigits: 6,
                                })} L`
                              : "—",
                        },
                        {
                          label: "Tracker duration",
                          value: formatDuration(energy.duration),
                        },
                      ]}
                    />

                    {continuous && signals.length > 0 ? (
                      <div>
                        <p className="overline mb-2">Snapshot history</p>
                        <DetailTable
                          columns={["#", "Energy", "CO₂", "Elapsed", "Status"]}
                          rows={signals.map((snapshot) => [
                            snapshot.snapshot_index ?? "—",
                            formatEnergy(snapshot.energy_consumed),
                            formatCo2(snapshot.emissions),
                            formatDuration(snapshot.execution_time_seconds),
                            snapshot.final ? "final" : (snapshot.execution_status ?? "—"),
                          ])}
                        />
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="text-xs text-muted">
                    No energy was measured for this run.
                  </p>
                )}
              </Disclosure>

              <Disclosure
                title="Environment & metadata"
                overline="Reproducibility"
                summary="Hardware, tracking mode and identifiers for this measurement"
              >
                {energy ? (
                  <KeyValue
                    columns={3}
                    items={[
                      { label: "Project path", value: energy.project_path ?? "—" },
                      { label: "Files in project", value: energy.file_count ?? "—" },
                      {
                        label: "CPU count",
                        value: energy.cpu_count ?? "—",
                      },
                      { label: "GPU count", value: energy.gpu_count ?? "—" },
                      {
                        label: "RAM total (GB)",
                        value:
                          energy.ram_total_size != null
                            ? formatNumber(energy.ram_total_size, {
                                maximumFractionDigits: 2,
                              })
                            : "—",
                      },
                      { label: "Tracking mode", value: energy.tracking_mode ?? "—" },
                      {
                        label: "On cloud",
                        value: energy.on_cloud == null ? "—" : String(energy.on_cloud),
                      },
                      { label: "PUE", value: energy.pue ?? "—" },
                      { label: "WUE", value: energy.wue ?? "—" },
                      { label: "Region", value: energy.country_name ?? "—" },
                      { label: "Run id", value: truncate(energy.run_id ?? "—", 24) },
                      { label: "Timestamp", value: energy.timestamp ?? "—" },
                      { label: "Process id", value: energy.pid ?? "—" },
                      {
                        label: "Stop reason",
                        value: energy.stop_reason ?? "completed",
                      },
                      {
                        label: "Stopped by user",
                        value: String(energy.stopped_by_user ?? false),
                      },
                    ]}
                  />
                ) : (
                  <p className="text-xs text-muted">Not measured.</p>
                )}
              </Disclosure>

              <Disclosure
                title="Process output"
                overline="stdout / stderr"
                summary="Console output captured during execution"
              >
                <div className="space-y-3">
                  <div>
                    <p className="overline mb-1.5">stdout</p>
                    <CodeBlock
                      code={energy?.stdout?.trim() || "(empty)"}
                      maxHeight={220}
                    />
                  </div>
                  <div>
                    <p className="overline mb-1.5">stderr</p>
                    <CodeBlock
                      code={energy?.stderr?.trim() || "(empty)"}
                      maxHeight={220}
                    />
                  </div>
                </div>
              </Disclosure>

              {(warnings.length > 0 || (structure?.failures?.length ?? 0) > 0) ? (
                <Disclosure
                  title="Problems & notes"
                  overline="Failures"
                  summary={`${structure?.failures?.length ?? 0} failure(s), ${warnings.length} note(s)`}
                >
                  <div className="space-y-4">
                    {warnings.length > 0 ? (
                      <ul className="list-inside list-disc space-y-1 text-xs text-muted">
                        {warnings.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                    ) : null}

                    {structure?.failures?.length ? (
                      <DetailTable
                        columns={["File", "Language", "Error"]}
                        rows={structure.failures.map((failure) => [
                          truncate(failure.file, 50),
                          failure.language ?? "—",
                          truncate(failure.error ?? "—", 90),
                        ])}
                      />
                    ) : null}
                  </div>
                </Disclosure>
              ) : null}

              <Disclosure
                title="Raw response"
                overline="JSON"
                summary="The exact payloads returned by the API"
              >
                <div className="space-y-3">
                  <div>
                    <p className="overline mb-1.5">Code understanding</p>
                    <CodeBlock
                      code={JSON.stringify(structure, null, 2)}
                      language="json"
                      maxHeight={280}
                    />
                  </div>
                  {energy ? (
                    <div>
                      <p className="overline mb-1.5">Energy measurement</p>
                      <CodeBlock
                        code={JSON.stringify(energy, null, 2)}
                        language="json"
                        maxHeight={280}
                      />
                    </div>
                  ) : null}
                </div>
              </Disclosure>
            </DisclosureStack>
          </section>
        </>
      ) : null}
    </>
  );
}

/* ============================================================
   LOCAL PRESENTATION HELPERS
   ============================================================ */

function DetailTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: (string | number | null | undefined)[][];
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-line bg-surface-2">
            {columns.map((column) => (
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
          {rows.slice(0, 300).map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className="border-b border-line/50 last:border-b-0 hover:bg-surface-2/60"
            >
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="max-w-[26rem] truncate px-3 py-1.5 text-ink/90"
                  title={typeof cell === "string" ? cell : undefined}
                >
                  {cell === null || cell === undefined ? "—" : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 300 ? (
        <p className="border-t border-line px-3 py-2 text-[11px] text-muted">
          Showing 300 of {rows.length} rows.
        </p>
      ) : null}
    </div>
  );
}

function TagList({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="overline mb-2">{label}</p>
      {values.length ? (
        <div className="flex flex-wrap gap-1.5">
          {values.slice(0, 120).map((value) => (
            <span
              key={value}
              className="rounded border border-line bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-ink/80"
            >
              {value}
            </span>
          ))}
          {values.length > 120 ? (
            <span className="text-[11px] text-muted">
              +{values.length - 120} more
            </span>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-muted">None detected.</p>
      )}
    </div>
  );
}
