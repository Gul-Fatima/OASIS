"use client";

/**
 * The main workflow: pick a file, see what can be optimized, copy the prompt.
 *
 * Deliberately summary-first and free of pipeline internals — a developer only
 * needs the issues, the strategy for each, and the prompt.
 */

import { useRef, useState } from "react";

import {
  Alert,
  Badge,
  Card,
  EmptyState,
  PageHeader,
  SectionHeader,
  Spinner,
  buttonGhost,
  buttonPrimary,
} from "@/components/ui";
import { apiPost } from "@/lib/api";
import type { OptimizeResponse } from "@/lib/types";

type SelectedFile = {
  name: string;
  source: string;
  size: number;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function OptimizeView() {
  const inputRef = useRef<HTMLInputElement>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const [file, setFile] = useState<SelectedFile | null>(null);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [dragging, setDragging] = useState(false);

  async function selectFile(next: File) {
    try {
      const source = await next.text();
      setFile({ name: next.name, source, size: next.size });
      setResult(null);
      setError(null);
      setCopied(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function analyze() {
    if (!file) {
      inputRef.current?.click();
      return;
    }

    setLoading(true);
    setError(null);
    setCopied(false);

    try {
      const response = await apiPost<OptimizeResponse>("/api/optimize", {
        source: file.source,
        filename: file.name,
      });
      setResult(response);
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  async function copyPrompt() {
    if (!result?.prompt) return;

    try {
      await navigator.clipboard.writeText(result.prompt);
    } catch {
      promptRef.current?.select();
      document.execCommand("copy");
    }

    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <PageHeader
        title="Optimize a file"
        description="Pick a Python file, review the optimization opportunities, and copy the prompt into your LLM."
      />

      <Card className="mb-5">
        <input
          ref={inputRef}
          type="file"
          accept=".py,text/x-python"
          className="hidden"
          onChange={(event) => {
            const next = event.target.files?.[0];
            if (next) void selectFile(next);
            event.target.value = "";
          }}
        />

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            const next = event.dataTransfer.files?.[0];
            if (next) void selectFile(next);
          }}
          className={`flex flex-col items-start gap-4 rounded-lg border border-dashed px-5 py-6 sm:flex-row sm:items-center sm:justify-between ${
            dragging ? "border-accent bg-accent-soft/30" : "border-line bg-surface-2/40"
          }`}
        >
          <div className="min-w-0">
            {file ? (
              <>
                <p className="truncate text-sm font-semibold text-ink">{file.name}</p>
                <p className="mt-0.5 text-xs text-muted">{formatSize(file.size)}</p>
              </>
            ) : (
              <>
                <p className="text-sm font-semibold text-ink">Drop a Python file here</p>
                <p className="mt-0.5 text-xs text-muted">
                  Nothing is executed — the file is only analysed.
                </p>
              </>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              className={buttonGhost}
              onClick={() => inputRef.current?.click()}
              disabled={loading}
            >
              {file ? "Choose another" : "Choose file"}
            </button>
            <button
              type="button"
              className={buttonPrimary}
              onClick={analyze}
              disabled={loading || !file}
            >
              Analyze
            </button>
          </div>
        </div>

        {loading ? (
          <div className="mt-4">
            <Spinner label="Looking for optimization opportunities…" />
          </div>
        ) : null}
      </Card>

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Could not analyze the file">
            {error}
          </Alert>
        </div>
      ) : null}

      {!result && !loading ? (
        <EmptyState
          icon="◌"
          title={file ? "Ready to analyze" : "No file selected"}
          message={
            file
              ? "Run the analysis to see the opportunities in this file."
              : "Choose a Python file to get started."
          }
        />
      ) : null}

      {result ? (
        <>
          <section className="mb-5">
            <SectionHeader
              title="Opportunities"
              actions={
                <Badge tone={result.issue_count > 0 ? "warn" : "muted"}>
                  {result.issue_count} issue{result.issue_count === 1 ? "" : "s"}
                </Badge>
              }
              description={`${result.filename} · ${result.line_count} lines`}
            />

            {result.issue_count === 0 ? (
              <EmptyState
                icon="✓"
                title="No optimization opportunities found"
                message="This file does not match any known energy smell patterns."
              />
            ) : (
              <div className="space-y-3">
                {result.issues.map((issue) => (
                  <div
                    key={issue.id}
                    className="rounded-xl border border-line bg-surface p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="violet">{issue.subcategory_id}</Badge>
                      <span className="text-sm font-semibold text-ink">
                        {issue.subcategory_name ?? issue.category_name}
                      </span>
                      <span className="ml-auto text-xs text-muted">
                        {issue.function ? `${issue.function}()` : ""}
                        {issue.function ? " · " : ""}
                        line {issue.line ?? "—"}
                      </span>
                    </div>

                    {issue.title ? (
                      <p className="mt-2 text-sm text-ink/90">{issue.title}</p>
                    ) : null}

                    {issue.strategy ? (
                      <div className="mt-2 rounded-lg border border-accent/20 bg-accent-soft/30 px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">
                          Optimization
                        </p>
                        <p className="mt-0.5 text-xs leading-relaxed text-ink/90">
                          {issue.strategy}
                        </p>
                      </div>
                    ) : null}

                    {issue.example ? (
                      <p className="mt-2 font-mono text-[11px] leading-relaxed text-muted">
                        {issue.example}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </section>

          {result.prompt ? (
            <section>
              <Card>
                <SectionHeader
                  title="Prompt"
                  description="Copy this into your LLM to apply the optimizations."
                  actions={
                    <button
                      type="button"
                      className={buttonPrimary}
                      onClick={copyPrompt}
                    >
                      {copied ? "✓ Copied" : "Copy prompt"}
                    </button>
                  }
                />

                <textarea
                  ref={promptRef}
                  readOnly
                  value={result.prompt}
                  rows={14}
                  spellCheck={false}
                  className="w-full resize-y rounded-lg border border-line bg-canvas p-3 font-mono text-xs leading-relaxed text-ink/90"
                />
              </Card>
            </section>
          ) : null}
        </>
      ) : null}
    </>
  );
}
