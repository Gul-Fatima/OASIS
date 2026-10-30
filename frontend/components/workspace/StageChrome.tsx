"use client";

/**
 * Shared chrome for the four workflow stages.
 *
 * Every stage opens with the same three things in the same place: where you are
 * in the journey, what the system suggests you do next, and the workspace
 * context it will use. That repetition is the point — it is what stops the four
 * screens from feeling like four different products.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { inputClass } from "@/components/ui";
import { useWorkspace, STAGES, targetName, type StageId } from "@/components/workspace/WorkspaceContext";

const STAGE_INDEX = Object.fromEntries(
  STAGES.map((stage) => [stage.id, stage.number]),
) as Record<StageId, number>;

export function StageHeader({
  stage,
  title,
  description,
  actions,
}: {
  stage: StageId;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  const step = STAGE_INDEX[stage];
  return (
    <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="overline mb-1.5">
          Step {step} of {STAGES.length} · {STAGES.find((item) => item.id === stage)?.title}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description ? (
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** A row of the four stages; the current one is filled, finished ones checked. */
export function StageSteps({ current }: { current: StageId }) {
  const { progress } = useWorkspace();

  return (
    <ol className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {STAGES.map((stage) => {
        const info = progress[stage.id];
        const active = stage.id === current;
        return (
          <li key={stage.id}>
            <Link
              href={stage.href}
              aria-current={active ? "step" : undefined}
              className={`flex h-full items-center gap-2.5 rounded-lg border px-3 py-2 text-xs transition ${
                active
                  ? "border-accent/50 bg-accent-soft/60 text-ink"
                  : "border-line bg-surface text-muted hover:border-accent/40 hover:text-ink"
              }`}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  info.state === "done"
                    ? "bg-accent text-canvas"
                    : active
                      ? "bg-accent-soft text-accent ring-1 ring-accent/50"
                      : "bg-surface-3 text-muted"
                }`}
              >
                {info.state === "done" ? "✓" : stage.number}
              </span>
              <span className="min-w-0">
                <span className="block truncate font-semibold">{stage.title}</span>
                <span className="block truncate text-[10px] text-muted">{info.hint}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * The "what to do next" strip. One sentence derived from real state, one
 * primary action. This is the user's mental model, made explicit.
 */
export function GuidanceBar({
  tone = "accent",
  eyebrow = "Next step",
  message,
  action,
}: {
  tone?: "accent" | "info" | "warn" | "muted";
  eyebrow?: string;
  message: ReactNode;
  action?: ReactNode;
}) {
  const styles = {
    accent: "border-accent/40 bg-accent-soft/40",
    info: "border-info/40 bg-info-soft/40",
    warn: "border-warn/40 bg-warn-soft/40",
    muted: "border-line bg-surface-2",
  }[tone];

  const dot = {
    accent: "bg-accent",
    info: "bg-info",
    warn: "bg-warn",
    muted: "bg-muted",
  }[tone];

  return (
    <div
      className={`mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 ${styles}`}
    >
      <div className="flex min-w-0 items-start gap-2.5">
        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot}`} />
        <div className="min-w-0">
          <p className="overline">{eyebrow}</p>
          <div className="mt-0.5 text-sm leading-relaxed text-ink">{message}</div>
        </div>
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}

/**
 * The persistent workspace context: the paths and command every stage needs.
 * Collapsed to chips by default so it never competes with the stage's own
 * controls; open it when something needs changing.
 */
export function WorkspaceBar({ disabled = false }: { disabled?: boolean }) {
  const { settings, updateSettings, resetWorkspace, scan, measure, improve } = useWorkspace();
  const hasAnything = Boolean(scan || measure || improve);

  return (
    <details className="group mb-5 rounded-xl border border-line bg-surface">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-4 py-2.5">
        <span className="overline mr-1">Workspace</span>
        <Chip label="file" value={targetName(settings.filePath) || "not set"} tone={settings.filePath ? "ink" : "muted"} />
        <Chip label="runtime" value={settings.command || "not set"} tone={settings.command ? "ink" : "muted"} />
        <Chip label="lang" value={settings.language} tone="muted" />
        <span className="ml-auto text-[11px] font-medium text-accent">
          Edit <span aria-hidden className="inline-block transition-transform group-open:rotate-180">▾</span>
        </span>
      </summary>

      <div className="grid grid-cols-1 gap-4 border-t border-line px-4 py-4 lg:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-muted">Project folder</span>
          <input
            className={inputClass}
            value={settings.projectPath}
            onChange={(event) => updateSettings({ projectPath: event.target.value })}
            placeholder="D:/projects/my_project"
            disabled={disabled}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-muted">File to optimize</span>
          <input
            className={inputClass}
            value={settings.filePath}
            onChange={(event) => updateSettings({ filePath: event.target.value })}
            placeholder="D:/projects/my_project/main.py"
            disabled={disabled}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-muted">Execution command</span>
          <input
            className={inputClass}
            value={settings.command}
            onChange={(event) => updateSettings({ command: event.target.value })}
            placeholder="python main.py"
            disabled={disabled}
          />
        </label>
        <div className="flex items-end justify-between gap-3">
          <label className="block w-full">
            <span className="mb-1.5 block text-xs font-medium text-muted">Language</span>
            <select
              className={inputClass}
              value={settings.language}
              onChange={(event) => updateSettings({ language: event.target.value })}
              disabled={disabled}
            >
              {[
                { value: "auto", label: "Auto-detect" },
                { value: "python", label: "Python" },
                { value: "java", label: "Java" },
                { value: "javascript", label: "JavaScript" },
                { value: "c", label: "C" },
                { value: "cpp", label: "C++" },
              ].map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          {hasAnything ? (
            <button
              type="button"
              onClick={resetWorkspace}
              disabled={disabled}
              className="mb-0.5 shrink-0 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-muted transition hover:border-danger/40 hover:text-danger disabled:opacity-40"
            >
              Clear results
            </button>
          ) : null}
        </div>
      </div>
    </details>
  );
}

function Chip({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "ink" | "muted";
}) {
  return (
    <span className="inline-flex max-w-[16rem] items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 py-0.5 text-[11px]">
      <span className="text-muted">{label}</span>
      <span
        className={`truncate font-mono ${tone === "ink" ? "text-ink" : "text-muted/70"}`}
        title={value}
      >
        {value}
      </span>
    </span>
  );
}
