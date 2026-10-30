"use client";

/**
 * Stage 4 — Decide.
 *
 * The measured comparison and the accept/reject record. Predictions are shown
 * for context only; the ordering and the recommendation come from measured
 * evidence. Decisions are written to the same history endpoint the archive
 * reads, so nothing here is a local-only flag.
 */

import Link from "next/link";
import { useState } from "react";

import { GuidanceBar, StageHeader, StageSteps } from "@/components/workspace/StageChrome";
import { useWorkspace, type DecisionAction } from "@/components/workspace/WorkspaceContext";
import {
  Alert,
  Badge,
  EmptyState,
  Grid,
  MetricCard,
  buttonGhost,
  buttonPrimary,
  type Tone,
} from "@/components/ui";
import { apiPost } from "@/lib/api";
import {
  formatInteger,
  formatJoules,
  formatPercent,
  formatSignedPercent,
  shortId,
} from "@/lib/format";
import type { Candidate } from "@/lib/types";

function statusTone(status?: string | null): Tone {
  switch ((status ?? "").toUpperCase()) {
    case "IMPROVED":
    case "VERIFIED":
    case "MEASURED":
    case "ACCEPTED":
      return "accent";
    case "NEUTRAL":
    case "PREDICTED":
    case "GENERATED":
      return "warn";
    case "REGRESSED":
    case "FAILED":
    case "REJECTED":
    case "VERIFICATION_FAILED":
    case "BENCHMARK_FAILED":
      return "danger";
    default:
      return "muted";
  }
}

export function DecideView() {
  const { improve, decisions, recordDecision } = useWorkspace();
  const [saving, setSaving] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const candidates = improve?.candidates ?? [];
  const recordedCount = candidates.filter((candidate) => decisions[candidate.candidate_id]).length;
  const allRecorded = candidates.length > 0 && recordedCount === candidates.length;
  const measuredCount = candidates.filter(
    (candidate) => candidate.measured_energy?.improvement_percent != null,
  ).length;
  const improvedCount = candidates.filter(
    (candidate) => candidate.final_status === "IMPROVED",
  ).length;

  async function record(candidate: Candidate, action: DecisionAction) {
    setSaving(candidate.candidate_id);
    setErrors((previous) => {
      const next = { ...previous };
      delete next[candidate.candidate_id];
      return next;
    });

    try {
      await apiPost("/api/candidates/decision/record", {
        candidate_id: candidate.candidate_id,
        status: candidate.final_status ?? "PREDICTED",
        developer_action: action,
        rationale: candidate.decision?.rationale ?? [],
        measured_improvement_percent:
          candidate.measured_energy?.improvement_percent ?? null,
      });
      recordDecision(candidate.candidate_id, action);
    } catch (caught) {
      setErrors((previous) => ({
        ...previous,
        [candidate.candidate_id]:
          caught instanceof Error ? caught.message : String(caught),
      }));
    } finally {
      setSaving(null);
    }
  }

  return (
    <>
      <StageHeader
        stage="decide"
        title="Review the evidence and decide"
        description="Compare measured results and record accept or reject."
        actions={
          <Link href="/history" className={buttonGhost}>
            Decision history
          </Link>
        }
      />
      <StageSteps current="decide" />

      {candidates.length === 0 ? (
        <EmptyState
          icon="⚖"
          title="No candidates to decide on"
          message="Run the improve stage first to get candidates."
        />
      ) : (
        <>
          {allRecorded ? (
            <GuidanceBar
              message={
                <>
                  All {candidates.length} recorded. Apply a change and scan again.
                </>
              }
              action={
                <Link href="/workspace/scan" className={buttonPrimary}>
                  Start a new cycle →
                </Link>
              }
            />
          ) : (
            <GuidanceBar
              tone={recordedCount > 0 ? "info" : "accent"}
              eyebrow={recordedCount > 0 ? "In progress" : "Finish the workflow"}
              message={
                recordedCount > 0
                  ? `${recordedCount} of ${candidates.length} recorded.`
                  : `Ordered by evidence. ${improvedCount} improved, ${measuredCount} measured.`
              }
            />
          )}

          <Grid columns={3} className="mb-5">
            <MetricCard label="Measured" value={formatInteger(measuredCount)} hint="Have usable energy data" />
            <MetricCard
              label="Improved"
              value={formatInteger(improvedCount)}
              tone={improvedCount > 0 ? "accent" : "muted"}
              emphasized
              hint="Above the noise threshold"
            />
            <MetricCard
              label="Decisions recorded"
              value={`${recordedCount} / ${candidates.length}`}
              tone={allRecorded ? "accent" : "warn"}
              hint="Accept or reject each candidate"
            />
          </Grid>

          {measuredCount === 0 ? (
            <div className="mb-5">
              <Alert tone="warn" title="Nothing was measured">
                These candidates were verified but not benchmarked, so none can be called an
                energy improvement.
              </Alert>
            </div>
          ) : null}

          <div className="space-y-3">
            {candidates.map((candidate) => (
              <CandidateDecision
                key={candidate.candidate_id}
                candidate={candidate}
                action={decisions[candidate.candidate_id]}
                saving={saving === candidate.candidate_id}
                error={errors[candidate.candidate_id]}
                onRecord={(next) => void record(candidate, next)}
              />
            ))}
          </div>

          {Object.keys(errors).length > 0 ? (
            <p className="mt-3 text-[11px] text-danger">
              Some decisions could not be recorded — the backend did not confirm them.
            </p>
          ) : null}
        </>
      )}
    </>
  );
}

