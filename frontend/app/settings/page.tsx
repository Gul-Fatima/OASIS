"use client";

/**
 * Settings: what the backend has been configured with.
 *
 * Read-only by design — configuration lives in OASIS/.env so it is never sent
 * over the wire or edited from the browser. The API key itself is never
 * returned by the backend.
 */

import { useCallback, useEffect, useState } from "react";

import { Disclosure, DisclosureStack } from "@/components/Disclosure";
import {
  Alert,
  Badge,
  Card,
  CodeBlock,
  KeyValue,
  PageHeader,
  SectionHeader,
  Spinner,
  buttonGhost,
} from "@/components/ui";
import { API_BASE, apiGet } from "@/lib/api";
import type { LanguagesResponse, LlmStatus } from "@/lib/types";

export default function SettingsPage() {
  const [llm, setLlm] = useState<LlmStatus | null>(null);
  const [languages, setLanguages] = useState<LanguagesResponse | null>(null);
  const [models, setModels] = useState<string[] | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const load = useCallback(async () => {
    const [llmResult, languageResult] = await Promise.allSettled([
      apiGet<LlmStatus>("/api/llm/status"),
      apiGet<LanguagesResponse>("/api/languages"),
    ]);

    if (llmResult.status === "fulfilled") setLlm(llmResult.value);
    if (languageResult.status === "fulfilled") setLanguages(languageResult.value);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function checkModels() {
    setChecking(true);
    setModelsError(null);
    try {
      const response = await apiGet<{ models: string[] }>("/api/llm/models");
      setModels(response.models);
    } catch (caught) {
      setModels(null);
      setModelsError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setChecking(false);
    }
  }

  return (
    <>
      <PageHeader
        overline="Configuration"
        title="Settings"
        description="Runtime configuration is read from OASIS/.env on the backend. This page reports what is active and helps you verify it."
      />

      <section className="mb-6">
        <SectionHeader overline="Connection" title="Backend & LLM" />

        <Card>
          <KeyValue
            columns={2}
            items={[
              { label: "API base URL", value: API_BASE },
              {
                label: "UI override",
                value: "NEXT_PUBLIC_API_BASE_URL in frontend/.env.local",
              },
              { label: "LLM provider", value: llm?.provider ?? "—" },
              { label: "Model", value: llm?.model ?? "—" },
              {
                label: "API key configured",
                value: llm ? (
                  <Badge tone={llm.configured ? "accent" : "warn"}>
                    {llm.configured ? "yes" : "no"}
                  </Badge>
                ) : (
                  "—"
                ),
              },
              {
                label: "Provider timeout",
                value: llm ? `${llm.timeout_seconds}s` : "—",
              },
            ]}
          />

          {llm && !llm.configured ? (
            <div className="mt-4">
              <Alert tone="warn" title="Candidate generation is disabled">
                {llm.hint ??
                  "Set GEMINI_API_KEY in OASIS/.env and restart the backend."}
              </Alert>
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              className={buttonGhost}
              onClick={() => void checkModels()}
              disabled={checking}
            >
              ⇄ List available models
            </button>
            {checking ? <Spinner label="Asking the provider…" /> : null}
          </div>

          {modelsError ? (
            <div className="mt-3">
              <Alert tone="danger" title="Model listing failed">
                {modelsError}
              </Alert>
            </div>
          ) : null}

          {models ? (
            <div className="mt-3">
              <p className="overline mb-2">Models available to this key</p>
              <div className="flex flex-wrap gap-1.5">
                {models.map((model) => (
                  <span
                    key={model}
                    className="rounded border border-line bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-ink/80"
                  >
                    {model}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </Card>
      </section>

      <section className="mb-6">
        <DisclosureStack>
          <Disclosure
            title="How to configure OASIS"
            overline="Setup"
            summary="Environment variables, backend and frontend commands"
          >
            <div className="space-y-4">
              <div>
                <p className="overline mb-1.5">1 · OASIS/.env</p>
                <CodeBlock
                  maxHeight={200}
                  code={`# Required for candidate generation
GEMINI_API_KEY=your-key-here

# Optional overrides
GEMINI_MODEL=gemini-3.8-flash
GEMINI_TIMEOUT_SECONDS=120
GEMINI_MAX_OUTPUT_TOKENS=8192`}
                />
              </div>

              <div>
                <p className="overline mb-1.5">2 · Start the backend (from OASIS/)</p>
                <CodeBlock maxHeight={120} code="uvicorn backend.main:app --port 8000 --reload" />
              </div>

              <div>
                <p className="overline mb-1.5">3 · Start this UI (from OASIS/frontend)</p>
                <CodeBlock
                  maxHeight={160}
                  code={`npm install
# optional, if the backend is not on localhost:8000
echo "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000" > .env.local
npm run dev`}
                />
              </div>
            </div>
          </Disclosure>

          <Disclosure
            title="Supported languages"
            overline="Parser"
            summary={
              languages?.supported?.length
                ? `${languages.supported.length} language(s) with adapters`
                : "Not reported"
            }
          >
            {languages ? (
              <div className="space-y-4">
                <div>
                  <p className="overline mb-2">Adapters</p>
                  <div className="flex flex-wrap gap-1.5">
                    {(languages.supported ?? []).map((name) => (
                      <span
                        key={name}
                        className="rounded border border-line bg-surface-2 px-2 py-0.5 text-[11px] text-ink/80"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>

                {languages.extensions?.length ? (
                  <div>
                    <p className="overline mb-2">Extensions</p>
                    <div className="flex flex-wrap gap-1.5">
                      {languages.extensions.map((extension) => (
                        <span
                          key={extension}
                          className="rounded border border-line bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-muted"
                        >
                          {extension}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-xs text-muted">The backend did not report languages.</p>
            )}
          </Disclosure>

          <Disclosure
            title="API endpoints used by this UI"
            overline="Contract"
            summary="Every backend call the frontend makes"
          >
            <CodeBlock
              maxHeight={380}
              code={`# Code understanding
POST /api/code/analyze            single file -> CodeState
POST /api/code/analyze/folder     folder -> aggregated CodeState
POST /api/code/analyze/stream     folder scan as SSE progress events

# Energy measurement (CodeCarbon)
POST /api/energy/estimate
POST /api/energy/estimate/stream  SSE snapshots (finite + continuous)
POST /api/energy/stop

# Energy smell detection
POST /api/detect
GET  /api/taxonomy
GET  /api/languages

# Candidate pipeline
GET  /api/llm/status
GET  /api/llm/models
POST /api/candidates/generate
POST /api/candidates/rank
POST /api/candidates/verify
POST /api/candidates/benchmark
POST /api/candidates/decision
POST /api/candidates/decision/record
GET  /api/candidates/history
POST /api/pipeline/run/stream     full pipeline as SSE

# Health
GET  /api/health`}
            />
          </Disclosure>
        </DisclosureStack>
      </section>
    </>
  );
}
