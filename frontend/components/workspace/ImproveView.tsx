"use client";

/**
 * Stage 3 — Improve.
 *
 * Runs detect → generate → rank → verify → benchmark → decide as one streamed
 * pipeline, then presents candidates as a list + detail workspace. The split
 * between predicted impact and measured energy stays visible everywhere.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Disclosure, DisclosureStack } from "@/components/Disclosure";
import { GuidanceBar, StageHeader, StageSteps, WorkspaceBar } from "@/components/workspace/StageChrome";
import { useWorkspace, targetName } from "@/components/workspace/WorkspaceContext";
import {
  Alert,
  Badge,
  Card,
  CodeBlock,
  EmptyState,
  Grid,
  MetricCard,
  Spinner,
  buttonGhost,
  buttonPrimary,
  inputClass,
  type Tone,
} from "@/components/ui";
import { apiGet, streamPost, type StreamEvent } from "@/lib/api";
import {
  formatElapsed,
  formatInteger,
  formatJoules,
  formatPercent,
  formatSignedPercent,
  shortId,
} from "@/lib/format";
import type {
  Candidate,
  Detection,
  LlmStatus,
  PipelineResult,
  VerificationResult,
  DecisionResult,
} from "@/lib/types";

const PIPELINE_STEPS = [
  { key: "detect", label: "Detect" },
  { key: "generate", label: "Generate" },
  { key: "rank", label: "Rank" },
  { key: "verify", label: "Verify" },
  { key: "benchmark", label: "Measure" },
  { key: "decide", label: "Decide" },
];

function statusTone(status?: string | null): Tone {
  switch ((status ?? "").toUpperCase()) {
    case "IMPROVED":
    case "VERIFIED":
    case "MEASURED":
    case "ACCEPTED":
      return "accent";
    case "NEUTRAL":
    case "BENCHMARK_PENDING":
    case "VERIFICATION_PENDING":
    case "PREDICTED":
    case "GENERATED":
      return "warn";
    case "REGRESSED":
    case "FAILED":
    case "VERIFICATION_FAILED":
    case "BENCHMARK_FAILED":
    case "REJECTED":
      return "danger";
    default:
      return "muted";
  }
}

export function ImproveView() {
  const { settings, updateSettings, scan, improve, setImprove, decisions } = useWorkspace();

  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("detect");
  const [percent, setPercent] = useState(0);
  const [statusText, setStatusText] = useState("Ready");
  const [elapsed, setElapsed] = useState(0);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [detections, setDetections] = useState<Detection[]>(improve?.result?.detections ?? []);
  const [candidates, setCandidates] = useState<Candidate[]>(improve?.candidates ?? []);
  const [result, setResult] = useState<PipelineResult | null>(improve?.result ?? null);
  const [llm, setLlm] = useState<LlmStatus | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    improve?.candidates[0]?.candidate_id ?? null,
  );

  const [numCandidates, setNumCandidates] = useState(2);
  const [runs, setRuns] = useState(2);
  const [warmupRuns, setWarmupRuns] = useState(1);
  const [minImprovement, setMinImprovement] = useState(5);
  const [skipBenchmark, setSkipBenchmark] = useState(false);

  const controllerRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    apiGet<LlmStatus>("/api/llm/status")
      .then(setLlm)
      .catch(() => setLlm(null));
  }, []);

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
    setLog((previous) => [...previous, message].slice(-300));
  }

  function patchCandidate(id: string, patch: Partial<Candidate>) {
    setCandidates((previous) =>
      previous.map((candidate) =>
        candidate.candidate_id === id ? { ...candidate, ...patch } : candidate,
      ),
    );
  }

  async function handleRun() {
    if (!settings.filePath.trim()) {
      setError("Enter the file to optimize.");
      return;
    }
    if (!skipBenchmark && !settings.command.trim()) {
      setError(
        "Benchmarking needs an execution command. Provide one, or enable " +
          "\"Skip benchmarking\" to stop after verification.",
      );
      return;
    }

    setRunning(true);
    setError(null);
    setPercent(0);
    setElapsed(0);
    setLog([]);
    setDetections([]);
    setCandidates([]);
    setResult(null);
    setSelectedId(null);
    setStage("detect");
    setStatusText("Starting pipeline…");

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await streamPost(
        "/api/pipeline/run/stream",
        {
          file_path: settings.filePath.trim(),
          language: settings.language,
          command: settings.command.trim(),
          project_path: settings.projectPath.trim() || null,
          num_candidates: Number(numCandidates) || 1,
          runs: Number(runs) || 1,
          warmup_runs: Number(warmupRuns) || 0,
          timeout: Number(settings.timeout) || 300,
          min_improvement_percent: Number(minImprovement) || 5,
          skip_benchmark: skipBenchmark,
        },
        (event: StreamEvent) => {
          if (event.percent != null) setPercent(Number(event.percent));
          if (event.stage) setStage(String(event.stage));
          if (event.message) setStatusText(String(event.message));

          if (event.type === "progress") {
            appendLog(String(event.message ?? ""));
            return;
          }

          if (event.type === "error") {
            throw new Error(String(event.message ?? "Pipeline failed"));
          }

          if (event.type === "partial") {
            const payload = (event.payload ?? {}) as Record<string, unknown>;

            if (event.stage === "detect") {
              const found = (payload.detections as Detection[]) ?? [];
              setDetections(found);
              appendLog(`Detected ${found.length} energy smell(s)`);
            }

            if (event.stage === "generate" && payload.candidates) {
              const generated = payload.candidates as Candidate[];
              setCandidates(generated);
              setSelectedId((current) => current ?? generated[0]?.candidate_id ?? null);
              appendLog(`Generated ${generated.length} candidate(s)`);
            }

            if (event.stage === "verify" && payload.candidate_id) {
              const verification = payload.verification as VerificationResult;
              patchCandidate(String(payload.candidate_id), {
                verification,
                correctness_status: verification?.status,
              });
              appendLog(`Candidate ${shortId(payload.candidate_id)}: ${verification?.status}`);
            }

            if (event.stage === "decide" && payload.candidate_id) {
              const decision = payload.decision as DecisionResult;
              patchCandidate(String(payload.candidate_id), {
                decision,
                final_status: decision?.status,
              });
              appendLog(`Candidate ${shortId(payload.candidate_id)}: ${decision?.status}`);
            }

            return;
          }

          if (event.type === "result") {
            const finalResult = event.result as PipelineResult;
            setResult(finalResult);
            setCandidates(finalResult.candidates ?? []);
            setDetections(finalResult.detections ?? []);
            setSelectedId((current) => current ?? finalResult.candidates?.[0]?.candidate_id ?? null);
            setPercent(100);
            setStatusText("Pipeline complete");
            appendLog("Pipeline complete.");
            setImprove({
              candidates: finalResult.candidates ?? [],
              result: finalResult,
              ranAt: new Date().toISOString(),
            });
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
        setStatusText("Pipeline failed");
        appendLog(`ERROR: ${message}`);
      }
    } finally {
      controllerRef.current = null;
      setRunning(false);
    }
  }

  function handleStop() {
    controllerRef.current?.abort();
  }

  const noDetections = result?.stopped_reason === "no_detections";
  const selected = candidates.find((candidate) => candidate.candidate_id === selectedId) ?? candidates[0] ?? null;
  const verified = candidates.filter((candidate) => candidate.correctness_status === "VERIFIED").length;
  const measured = candidates.filter((candidate) => candidate.benchmark?.status === "MEASURED").length;
  const decided = candidates.filter((candidate) => decisions[candidate.candidate_id]).length;

  const stageIndex = PIPELINE_STEPS.findIndex((item) => item.key === stage);

  return (
    <>
      <StageHeader
        stage="improve"
        title="Generate and prove candidate fixes"
        description="Generate candidate fixes, check correctness, and measure energy."
      />
      <StageSteps current="improve" />
      <WorkspaceBar disabled={running} />

      {running ? (
        <GuidanceBar
          tone="info"
          eyebrow="Pipeline running"
          message={`${PIPELINE_STEPS[Math.max(0, stageIndex)]?.label ?? "Working"} — ${
            statusText || "streaming stages"
          }. Candidates appear as they are generated.`}
        />
      ) : candidates.length > 0 ? (
        <GuidanceBar
          message={
            <>
              <strong>{candidates.length}</strong> candidate
              {candidates.length === 1 ? "" : "s"} · {verified} verified · {measured} measured.
              Review the evidence next.
            </>
          }
          action={
            <Link href="/workspace/decide" className={buttonPrimary}>
              Review decisions →
            </Link>
          }
        />
      ) : (
        <GuidanceBar
          tone={scan ? "accent" : "muted"}
          eyebrow={scan ? "Ready to improve" : "Optional step"}
          message={
            scan && scan.detections.length > 0 ? (
              <>
                <strong>{scan.detections.length}</strong> smell
                {scan.detections.length === 1 ? "" : "s"} in{" "}
                <span className="font-mono text-xs">
                  {targetName(settings.filePath) || "this file"}
                </span>
                . Run the pipeline to propose fixes.
              </>
            ) : (
              "Run the pipeline to detect and propose fixes."
            )
          }
        />
      )}

      {llm && !llm.configured ? (
        <div className="mb-5">
          <Alert tone="warn" title="Candidate generation needs an LLM key">
            {llm.hint ?? "Set GEMINI_API_KEY in OASIS/.env and restart the backend to enable generation."}
          </Alert>
        </div>
      ) : null}

      <Card className="mb-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label className="block lg:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-muted">File to optimize</span>
            <input
              className={inputClass}
              value={settings.filePath}
              onChange={(event) => updateSettings({ filePath: event.target.value })}
              placeholder="D:/projects/my_project/main.py"
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
              disabled={running || skipBenchmark}
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-muted">Project path (optional)</span>
            <input
              className={inputClass}
              value={settings.projectPath}
              onChange={(event) => updateSettings({ projectPath: event.target.value })}
              placeholder="Defaults to the file's folder"
              disabled={running}
            />
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={buttonPrimary}
            onClick={() => void handleRun()}
            disabled={running}
          >
            {running ? "Running pipeline…" : candidates.length > 0 ? "Run again" : "Run pipeline"}
          </button>
          <button
            type="button"
            className={buttonGhost}
            onClick={handleStop}
            disabled={!running}
          >
            ■ Stop
          </button>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 accent-[var(--color-accent)]"
              checked={skipBenchmark}
              onChange={(event) => setSkipBenchmark(event.target.checked)}
              disabled={running}
            />
            Skip benchmarking
          </label>
          {running ? <Spinner label={statusText} /> : null}
        </div>

        <Disclosure
          title="Advanced run settings"
          overline="Optional"
          summary={`${numCandidates} candidates · ${skipBenchmark ? "no benchmark" : `${runs} measured run(s) + ${warmupRuns} warm-up`} · ${minImprovement}% threshold`}
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <NumberField label="Candidates" value={numCandidates} onChange={setNumCandidates} min={1} max={5} disabled={running} />
            <NumberField label="Measured runs / version" value={runs} onChange={setRuns} min={1} max={10} disabled={running || skipBenchmark} />
            <NumberField label="Warm-up runs" value={warmupRuns} onChange={setWarmupRuns} min={0} max={5} disabled={running || skipBenchmark} />
            <NumberField label="Run timeout (s)" value={settings.timeout} onChange={(value) => updateSettings({ timeout: value })} min={10} max={3600} disabled={running} />
            <NumberField label="Minimum improvement (%)" value={minImprovement} onChange={setMinImprovement} min={0} max={100} disabled={running} />
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-muted">
            Behaviour changes are rejected regardless of savings. Skipping the benchmark means
            nothing can be called improved.
          </p>
        </Disclosure>
      </Card>

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Pipeline failed">
            {error}
          </Alert>
        </div>
      ) : null}

      {/* ---------------- PIPELINE PROGRESS ---------------- */}
      {(running || log.length > 0) && (
        <Card className="mb-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="overline mb-0.5">Pipeline</p>
              <p className="text-sm font-semibold text-ink">{statusText}</p>
            </div>
            <span className="font-mono text-xs text-muted">
              {Math.round(percent)}% · {formatElapsed(elapsed)}
            </span>
          </div>

          <ol className="mb-3 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
            {PIPELINE_STEPS.map((item, index) => {
              const done = result !== null || index < stageIndex;
              const active = running && index === stageIndex;
              return (
                <li
                  key={item.key}
                  className={`rounded-md border px-2 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wide ${
                    done
                      ? "border-accent/40 bg-accent-soft/50 text-accent"
                      : active
                        ? "border-accent/60 bg-accent-soft text-ink"
                        : "border-line bg-surface-2 text-muted"
                  }`}
                >
                  {done ? "✓ " : ""}
                  {item.label}
                </li>
              );
            })}
          </ol>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-300"
              style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
            />
          </div>

          {log.length > 0 ? (
            <details className="group mt-3">
              <summary className="cursor-pointer text-[11px] font-medium text-muted hover:text-ink">
                Live log ({log.length}) ▾
              </summary>
              <div
                ref={logRef}
                className="mt-2 max-h-44 overflow-y-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-muted"
              >
                {log.map((line, index) => (
                  <div key={`${index}-${line.slice(0, 12)}`}>{line}</div>
                ))}
              </div>
            </details>
          ) : null}
        </Card>
      )}

      {noDetections ? (
        <EmptyState
          icon="✓"
          title="No energy smells detected"
          message={result?.message ?? "Nothing was detected, so there was nothing to optimize."}
        />
      ) : null}

      {!running && candidates.length === 0 && !noDetections ? (
        <EmptyState
          icon="✦"
          title="No candidates yet"
          message="Run the pipeline to generate and measure candidate fixes."
        />
      ) : null}

      {/* ---------------- SUMMARY ---------------- */}
      {candidates.length > 0 ? (
        <>
          <Grid columns={3} className="mb-5">
            <MetricCard label="Candidates" value={formatInteger(candidates.length)} tone="info" hint="Generated by the LLM" />
            <MetricCard label="Verified" value={formatInteger(verified)} tone="accent" hint="Behaviour preserved" />
            <MetricCard
              label="Improved"
              value={formatInteger(candidates.filter((item) => item.final_status === "IMPROVED").length)}
              tone="accent"
              emphasized
              hint={result?.summary?.best_improvement_percent != null ? `Best: ${formatPercent(result.summary.best_improvement_percent)}` : "Measured, not predicted"}
            />
          </Grid>

          {result && !result.benchmark_ran ? (
            <p className="mb-4 text-xs text-muted">
              Benchmarking was skipped: candidates are verified, not improved.
            </p>
          ) : null}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            {/* ---------------- LIST ---------------- */}
            <div className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="border-b border-line bg-surface-2/40 px-3 py-2">
                <p className="overline">Candidates</p>
              </div>
              <ul className="max-h-[34rem] divide-y divide-line/70 overflow-y-auto">
                {candidates.map((candidate, index) => {
                  const active = selected?.candidate_id === candidate.candidate_id;
                  const measuredPercent = candidate.measured_energy?.improvement_percent ?? null;
                  return (
                    <li key={candidate.candidate_id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(candidate.candidate_id)}
                        aria-pressed={active}
                        className={`flex w-full items-start gap-2 px-3 py-2.5 text-left transition ${
                          active ? "bg-accent-soft/50" : "hover:bg-surface-2/60"
                        }`}
                      >
                        <span
                          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                            active ? "bg-accent text-canvas" : "bg-surface-3 text-muted"
                          }`}
                        >
                          {candidate.rank ?? index + 1}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-1.5">
                            <span className="truncate font-mono text-[11px] text-ink">
                              {shortId(candidate.candidate_id, 8)}
                            </span>
                            <Badge tone={statusTone(candidate.final_status)}>
                              {candidate.final_status ?? "PREDICTED"}
                            </Badge>
                          </span>
                          <span className="mt-0.5 block truncate text-[10px] text-muted">
                            {candidate.strategy ?? "Candidate change"}
                          </span>
                          <span className="mt-0.5 block font-mono text-[10px] text-muted">
                            {measuredPercent != null
                              ? `${formatSignedPercent(measuredPercent)} measured`
                              : "not measured"}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            {/* ---------------- DETAIL ---------------- */}
            <div>
              {selected ? (
                <CandidateDetail candidate={selected} />
              ) : (
                <EmptyState icon="◎" title="No candidate selected" message="Pick a candidate from the list." />
              )}
            </div>
          </div>

          {detections.length > 0 ? (
            <div className="mt-5">
              <DisclosureStack>
                <Disclosure
                  title="Detected energy smells"
                  overline="Input to generation"
                  summary={`${detections.length} finding(s) guided the candidates`}
                >
                  <FindingsSummary detections={detections} />
                </Disclosure>
              </DisclosureStack>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  disabled,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        className={inputClass}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        disabled={disabled}
      />
    </label>
  );
}

/* ============================================================
   CANDIDATE DETAIL
   ============================================================ */

function CandidateDetail({ candidate }: { candidate: Candidate }) {
  const decision = candidate.decision;
  const verification = candidate.verification;
  const benchmark = candidate.benchmark;
  const measured = candidate.measured_energy;
  const changes = candidate.changes_made ?? [];

  const originalJoules = benchmark?.original_summary?.mean_energy_joules ?? measured?.original_mean_joules ?? null;
  const candidateJoules = benchmark?.candidate_summary?.mean_energy_joules ?? measured?.candidate_mean_joules ?? null;
  const chartMax = Math.max(originalJoules ?? 0, candidateJoules ?? 0, 1e-9);
  const spread =
    benchmark?.original_summary?.energy_spread_percent ??
    benchmark?.candidate_summary?.energy_spread_percent ??
    null;

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone="violet">{candidate.rank ? `Rank ${candidate.rank}` : "Candidate"}</Badge>
        <span className="font-mono text-xs text-muted">{shortId(candidate.candidate_id)}</span>
        <Badge tone={statusTone(candidate.final_status)}>
          {candidate.final_status ?? "PREDICTED"}
        </Badge>
        {candidate.score != null ? (
          <span className="text-[11px] text-muted">Score {formatPercent(candidate.score, 1)}</span>
        ) : null}
      </div>

      <p className="mb-4 text-sm leading-relaxed text-ink/90">
        {candidate.strategy ?? candidate.explanation ?? "No strategy description was returned."}
      </p>

      <Grid columns={3} className="mb-4">
        <MetricCard
          label="Predicted impact"
          value={candidate.predicted_impact ?? "—"}
          tone="violet"
          hint="Model estimate only"
        />
        <MetricCard
          label="Measured energy change"
          value={measured?.improvement_percent != null ? formatSignedPercent(measured.improvement_percent) : "Not measured"}
          tone={
            measured?.improvement_percent == null
              ? "muted"
              : measured.improvement_percent > 0
                ? "accent"
                : "danger"
          }
          emphasized={measured?.improvement_percent != null}
          hint={
            originalJoules != null
              ? `${formatJoules(originalJoules)} → ${formatJoules(candidateJoules)}`
              : "Needs a benchmark run"
          }
        />
        <MetricCard
          label="Correctness"
          value={candidate.correctness_status ?? "—"}
          tone={statusTone(candidate.correctness_status)}
          hint={
            verification?.tests_total
              ? `${verification.tests_passed}/${verification.tests_total} checks passed`
              : "Syntax + behaviour comparison"
          }
        />
      </Grid>

      {originalJoules != null || candidateJoules != null ? (
        <div className="mb-4 rounded-lg border border-line bg-surface-2/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="overline">Measured energy comparison</p>
            <span className="text-[10px] text-muted">
              {benchmark?.runs_per_version ?? "—"} run(s) / version
              {spread != null ? ` · ${formatPercent(spread, 1)} spread` : ""}
            </span>
          </div>
          <ComparisonBar label="Original" joules={originalJoules} max={chartMax} className="bg-muted" />
          <ComparisonBar label="Candidate" joules={candidateJoules} max={chartMax} className="bg-accent" />
          {benchmark?.verdict ? (
            <p className="mt-2 text-[11px] text-muted">{benchmark.verdict}</p>
          ) : null}
        </div>
      ) : null}

      {decision ? (
        <div
          className={`mb-4 rounded-lg border px-3 py-2.5 ${
            candidate.final_status === "IMPROVED"
              ? "border-accent/40 bg-accent-soft/40"
              : candidate.final_status === "REGRESSED" || candidate.final_status === "FAILED"
                ? "border-danger/40 bg-danger-soft/40"
                : "border-warn/40 bg-warn-soft/40"
          }`}
        >
          <p className="text-sm font-semibold text-ink">{decision.recommendation}</p>
          <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-[11px] leading-relaxed text-muted">
            {decision.rationale.slice(0, 4).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {verification?.checks?.length ? (
        <Disclosure
          title="Verification checks"
          overline="Correctness"
          summary={`${verification.checks.filter((check) => check.passed).length}/${verification.checks.length} passed`}
        >
          <ul className="space-y-1.5">
            {verification.checks.map((check) => (
              <li key={check.name} className="flex items-start gap-2 text-xs">
                <span
                  className={`mt-0.5 font-bold ${
                    check.passed === true
                      ? "text-accent"
                      : check.passed === false
                        ? "text-danger"
                        : "text-muted"
                  }`}
                >
                  {check.passed === true ? "✓" : check.passed === false ? "✕" : "–"}
                </span>
                <span className="min-w-0">
                  <span className="text-ink">{check.name}</span>
                  {check.detail ? (
                    <span className="block text-[11px] text-muted">{check.detail}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}

      {changes.length > 0 ? (
        <div className="mt-4 space-y-2">
          <p className="overline">Changes made</p>
          {changes.map((change, index) => (
            <div key={`${change.smell_id ?? "change"}-${index}`} className="rounded-lg border border-line bg-surface-2/40 p-3">
              {change.description ? (
                <p className="mb-2 text-xs text-ink/90">{change.description}</p>
              ) : null}
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div>
                  <p className="overline mb-1 text-danger/80">Before</p>
                  <pre className="max-h-40 overflow-auto rounded border border-line bg-canvas p-2 font-mono text-[10px] leading-relaxed text-ink/80">
                    {change.before?.trim() || "(not returned)"}
                  </pre>
                </div>
                <div>
                  <p className="overline mb-1 text-accent/80">After</p>
                  <pre className="max-h-40 overflow-auto rounded border border-line bg-canvas p-2 font-mono text-[10px] leading-relaxed text-ink/80">
                    {change.after?.trim() || "(not returned)"}
                  </pre>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {candidate.source_code ? (
        <div className="mt-4">
          <Disclosure
            title="Full candidate source"
            overline="Generated code"
            summary={`${candidate.source_code.split("\n").length} lines · ${candidate.model ?? candidate.generation_method ?? "LLM"}`}
          >
            <CodeBlock code={candidate.source_code} language={candidate.candidate_id} maxHeight={420} />
          </Disclosure>
        </div>
      ) : null}
    </Card>
  );
}

function ComparisonBar({
  label,
  joules,
  max,
  className,
}: {
  label: string;
  joules: number | null;
  max: number;
  className: string;
}) {
  const width = joules == null ? 0 : Math.max(1, Math.min(100, (joules / max) * 100));
  return (
    <div className="mb-1.5 flex items-center gap-2 text-[11px]">
      <span className="w-16 shrink-0 text-muted">{label}</span>
      <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-3">
        <span className={`block h-full rounded-full ${className}`} style={{ width: `${width}%` }} />
      </span>
      <span className="w-24 shrink-0 text-right font-mono text-muted">{formatJoules(joules)}</span>
    </div>
  );
}

function FindingsSummary({ detections }: { detections: Detection[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-line bg-surface-2">
            {["Severity", "Subcategory", "Location", "Description"].map((column) => (
              <th key={column} className="whitespace-nowrap px-3 py-2 font-semibold text-muted">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {detections.map((detection, index) => (
            <tr key={`${detection.subcategory_id}-${index}`} className="border-b border-line/50 last:border-b-0">
              <td className="px-3 py-1.5 uppercase">{detection.severity}</td>
              <td className="px-3 py-1.5">{detection.subcategory_id} — {detection.subcategory_name}</td>
              <td className="px-3 py-1.5 font-mono text-muted">
                {detection.location?.function ?? ""}
                {detection.location?.line ? `:${detection.location.line}` : ""}
              </td>
              <td className="max-w-[30rem] px-3 py-1.5 text-muted">{detection.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
