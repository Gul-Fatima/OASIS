import Link from "next/link";

type IconName =
  | "folder"
  | "file"
  | "arrow"
  | "check"
  | "clock"
  | "code"
  | "leaf";

function Icon({
  name,
  size = 18,
}: {
  name: IconName;
  size?: number;
}) {
  const paths: Record<IconName, React.ReactNode> = {
    folder: (
      <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
    ),
    file: (
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8M8 17h8" />
    ),
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    check: <path d="m5 12 4 4L19 6" />,
    clock: (
      <path d="M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    ),
    code: (
      <path d="m8 8-4 4 4 4m8-8 4 4-4 4m-3-11-2 14" />
    ),
    leaf: (
      <path d="M20 4c-8 0-14 3-14 10a6 6 0 0 0 6 6c7 0 8-8 8-16ZM4 20c3-5 6-8 11-11" />
    ),
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0"
    >
      {paths[name]}
    </svg>
  );
}

const projects = [
  {
    name: "code-optimization",
    description: "Python · Code analysis",
    status: "Analysis completed",
    statusColor: "green",
    icon: "code" as const,
    href: "/analyze",
  },
  {
    name: "ml-training-pipeline",
    description: "Python · AI workflow",
    status: "Ready to analyze",
    statusColor: "purple",
    icon: "folder" as const,
    href: "/candidates",
  },
];

export default function HomeDashboard() {
  return (
    <div className="text-ink">
      <div className="mx-auto max-w-[1440px] space-y-7">
        {/* Welcome */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-xs font-medium text-accent">
            <Icon name="leaf" size={15} />
            <span>ENERGY-AWARE CODE OPTIMIZATION</span>
          </div>

          <div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Good evening
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted sm:text-base">
              Analyze your code, explore improvements, and validate their
              impact with evidence.
            </p>
          </div>

          <div className="flex flex-wrap gap-3 pt-1">
            <Link
              href="/analyze"
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-canvas transition hover:bg-accent/90"
            >
              <Icon name="folder" size={16} />
              Open analysis
              <Icon name="arrow" size={15} />
            </Link>

            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-surface-2"
            >
              <Icon name="file" size={16} />
              Optimize code
            </Link>
          </div>
        </section>

        {/* Projects */}
        <section className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Your projects</h2>
              <p className="mt-1 text-sm text-muted">
                Continue working on your code.
              </p>
            </div>
            <Link
              href="/analyze"
              className="text-sm font-medium text-accent hover:underline"
            >
              View analysis
            </Link>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {projects.map((project) => (
              <Link
                key={project.name}
                href={project.href}
                className="group rounded-xl border border-line bg-surface p-5 transition hover:border-accent/60 hover:shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-soft text-accent">
                    <Icon name={project.icon} size={20} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-semibold">
                      {project.name}
                    </h3>
                    <p className="mt-1 text-xs text-muted">
                      {project.description}
                    </p>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ${
                          project.statusColor === "green"
                            ? "bg-accent-soft text-accent"
                            : "bg-surface-3 text-violet"
                        }`}
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {project.status}
                      </span>
                      <span className="text-xs text-accent group-hover:underline">
                        Open <span aria-hidden="true">→</span>
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Recent activity */}
        <section className="rounded-xl border border-line bg-surface">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <h2 className="text-base font-semibold">Recent activity</h2>
              <p className="mt-1 text-xs text-muted">
                Pick up where you left off.
              </p>
            </div>
            <Link
              href="/history"
              className="text-sm font-medium text-accent hover:underline"
            >
              Run history
            </Link>
          </div>

          <div className="divide-y divide-line">
            <div className="flex items-center gap-3 px-5 py-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-accent">
                <Icon name="check" size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">Code analysis</p>
                <p className="mt-1 text-xs text-muted">
                  Review findings and potential optimization opportunities.
                </p>
              </div>
              <Link
                href="/detect"
                className="hidden text-xs font-medium text-accent hover:underline sm:block"
              >
                View findings
              </Link>
            </div>

            <div className="flex items-center gap-3 px-5 py-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-3 text-violet">
                <Icon name="clock" size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">Optimization workflow</p>
                <p className="mt-1 text-xs text-muted">
                  Review candidates, verification, and benchmark results.
                </p>
              </div>
              <Link
                href="/candidates"
                className="hidden text-xs font-medium text-accent hover:underline sm:block"
              >
                Open workflow
              </Link>
            </div>
          </div>
        </section>

        {/* Small footer note */}
        <p className="text-xs text-muted">
          OASIS · Evidence-based software energy optimization
        </p>
      </div>
    </div>
  );
}