function CandidateDecision({
  candidate,
  action,
  saving,
  error,
  onRecord,
}: {
  candidate: Candidate;
  action?: DecisionAction;
  saving: boolean;
  error?: string;
  onRecord: (action: DecisionAction) => void;
}) {
  const measured = candidate.measured_energy;
  const benchmark = candidate.benchmark;
  const decision = candidate.decision;
  const originalJoules =
    benchmark?.original_summary?.mean_energy_joules ?? measured?.original_mean_joules ?? null;
  const candidateJoules =
    benchmark?.candidate_summary?.mean_energy_joules ?? measured?.candidate_mean_joules ?? null;
  const max = Math.max(originalJoules ?? 0, candidateJoules ?? 0, 1e-9);
  const delta = measured?.improvement_percent ?? null;
  const spread =
    benchmark?.original_summary?.energy_spread_percent ??
    benchmark?.candidate_summary?.energy_spread_percent ??
    null;

  return (
    <div
      className={`rounded-xl border bg-surface shadow-[var(--elevation)] ${
        action ? "border-accent/30" : "border-line"
      }`}
    >
      <div className="grid grid-cols-1 gap-0 lg:grid-cols-[minmax(0,1fr)_280px]">
        {/* ---------------- EVIDENCE ---------------- */}
        <div className="min-w-0 p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge tone="violet">{candidate.rank ? `Rank ${candidate.rank}` : "Candidate"}</Badge>
            <span className="font-mono text-[11px] text-muted">
              {shortId(candidate.candidate_id)}
            </span>
            <Badge tone={statusTone(candidate.final_status)}>
              {candidate.final_status ?? "PREDICTED"}
            </Badge>
            <Badge tone={statusTone(candidate.correctness_status)}>
              {candidate.correctness_status ?? "unverified"}
            </Badge>
            {delta != null ? (
              <span
                className={`ml-auto font-mono text-sm font-semibold ${
                  delta > 0 ? "text-accent" : delta < 0 ? "text-danger" : "text-muted"
                }`}
              >
                {formatSignedPercent(delta)}
              </span>
            ) : (
              <span className="ml-auto text-[11px] text-muted">not measured</span>
            )}
          </div>

          <p className="mb-3 line-clamp-2 text-sm leading-relaxed text-ink/90">
            {candidate.strategy ?? "No strategy description was returned."}
          </p>

          <div className="mb-3 grid grid-cols-1 gap-x-6 gap-y-1.5 text-[11px] sm:grid-cols-2">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-muted">Predicted impact</span>
              <span className="truncate text-violet" title={candidate.predicted_impact}>
                {candidate.predicted_impact ?? "—"}
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-muted">Measured runs</span>
              <span className="font-mono text-ink">
                {benchmark?.runs_per_version ?? "—"} / version
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-muted">Original mean</span>
              <span className="font-mono text-ink">{formatJoules(originalJoules)}</span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-muted">Candidate mean</span>
              <span className="font-mono text-ink">{formatJoules(candidateJoules)}</span>
            </div>
          </div>

          {originalJoules != null || candidateJoules != null ? (
            <div className="rounded-lg border border-line bg-surface-2/40 p-2.5">
              <Bar label="Original" joules={originalJoules} max={max} className="bg-muted" />
              <Bar label="Candidate" joules={candidateJoules} max={max} className="bg-accent" />
              {spread != null ? (
                <p className="mt-1.5 text-[10px] text-muted">
                  Measurement spread {formatPercent(spread, 1)} — changes inside the spread are
                  treated as neutral.
                </p>
              ) : null}
            </div>
          ) : null}

          {decision?.rationale?.length ? (
            <ul className="mt-2.5 space-y-0.5 text-[11px] leading-relaxed text-muted">
              {decision.rationale.slice(0, 3).map((line) => (
                <li key={line}>· {line}</li>
              ))}
            </ul>
          ) : null}
        </div>

        {/* ---------------- DECISION ---------------- */}
        <div className="flex flex-col justify-between gap-3 border-t border-line bg-surface-2/30 p-4 lg:border-l lg:border-t-0">
          <div>
            <p className="overline mb-1">Your decision</p>
            <p className="text-xs leading-relaxed text-muted">
              Records your review. Nothing is applied automatically.
            </p>
          </div>

          {action ? (
            <div>
              <Badge tone={action === "ACCEPTED" ? "accent" : "danger"} className="w-full justify-center py-1.5">
                {action === "ACCEPTED" ? "✓ Accepted" : "✕ Rejected"}
              </Badge>
              <p className="mt-1.5 text-center text-[10px] text-muted">Recorded in history</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                className={`${buttonPrimary} w-full`}
                disabled={saving}
                onClick={() => onRecord("ACCEPTED")}
              >
                {saving ? "Recording…" : "Accept"}
              </button>
              <button
                type="button"
                className={`${buttonGhost} w-full`}
                disabled={saving}
                onClick={() => onRecord("REJECTED")}
              >
                Reject
              </button>
            </div>
          )}

          {error ? <p className="text-[10px] leading-relaxed text-danger">{error}</p> : null}
        </div>
      </div>
    </div>
  );
}

function Bar({
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
    <div className="mb-1 flex items-center gap-2 text-[11px] last:mb-0">
      <span className="w-16 shrink-0 text-muted">{label}</span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
        <span className={`block h-full rounded-full ${className}`} style={{ width: `${width}%` }} />
      </span>
      <span className="w-20 shrink-0 text-right font-mono text-muted">{formatJoules(joules)}</span>
    </div>
  );
}
