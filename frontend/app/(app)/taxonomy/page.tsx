"use client";

/**
 * Taxonomy browser: the 12 energy smell categories and their subcategories.
 *
 * Summary-first again — counts on top, each category collapsed.
 */

import { useEffect, useState } from "react";

import { Disclosure, DisclosureStack } from "@/components/Disclosure";
import {
  Alert,
  Badge,
  EmptyState,
  Grid,
  MetricCard,
  PageHeader,
  SectionHeader,
  Spinner,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatInteger } from "@/lib/format";
import type { TaxonomyResponse } from "@/lib/types";

export default function TaxonomyPage() {
  const [taxonomy, setTaxonomy] = useState<TaxonomyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await apiGet<TaxonomyResponse>("/api/taxonomy");
        if (!cancelled) setTaxonomy(response);
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageHeader
        overline="Energy smells"
        title="Taxonomy"
        description="The category system every detection is labelled with. Detections map to subcategories here, which is what makes a finding auditable rather than a vague claim."
      />

      <div className="mb-5">
        <Alert tone="info" title="Where this comes from">
          The taxonomy follows the SMART-Dal Energy-Smells classification work. Each
          detection names one subcategory so a reviewer can check whether the pattern
          really matches the definition.
        </Alert>
      </div>

      {loading ? (
        <div className="rounded-xl border border-line bg-surface px-5 py-8 text-center">
          <Spinner label="Loading taxonomy…" />
        </div>
      ) : null}

      {error ? (
        <Alert tone="danger" title="Could not load the taxonomy">
          {error}
        </Alert>
      ) : null}

      {taxonomy ? (
        <>
          <Grid columns={3} className="mb-6">
            <MetricCard
              label="Categories"
              value={formatInteger(taxonomy.total_categories)}
              tone="accent"
              emphasized
              hint="Parent groupings of energy inefficiency"
            />
            <MetricCard
              label="Subcategories"
              value={formatInteger(taxonomy.total_subcategories)}
              tone="info"
              hint="Precise labels a detection can carry"
            />
            <MetricCard
              label="Detectors wired"
              value="8 rules"
              hint="Static detectors currently mapped onto this taxonomy"
            />
          </Grid>

          <section className="mb-8">
            <SectionHeader
              overline="Browse"
              title="Categories and subcategories"
              description="Collapsed by default — open the categories you care about."
            />

            <DisclosureStack>
              {taxonomy.categories.map((category) => (
                <Disclosure
                  key={category.id}
                  overline={category.id}
                  title={category.name}
                  summary={`${category.subcategories.length} subcategor${
                    category.subcategories.length === 1 ? "y" : "ies"
                  }`}
                >
                  <p className="mb-4 text-xs leading-relaxed text-muted">
                    {category.description}
                  </p>

                  <div className="space-y-2">
                    {category.subcategories.map((subcategory) => (
                      <div
                        key={subcategory.id}
                        className="rounded-lg border border-line bg-surface-2/50 p-3"
                      >
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <Badge tone="violet">{subcategory.id}</Badge>
                          <span className="text-sm font-medium text-ink">
                            {subcategory.name}
                          </span>
                        </div>
                        <p className="text-xs leading-relaxed text-muted">
                          {subcategory.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </Disclosure>
              ))}
            </DisclosureStack>
          </section>
        </>
      ) : null}

      {!loading && !taxonomy && !error ? (
        <EmptyState
          icon="≡"
          title="No taxonomy returned"
          message="The backend did not return a taxonomy. Check that it is running."
        />
      ) : null}
    </>
  );
}
