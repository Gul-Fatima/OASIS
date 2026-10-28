
import Link from "next/link";

export const metadata = {
  title: "OASIS — Energy-Aware Code Optimization",
  description:
    "Analyze code, explore optimization opportunities, and evaluate performance and energy impact.",
};

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[#F7F7FC] text-[#20252C]">
      {/* Public navigation */}
      <header className="border-b border-[#E8E7F0] bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#E3F2E8] text-[#176B48]">
              <svg
                width="21"
                height="21"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M20 4c-8 0-14 3-14 10a6 6 0 0 0 6 6c7 0 8-8 8-16Z" />
                <path d="M4 20c3-5 6-8 11-11" />
              </svg>
            </span>
            <span className="text-lg font-semibold tracking-tight">
              OASIS
            </span>
          </Link>

          <nav className="flex items-center gap-3">
            <Link
              href="/auth"
              className="rounded-lg px-3 py-2 text-sm font-medium text-[#45495A] hover:bg-[#F7F7FC]"
            >
              Sign in
            </Link>
            <Link
              href="/auth"
              className="rounded-lg bg-[#176B48] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#12583B]"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      {/* Promotional hero */}
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-20 md:grid-cols-2 md:py-28">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#D7E9DD] bg-[#EAF4ED] px-3 py-1.5 text-xs font-medium text-[#176B48]">
            <span className="h-2 w-2 rounded-full bg-[#28754F]" />
            Energy-aware software engineering
          </div>

          <h1 className="max-w-xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            Write better code.
            <span className="mt-2 block text-[#28754F]">
              Understand its impact.
            </span>
          </h1>

          <p className="mt-6 max-w-lg text-base leading-7 text-[#737786] sm:text-lg">
            OASIS helps you explore code optimization opportunities,
            inspect proposed changes, verify correctness, and evaluate
            performance and energy measurements.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/auth"
              className="inline-flex items-center gap-2 rounded-lg bg-[#176B48] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#12583B]"
            >
              Get started with OASIS
              <span aria-hidden="true">→</span>
            </Link>
            <a
              href="#how-it-works"
              className="rounded-lg border border-[#DDDCE8] bg-white px-5 py-3 text-sm font-medium text-[#343746] transition hover:bg-[#F1F0F8]"
            >
              Explore the workflow
            </a>
          </div>

          <p className="mt-5 text-xs text-[#858696]">
            Evidence-based analysis. Reviewable changes. Measurable results.
          </p>
        </div>

        {/* Product preview */}
        <div className="rounded-2xl border border-[#E5E3EF] bg-white p-4 shadow-sm sm:p-6">
          <div className="flex items-center justify-between border-b border-[#F0EFF5] pb-4">
            <div>
              <p className="text-xs text-[#858696]">OPTIMIZATION WORKSPACE</p>
              <h2 className="mt-1 text-base font-semibold">
                Candidate comparison
              </h2>
            </div>
            <span className="rounded-full bg-[#F0EFFB] px-2.5 py-1 text-xs text-[#7068B5]">
              Preview
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 py-5">
            <div className="rounded-lg border border-[#E8E7F0] bg-[#FAFAFD] p-3">
              <p className="text-xs text-[#737786]">Original code</p>
              <div className="mt-4 space-y-2 font-mono text-xs text-[#737786]">
                <p>01&nbsp; for item in data:</p>
                <p>02&nbsp;&nbsp;&nbsp; result.append(</p>
                <p>03&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; process(item))</p>
              </div>
            </div>

            <div className="rounded-lg border border-[#D7E9DD] bg-[#F4FAF5] p-3">
              <p className="text-xs text-[#28754F]">Proposed change</p>
              <div className="mt-4 space-y-2 font-mono text-xs text-[#28754F]">
                <p>01&nbsp; result = [</p>
                <p>02&nbsp;&nbsp;&nbsp; process(item)</p>
                <p>03&nbsp;&nbsp;&nbsp; for item in data]</p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-[#E8E7F0] p-4">
            <p className="text-sm font-medium">Review before accepting</p>
            <p className="mt-1 text-xs leading-5 text-[#737786]">
              Inspect code changes, verify correctness, and compare
              measured outcomes when benchmark data is available.
            </p>
          </div>

          <p className="mt-4 text-xs text-[#858696]">
            Illustrative interface preview — not a real optimization result.
          </p>
        </div>
      </section>

      {/* Workflow introduction */}
      <section
        id="how-it-works"
        className="border-t border-[#E8E7F0] bg-white"
      >
        <div className="mx-auto max-w-7xl px-6 py-16 sm:py-20">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#28754F]">
              The workflow
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
              From code analysis to evidence
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#737786]">
              Explore potential improvements, inspect candidate changes,
              and evaluate them before making a decision.
            </p>
          </div>

          <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                number: "01",
                title: "Analyze",
                description:
                  "Inspect source code and identify potential optimization opportunities.",
              },
              {
                number: "02",
                title: "Explore",
                description:
                  "Review proposed code changes and their supporting evidence.",
              },
              {
                number: "03",
                title: "Verify",
                description:
                  "Check candidate correctness before relying on its results.",
              },
              {
                number: "04",
                title: "Evaluate",
                description:
                  "Compare runtime and energy measurements when available.",
              },
            ].map((step) => (
              <article
                key={step.number}
                className="rounded-xl border border-[#E8E7F0] bg-[#FCFCFE] p-5"
              >
                <p className="text-sm font-semibold text-[#28754F]">
                  {step.number}
                </p>
                <h3 className="mt-4 text-base font-semibold">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-[#737786]">
                  {step.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E8E7F0] bg-[#F7F7FC]">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-6 py-6 text-xs text-[#858696] sm:flex-row sm:items-center sm:justify-between">
          <span>OASIS · Energy-aware code optimization</span>
          <span>Evidence first. Optimize with confidence.</span>
        </div>
      </footer>
    </main>
  );
}
