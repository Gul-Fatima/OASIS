"use client";

/**
 * Optimization pipeline: detect → generate → rank → verify → benchmark → decide.
 *
 * The UI enforces the project's central rule visually: predicted impact and
 * measured improvement are always shown as separate, clearly labelled figures,
 * and the verdict on each candidate comes from the decision record the backend
 * produced from measurements.
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
  buttonGhost,
  buttonPrimary,
  inputClass,
  type Tone,
} from "@/components/ui";
import { apiPost, streamPost, type StreamEvent } from "@/lib/api";
import {
  formatDuration,
  formatElapsed,
  formatEnergy,
  formatInteger,
  formatJoules,
  formatPercent,
  formatSignedPercent,
  formatWatts,
  shortId,
} from "@/lib/format";
import type {
  BenchmarkResult,
  Candidate,
  DecisionResult,
  Detection,
  DetectionSummary,
  LlmStatus,
  PipelineResult,
  VerificationResult,
} from "@/lib/types";

const LANGUAGES = [
  { value: "auto", label: "Auto-detect" },
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "javascript", label: "JavaScript" },
  { value: "c", label: "C" },
  { value: "cpp", label: "C++" },
];

const STAGE_LABELS: Record<string, string> = {
  detect: "1 · Detect energy smells",
  generate: "2 · Generate candidates",
  rank: "3 · Rank candidates",
  verify: "4 · Verify correctness",
  benchmark: "5 · Benchmark energy",
  decide: "6 · Decide",
  report: "7 · Report",
};

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

export function CandidatesView() {
  // -------------------- form --------------------
  const [filePath, setFilePath] = useState("");
  const [language, setLanguage] = useState("auto");
  const [command, setCommand] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [numCandidates, setNumCandidates] = useState(2);
  const [runs, setRuns] = useState(2);
  const [warmupRuns, setWarmupRuns] = useState(1);
  const [timeout, setTimeoutSeconds] = useState(300);
  const [minImprovement, setMinImprovement] = useState(5);
  const [skipBenchmark, setSkipBenchmark] = useState(false);

  // -------------------- run state --------------------
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("detect");
  const [percent, setPercent] = useState(0);
  const [statusText, setStatusText] = useState("Ready");
  const [elapsed, setElapsed] = useState(0);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [detections, setDetections] = useState<Detection[]>([]);
  const [detectionSummary, setDetectionSummary] = useState<DetectionSummary | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [llm, setLlm] = useState<LlmStatus | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    apiGetLlm().then(setLlm).catch(() => setLlm(null));
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

  /** Replace one candidate in place as streamed evidence arrives. */
  function patchCandidate(id: string, patch: Partial<Candidate>) {
    setCandidates((previous) =>
      previous.map((candidate) =>
        candidate.candidate_id === id ? { ...candidate, ...patch } : candidate,
      ),
    );
  }

  async function handleRun() {
    if (!filePath.trim()) {
      setError("Enter the file to optimise.");
      return;
    }
    if (!skipBenchmark && !command.trim()) {
      setError(
        "Benchmarking needs an execution command. Provide one, or enable " +
          "'Skip benchmarking' to stop after verification.",
      );
      return;
    }

    setRunning(true);
    setError(null);
    setPercent(0);
    setElapsed(0);
    setLog([]);
    setDetections([]);
    setDetectionSummary(null);
    setCandidates([]);
    setResult(null);
    setStage("detect");
    setStatusText("Starting pipeline…");

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await streamPost(
        "/api/pipeline/run/stream",
        {
          file_path: filePath.trim(),
          language,
          command: command.trim(),
          project_path: projectPath.trim() || null,
          num_candidates: Number(numCandidates) || 1,
          runs: Number(runs) || 1,
          warmup_runs: Number(warmupRuns) || 0,
          timeout: Number(timeout) || 300,
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
              setDetections((payload.detections as Detection[]) ?? []);
              setDetectionSummary(
                (payload.detection_summary as DetectionSummary) ?? null,
              );
              appendLog(
                `Detected ${((payload.detections as Detection[]) ?? []).length} energy smell(s)`,
              );
            }

            if (event.stage === "generate" && payload.candidates) {
              setCandidates(payload.candidates as Candidate[]);
              appendLog(`Generated ${(payload.candidates as Candidate[]).length} candidate(s)`);
            }

            if (event.stage === "verify" && payload.candidate_id) {
              const verification = payload.verification as VerificationResult;
              patchCandidate(String(payload.candidate_id), {
                verification,
                correctness_status: verification?.status,
              });
              appendLog(
                `Candidate ${shortId(payload.candidate_id)}: ${verification?.status}`,
              );
            }

            if (event.stage === "decide" && payload.candidate_id) {
              const decision = payload.decision as DecisionResult;
              patchCandidate(String(payload.candidate_id), {
                decision,
                final_status: decision?.status,
              });
              appendLog(
                `Candidate ${shortId(payload.candidate_id)}: ${decision?.status}`,
              );
            }

            return;
          }

          if (event.type === "result") {
            const finalResult = event.result as PipelineResult;
            setResult(finalResult);
            setCandidates(finalResult.candidates ?? []);
            setDetections(finalResult.detections ?? []);
            setDetectionSummary(finalResult.detection_summary ?? null);
            setPercent(100);
            setStatusText("Pipeline complete");
            appendLog("Pipeline complete.");
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

  const summary = result?.summary;
  const noDetections = result?.stopped_reason === "no_detections";

  return (
    <>
      <PageHeader
        overline="Generate · Verify · Measure · Decide"
        title="Optimization Pipeline"
        description="Turn detected energy smells into candidate implementations, prove they still behave correctly, measure whether they actually use less energy, and record the accept/reject decision."
      />

      <div className="mb-5">
        <Alert tone="accent" title="Correctness gates everything">
          A candidate that changes behaviour is rejected regardless of how much energy
          it saves. A candidate that is correct but only looks faster is not an
          optimization until a measured run says so.
        </Alert>
      </div>

      <Card className="mb-5">
        <SectionHeader
          overline="New run"
          title="Configure the pipeline"
          actions={
            llm ? (
              <Badge tone={llm.configured ? "accent" : "warn"}>
                {llm.configured ? `LLM ready · ${llm.model}` : "LLM not configured"}
              </Badge>
            ) : null
          }
        />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="lg:col-span-2">
            <Field
              label="File to optimize"
              htmlFor="filePath"
              hint="The file containing the detected smells. Other files in the project are left untouched."
            >
              <input
                id="filePath"
                className={inputClass}
                value={filePath}
                onChange={(event) => setFilePath(event.target.value)}
                placeholder="D:/projects/my_project/main.py"
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
            hint="Required for benchmarking — the same command runs against both versions."
          >
            <input
              id="command"
              className={inputClass}
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              placeholder="python main.py"
              disabled={running || skipBenchmark}
            />
          </Field>

          <Field
            label="Project path (optional)"
            htmlFor="projectPath"
            hint="Benchmarks run in an isolated copy of this folder. Defaults to the file's folder."
          >
            <input
              id="projectPath"
              className={inputClass}
              value={projectPath}
              onChange={(event) => setProjectPath(event.target.value)}
              placeholder="leave empty to use the file's folder"
              disabled={running}
            />
          </Field>

          <Field label="Candidates to generate" htmlFor="numCandidates">
            <input
              id="numCandidates"
              type="number"
              min={1}
              max={5}
              className={inputClass}
              value={numCandidates}
              onChange={(event) => setNumCandidates(Number(event.target.value))}
              disabled={running}
            />
          </Field>

          <Field label="Measured runs per version" htmlFor="runs">
            <input
              id="runs"
              type="number"
              min={1}
              max={10}
              className={inputClass}
              value={runs}
              onChange={(event) => setRuns(Number(event.target.value))}
              disabled={running || skipBenchmark}
            />
          </Field>

          <Field
            label="Warm-up runs"
            htmlFor="warmupRuns"
            hint="Discarded runs that stabilise CPU frequency before measuring."
          >
            <input
              id="warmupRuns"
              type="number"
              min={0}
              max={5}
              className={inputClass}
              value={warmupRuns}
              onChange={(event) => setWarmupRuns(Number(event.target.value))}
              disabled={running || skipBenchmark}
            />
          </Field>

          <Field label="Run timeout (seconds)" htmlFor="timeout">
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

          <Field
            label="Minimum improvement to call it improved (%)"
            htmlFor="minImprovement"
            hint="Raised automatically when the measured spread is larger than this."
          >
            <input
              id="minImprovement"
              type="number"
              min={0}
              max={100}
              className={inputClass}
              value={minImprovement}
              onChange={(event) => setMinImprovement(Number(event.target.value))}
              disabled={running}
            />
          </Field>

          <div className="flex items-end">
            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
                checked={skipBenchmark}
                onChange={(event) => setSkipBenchmark(event.target.checked)}
                disabled={running}
              />
              <span>
                Skip benchmarking (generate + verify only)
                <span className="mt-0.5 block text-xs text-muted">
                  Stops after correctness. No measured energy is produced, so no
                  candidate can be called improved.
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
            ⚡ Run pipeline
          </button>
          <button
            type="button"
            className={buttonGhost}
            onClick={handleStop}
            disabled={!running}
          >
            ■ Stop
          </button>
          {running ? <Spinner label={statusText} /> : (
            <span className="text-xs text-muted">{statusText}</span>
          )}
        </div>

        {running || log.length > 0 ? (
          <div className="mt-5">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
              <span>{STAGE_LABELS[stage] ?? stage}</span>
              <span className="font-mono">
                {Math.round(percent)}% · {formatElapsed(elapsed)}
              </span>
            </div>
            <ProgressBar percent={percent} />
            {log.length > 0 ? (
              <div
                ref={logRef}
                className="mt-3 max-h-44 overflow-y-auto rounded-lg border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-muted"
              >
                {log.map((line, index) => (
                  <div key={`${index}-${line.slice(0, 12)}`}>{line}</div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </Card>

      {llm && !llm.configured ? (
        <div className="mb-5">
          <Alert tone="warn" title="Candidate generation needs a Gemini API key">
            {llm.hint ??
              "Set GEMINI_API_KEY in OASIS/.env and restart the backend to enable generation."}
          </Alert>
        </div>
      ) : null}

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Pipeline failed">
            {error}
          </Alert>
        </div>
      ) : null}

      {!result && candidates.length === 0 && !running ? (
        <EmptyState
          icon="✦"
          title="No run yet"
          message="Configure the pipeline above and run it. Detected smells, generated candidates, verification results and measured energy all appear here."
        />
      ) : null}

      {noDetections ? (
        <EmptyState
          icon="✓"
          title="No energy smells detected"
          message={
            result?.message ??
            "Nothing was detected, so no candidates were generated. Detection is a hypothesis — an empty result means no rule matched."
          }
        />
      ) : null}

      {(candidates.length > 0 || detections.length > 0) && !noDetections ? (
        <>
          <section className="mb-5">
            <SectionHeader overline="Summary" title="Pipeline outcome" />

            <Grid columns={5}>
              <MetricCard
                label="Smells detected"
                value={formatInteger(detectionSummary?.detection_count ?? detections.length)}
                hint="Static hypotheses, not measurements"
              />
              <MetricCard
                label="Candidates"
                value={formatInteger(summary?.candidates_generated ?? candidates.length)}
                tone="info"
                hint="Generated by the LLM"
              />
              <MetricCard
                label="Verified correct"
                value={formatInteger(
                  summary?.verified ??
                    candidates.filter((item) => item.correctness_status === "VERIFIED")
                      .length,
                )}
                tone="accent"
                hint="Behaviour matched the original"
              />
              <MetricCard
                label="Measured"
                value={formatInteger(
                  summary?.measured ??
                    candidates.filter(
                      (item) => item.benchmark?.status === "MEASURED",
                    ).length,
                )}
                hint="Benchmarks that produced usable data"
              />
              <MetricCard
                label="Improved"
                value={formatInteger(
                  summary?.improved ??
                    candidates.filter((item) => item.final_status === "IMPROVED").length,
                )}
                tone={
                  (summary?.improved ??
                    candidates.filter((item) => item.final_status === "IMPROVED").length) > 0
                    ? "accent"
                    : "muted"
                }
                emphasized
                hint={
                  summary?.best_improvement_percent != null
                    ? `Best measured saving: ${formatPercent(
                        summary.best_improvement_percent,
                      )}`
                    : "Measured, not predicted"
                }
              />
            </Grid>

            {result && !result.benchmark_ran ? (
              <p className="mt-3 text-xs text-muted">
                Benchmarking was skipped, so no measured energy exists for this run —
                candidates are correct at best, never “improved”.
              </p>
            ) : null}
          </section>

          {candidates.map((candidate) => (
            <CandidateCard key={candidate.candidate_id} candidate={candidate} />
          ))}

          <section className="mb-8">
            <DisclosureStack>
              <Disclosure
                title="Detected energy smells"
                overline="Input to generation"
                summary={`${detections.length} finding(s) guided the LLM`}
              >
                <div className="overflow-x-auto rounded-lg border border-line">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-line bg-surface-2">
                        {["Category", "Subcategory", "Severity", "Location", "Description"].map(
                          (column) => (
                            <th
                              key={column}
                              className="whitespace-nowrap px-3 py-2 font-semibold text-muted"
                            >
                              {column}
                            </th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {detections.map((detection, index) => (
                        <tr
                          key={`${detection.subcategory_id}-${index}`}
                          className="border-b border-line/50 last:border-b-0"
                        >
                          <td className="px-3 py-1.5">
                            {detection.category_id} — {detection.category_name}
                          </td>
                          <td className="px-3 py-1.5">{detection.subcategory_id}</td>
                          <td className="px-3 py-1.5">{detection.severity}</td>
                          <td className="px-3 py-1.5 font-mono">
                            {detection.location?.function ?? ""}
                            {detection.location?.line ? `:${detection.location.line}` : ""}
                          </td>
                          <td className="max-w-[30rem] px-3 py-1.5 text-muted">
                            {detection.description}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
   CANDIDATE CARD
   ============================================================ */

function CandidateCard({ candidate }: { candidate: Candidate }) {
  const [recorded, setRecorded] = useState<string | null>(null);
  const [recordError, setRecordError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const finalStatus = candidate.final_status ?? "PREDICTED";
  const decision = candidate.decision;
  const verification = candidate.verification;
  const benchmark = candidate.benchmark;
  const measured = candidate.measured_energy;

  async function record(action: "ACCEPTED" | "REJECTED") {
    setSaving(true);
    setRecordError(null);
    try {
      await apiPost("/api/candidates/decision/record", {
        candidate_id: candidate.candidate_id,
        status: finalStatus,
        developer_action: action,
        rationale: decision?.rationale ?? [],
        measured_improvement_percent: measured?.improvement_percent ?? null,
      });
      setRecorded(action);
    } catch (caught) {
      setRecordError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="mb-4">
      {/* ---------- HEADER ---------- */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone="violet">
          {candidate.rank ? `Rank ${candidate.rank}` : "Candidate"}
        </Badge>
        <span className="font-mono text-xs text-muted">
          {shortId(candidate.candidate_id)}
        </span>
        <Badge tone={statusTone(finalStatus)}>{finalStatus}</Badge>
        {candidate.score != null ? (
          <span className="text-xs text-muted">Score {formatPercent(candidate.score, 1)}</span>
        ) : null}
        {recorded ? (
          <Badge tone={recorded === "ACCEPTED" ? "accent" : "danger"} className="ml-auto">
            {recorded}
          </Badge>
        ) : null}
      </div>

      <p className="mb-4 text-sm leading-relaxed text-ink/90">
        {candidate.strategy ?? "No strategy description was returned."}
      </p>

      {/* ---------- PREDICTED vs MEASURED ---------- */}
      <Grid columns={4} className="mb-4">
        <MetricCard
          label="Predicted impact (LLM)"
          value={candidate.predicted_impact ?? "—"}
          tone="violet"
          hint="A prediction. It never decides the outcome."
        />
        <MetricCard
          label="Model confidence"
          value={
            candidate.confidence != null ? formatPercent(candidate.confidence * 100, 0) : "—"
          }
          hint="Self-reported by the model"
        />
        <MetricCard
          label="Measured energy change"
          value={
            measured?.improvement_percent != null
              ? formatSignedPercent(measured.improvement_percent)
              : "Not measured"
          }
          tone={
            measured?.improvement_percent == null
              ? "muted"
              : measured.improvement_percent > 0
                ? "accent"
                : "danger"
          }
          emphasized={measured?.improvement_percent != null}
          hint={
            measured?.original_mean_joules != null
              ? `From ${formatJoules(measured.original_mean_joules)} to ${formatJoules(
                  measured.candidate_mean_joules,
                )}`
              : "Needs a benchmark run"
          }
        />
        <MetricCard
          label="Correctness"
          value={candidate.correctness_status ?? "—"}
          tone={statusTone(candidate.correctness_status)}
          hint={
            verification?.tests_total
              ? `${verification.tests_passed}/${verification.tests_total} test cases`
              : "Syntax + behaviour comparison"
          }
        />
      </Grid>

      {decision ? (
        <div
          className={`mb-4 rounded-lg border px-4 py-3 ${
            finalStatus === "IMPROVED"
              ? "border-accent/40 bg-accent-soft/40"
              : finalStatus === "REGRESSED" || finalStatus === "FAILED"
                ? "border-danger/40 bg-danger-soft/40"
                : "border-warn/40 bg-warn-soft/40"
          }`}
        >
          <p className="text-sm font-semibold text-ink">{decision.recommendation}</p>
          <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs leading-relaxed text-muted">
            {decision.rationale.slice(0, 4).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ---------- ACTIONS ---------- */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={buttonPrimary}
          disabled={saving || recorded !== null}
          onClick={() => void record("ACCEPTED")}
        >
          ✓ Accept optimization
        </button>
        <button
          type="button"
          className={buttonGhost}
          disabled={saving || recorded !== null}
          onClick={() => void record("REJECTED")}
        >
          ✕ Reject
        </button>
        <span className="text-[11px] text-muted">
          Final adoption is a developer decision; recording it stores the evidence trail.
        </span>
      </div>

      {recordError ? (
        <div className="mb-4">
          <Alert tone="danger" title="Could not record the decision">
            {recordError}
          </Alert>
        </div>
      ) : null}

      {/* ---------- DETAILS ---------- */}
      <DisclosureStack>
        <Disclosure
          title="Generated source code"
          overline="Candidate"
          summary={`${candidate.source_code?.split("\n").length ?? 0} lines · ${candidate.model ?? "unknown model"}`}
        >
          <CodeBlock
            code={candidate.source_code ?? ""}
            language={candidate.generation_method ?? undefined}
            maxHeight={420}
          />
        </Disclosure>

        <Disclosure
          title="Reported changes"
          overline="What the model says it changed"
          summary={`${candidate.changes_made?.length ?? 0} change(s) · targets ${
            candidate.target_smells?.join(", ") || "unspecified smells"
          }`}
        >
          {candidate.changes_made?.length ? (
            <div className="space-y-3">
              {candidate.changes_made.map((change, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-line bg-surface-2/50 p-3"
                >
                  <div className="mb-2 flex items-center gap-2">
                    {change.smell_id ? <Badge tone="violet">{change.smell_id}</Badge> : null}
                    <span className="text-xs text-ink/90">{change.description}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                    {change.before ? (
                      <div>
                        <p className="overline mb-1">Before</p>
                        <CodeBlock code={change.before} maxHeight={160} />
                      </div>
                    ) : null}
                    {change.after ? (
                      <div>
                        <p className="overline mb-1">After</p>
                        <CodeBlock code={change.after} maxHeight={160} />
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted">
              The model did not report discrete changes for this candidate.
            </p>
          )}
        </Disclosure>

        <Disclosure
          title="Correctness verification"
          overline="Gate 1"
          summary={`${verification?.status ?? "not run"}${
            verification?.inconclusive ? " (inconclusive)" : ""
          }`}
        >
          {verification ? (
            <div className="space-y-4">
              <KeyValue
                columns={3}
                items={[
                  { label: "Status", value: verification.status },
                  { label: "Passed", value: String(verification.passed) },
                  {
                    label: "Syntax",
                    value:
                      verification.syntax_ok == null
                        ? "not applicable"
                        : String(verification.syntax_ok),
                  },
                  {
                    label: "Behaviour",
                    value:
                      verification.behaviour_ok == null
                        ? "not comparable"
                        : String(verification.behaviour_ok),
                  },
                  {
                    label: "Test cases",
                    value: verification.tests_total
                      ? `${verification.tests_passed}/${verification.tests_total}`
                      : "none supplied",
                  },
                  {
                    label: "Inconclusive",
                    value: String(verification.inconclusive ?? false),
                  },
                ]}
              />

              {verification.checks?.length ? (
                <div className="overflow-x-auto rounded-lg border border-line">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead>
                      <tr className="border-b border-line bg-surface-2">
                        {["Check", "Result", "Detail"].map((column) => (
                          <th key={column} className="px-3 py-2 font-semibold text-muted">
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {verification.checks.map((check) => (
                        <tr
                          key={check.name}
                          className="border-b border-line/50 last:border-b-0"
                        >
                          <td className="px-3 py-1.5">{check.name}</td>
                          <td
                            className={`px-3 py-1.5 font-semibold ${
                              check.passed === true
                                ? "text-accent"
                                : check.passed === false
                                  ? "text-danger"
                                  : "text-muted"
                            }`}
                          >
                            {check.passed === null ? "skipped" : String(check.passed)}
                          </td>
                          <td className="px-3 py-1.5 text-muted">{check.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {verification.errors?.length ? (
                <Alert tone="danger" title="Verification errors">
                  <ul className="list-inside list-disc space-y-0.5">
                    {verification.errors.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </Alert>
              ) : null}

              {verification.notes?.length ? (
                <ul className="list-inside list-disc space-y-0.5 text-xs text-muted">
                  {verification.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <p className="text-xs text-muted">Verification has not run for this candidate.</p>
          )}
        </Disclosure>

        <Disclosure
          title="Energy benchmark"
          overline="Gate 2 · measured"
          summary={
            benchmark
              ? `${benchmark.status}${
                  benchmark.improvement_percent != null
                    ? ` · ${formatSignedPercent(benchmark.improvement_percent)}`
                    : ""
                }`
              : "not run"
          }
        >
          {benchmark ? (
            <BenchmarkDetails benchmark={benchmark} />
          ) : (
            <p className="text-xs text-muted">
              No benchmark was run, so no measured energy is available.
            </p>
          )}
        </Disclosure>

        <Disclosure
          title="Decision record"
          overline="Outcome"
          summary={decision ? `${decision.status} · ${decision.recommendation}` : "not decided"}
        >
          {decision ? (
            <div className="space-y-4">
              <KeyValue
                columns={3}
                items={[
                  { label: "Status", value: decision.status },
                  {
                    label: "Measured improvement",
                    value:
                      decision.measured_improvement_percent != null
                        ? formatSignedPercent(decision.measured_improvement_percent)
                        : "—",
                  },
                  {
                    label: "Threshold applied",
                    value:
                      decision.considered_noise_floor_percent != null
                        ? `${decision.considered_noise_floor_percent}%`
                        : "—",
                  },
                  { label: "Correctness", value: decision.correctness_status ?? "—" },
                  { label: "Benchmark", value: decision.benchmark_status ?? "—" },
                  { label: "Predicted impact", value: decision.predicted_impact ?? "—" },
                ]}
              />
              <ul className="list-inside list-disc space-y-1 text-xs leading-relaxed text-muted">
                {decision.rationale.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-muted">No decision was recorded.</p>
          )}
        </Disclosure>

        <Disclosure
          title="Ranking factors"
          overline="Prioritisation"
          summary={
            candidate.rationale?.length
              ? candidate.rationale[0]
              : "No ranking explanation"
          }
        >
          {candidate.rationale?.length ? (
            <div className="space-y-3">
              <ul className="list-inside list-disc space-y-1 text-xs text-muted">
                {candidate.rationale.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              {candidate.factors ? (
                <KeyValue
                  columns={3}
                  items={Object.entries(candidate.factors).map(([key, value]) => ({
                    label: key.replace(/_/g, " "),
                    value: formatPercent(value * 100, 1),
                  }))}
                />
              ) : null}
              {candidate.missing_inputs?.length ? (
                <Alert tone="warn" title="Values defaulted">
                  These inputs were missing and treated as zero:{" "}
                  {candidate.missing_inputs.join(", ")}.
                </Alert>
              ) : null}
            </div>
          ) : (
            <p className="text-xs text-muted">This candidate was not ranked.</p>
          )}
        </Disclosure>
      </DisclosureStack>
    </Card>
  );
}

function BenchmarkDetails({ benchmark }: { benchmark: BenchmarkResult }) {
  return (
    <div className="space-y-4">
      <KeyValue
        columns={3}
        items={[
          { label: "Status", value: benchmark.status },
          { label: "Verdict", value: benchmark.verdict ?? "—" },
          {
            label: "Measured improvement",
            value:
              benchmark.improvement_percent != null
                ? formatSignedPercent(benchmark.improvement_percent)
                : "—",
          },
          {
            label: "Runs per version",
            value: benchmark.runs_per_version ?? "—",
          },
          { label: "Warm-up runs", value: benchmark.warmup_runs ?? "—" },
          {
            label: "Total benchmark time",
            value: formatDuration(benchmark.duration_seconds),
          },
        ]}
      />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <SummaryBlock
          title="Original"
          summary={benchmark.original_summary}
        />
        <SummaryBlock
          title="Candidate"
          summary={benchmark.candidate_summary}
        />
      </div>

      {benchmark.original?.length || benchmark.candidate?.length ? (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-line bg-surface-2">
                {["Version", "Run", "Energy", "Duration", "Avg power", "OK"].map(
                  (column) => (
                    <th
                      key={column}
                      className="whitespace-nowrap px-3 py-2 font-semibold text-muted"
                    >
                      {column}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {[...(benchmark.original ?? []), ...(benchmark.candidate ?? [])].map(
                (run, index) => (
                  <tr key={index} className="border-b border-line/50 last:border-b-0">
                    <td className="px-3 py-1.5">{run.label}</td>
                    <td className="px-3 py-1.5">{run.index}</td>
                    <td className="px-3 py-1.5">{formatJoules(run.energy_joules)}</td>
                    <td className="px-3 py-1.5">
                      {formatDuration(run.duration_seconds)}
                    </td>
                    <td className="px-3 py-1.5">{formatWatts(run.average_watts)}</td>
                    <td
                      className={`px-3 py-1.5 font-semibold ${
                        run.success ? "text-accent" : "text-danger"
                      }`}
                    >
                      {run.success ? "yes" : "no"}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {benchmark.errors?.length ? (
        <Alert tone="danger" title="Benchmark problems">
          <ul className="list-inside list-disc space-y-0.5">
            {benchmark.errors.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {benchmark.notes?.length ? (
        <ul className="list-inside list-disc space-y-0.5 text-xs text-muted">
          {benchmark.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SummaryBlock({
  title,
  summary,
}: {
  title: string;
  summary?: BenchmarkResult["original_summary"];
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/50 p-4">
      <p className="overline mb-2">{title}</p>
      <KeyValue
        columns={2}
        items={[
          { label: "Mean energy", value: formatJoules(summary?.mean_energy_joules) },
          {
            label: "Mean duration",
            value: formatDuration(summary?.mean_duration_seconds),
          },
          { label: "Avg power", value: formatWatts(summary?.average_watts) },
          {
            label: "Spread",
            value:
              summary?.energy_spread_percent != null
                ? formatPercent(summary.energy_spread_percent)
                : "—",
          },
          { label: "Runs", value: summary?.runs ?? "—" },
          { label: "Energy (kWh)", value: formatEnergy((summary?.mean_energy_joules ?? 0) / 3.6e6) },
        ]}
      />
    </div>
  );
}

/* Kept local so the view does not depend on the dashboard's effect lifecycle. */
async function apiGetLlm(): Promise<LlmStatus> {
  const { apiGet } = await import("@/lib/api");
  return apiGet<LlmStatus>("/api/llm/status");
}
