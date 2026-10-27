"use client";

/**
 * Optimization history: the accept/reject record written to results/decisions.jsonl.
 *
 * Failure and neutral outcomes are shown alongside successes — CLAUDE.md
 * forbids hiding failed or neutral experiments.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Card,
  EmptyState,
  Grid,
  MetricCard,
  PageHeader,
  SectionHeader,
  Spinner,
  buttonGhost,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatInteger, formatSignedPercent, shortId } from "@/lib/format";
import type { DecisionRecord } from "@/lib/types";

export default function HistoryPage() {
  const [records, setRecords] = useState<DecisionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiGet<{ decisions: DecisionRecord[] }>(
        "/api/candidates/history?limit=200",
      );
      setRecords(response.decisions ?? []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const accepted = records.filter((item) => item.developer_action === "ACCEPTED");
  const rejected = records.filter((item) => item.developer_action === "REJECTED");
  const improved = records.filter((item) => item.status === "IMPROVED");
  const neutral = records.filter((item) => item.status === "NEUTRAL");
  const regressedOrFailed = records.filter(
    (item) => item.status === "REGRESSED" || item.status === "FAILED",
  );

  return (
    <>
      <PageHeader
        overline="Experiment history"
        title="Optimization Decisions"
        description="Every accept/reject action recorded with the status and measured improvement it was based on."
        actions={
          <button type="button" className={buttonGhost} onClick={() => void load()}>
            ⟳ Refresh
          </button>
        }
      />

      <div className="mb-5">
        <Alert tone="info" title="Full reporting, including the ones that did not work">
          Successful, neutral and failed candidates are all kept here. A history that
          only shows wins would misrepresent the measurements.
        </Alert>
      </div>

      {error ? (
        <div className="mb-5">
          <Alert tone="danger" title="Could not load history">
            {error}
          </Alert>
        </div>
      ) : null}

      <Grid columns={5} className="mb-6">
        <MetricCard
          label="Decisions recorded"
          value={formatInteger(records.length)}
          tone="accent"
          emphasized
          hint="Developer accept/reject actions"
        />
        <MetricCard
          label="Accepted"
          value={formatInteger(accepted.length)}
          tone="accent"
          hint={`${rejected.length} rejected`}
        />
        <MetricCard
          label="Improved"
          value={formatInteger(improved.length)}
          hint="Measured saving above the noise floor"
        />
        <MetricCard
          label="Neutral"
          value={formatInteger(neutral.length)}
          tone="warn"
          hint="Within measurement noise"
        />
        <MetricCard
          label="Regressed / failed"
          value={formatInteger(regressedOrFailed.length)}
          tone="danger"
          hint="Kept visible on purpose"
        />
      </Grid>

      {loading ? (
        <div className="rounded-xl border border-line bg-surface px-5 py-8 text-center">
          <Spinner label="Loading decisions…" />
        </div>
      ) : null}

      {!loading && records.length === 0 && !error ? (
        <EmptyState
          icon="◷"
          title="No decisions yet"
          message="Run the optimization pipeline and accept or reject a candidate; the decision and its evidence will be stored here."
        />
      ) : null}

      {records.length > 0 ? (
        <section>
          <SectionHeader overline="Records" title="Decision log" />
          <Card className="overflow-x-auto p-0">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-line bg-surface-2">
                  {[
                    "Candidate",
                    "Status",
                    "Measured change",
                    "Action",
                    "Recorded",
                    "Rationale",
                  ].map((column) => (
                    <th
                      key={column}
                      className="whitespace-nowrap px-4 py-2.5 font-semibold text-muted"
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {records.map((record, index) => (
                  <tr
                    key={`${record.candidate_id}-${index}`}
                    className="border-b border-line/50 last:border-b-0 hover:bg-surface-2/50"
                  >
                    <td className="px-4 py-2 font-mono">{shortId(record.candidate_id)}</td>
                    <td className="px-4 py-2">
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
                    </td>
                    <td className="px-4 py-2">
                      {record.measured_improvement_percent != null
                        ? formatSignedPercent(record.measured_improvement_percent)
                        : "—"}
                    </td>
                    <td
                      className={`px-4 py-2 font-semibold ${
                        record.developer_action === "ACCEPTED"
                          ? "text-accent"
                          : "text-danger"
                      }`}
                    >
                      {record.developer_action}
                    </td>
                    <td className="px-4 py-2 text-muted">
                      {record.recorded_at
                        ? new Date(record.recorded_at).toLocaleString()
                        : "—"}
                    </td>
                    <td className="max-w-[28rem] px-4 py-2 text-muted">
                      {(record.rationale ?? []).slice(0, 2).join(" ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      ) : null}
    </>
  );
}
