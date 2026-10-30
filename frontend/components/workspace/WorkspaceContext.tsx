"use client";

/**
 * Shared workspace state.
 *
 * The four stages used to be independent pages that each re-asked for the same
 * file path and threw their results away on navigation. This provider is what
 * makes them one continuous session: settings live in localStorage, results
 * live in memory for the lifetime of the app shell (the `(app)` layout does not
 * remount between routes), so Scan → Measure → Improve → Decide carries context
 * forward.
 *
 * Nothing here is business logic. Results are stored exactly as the API
 * returned them.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type {
  Candidate,
  Detection,
  DetectionSummary,
  EnergySnapshot,
  PipelineResult,
} from "@/lib/types";

export type StageId = "scan" | "measure" | "improve" | "decide";

export type StageMeta = {
  id: StageId;
  number: number;
  title: string;
  href: string;
  /** What the stage answers for the user. */
  question: string;
};

export const STAGES: StageMeta[] = [
  {
    id: "scan",
    number: 1,
    title: "Scan",
    href: "/workspace/scan",
    question: "Where could this code waste energy?",
  },
  {
    id: "measure",
    number: 2,
    title: "Measure",
    href: "/workspace/measure",
    question: "What does it actually consume?",
  },
  {
    id: "improve",
    number: 3,
    title: "Improve",
    href: "/workspace/improve",
    question: "What would a better version look like?",
  },
  {
    id: "decide",
    number: 4,
    title: "Decide",
    href: "/workspace/decide",
    question: "Is the change proven better?",
  },
];

export type WorkspaceSettings = {
  projectPath: string;
  filePath: string;
  language: string;
  command: string;
  timeout: number;
  continuous: boolean;
};

export type ScanResult = {
  filePath: string;
  language: string;
  lineCount: number;
  functionCount: number;
  classCount: number;
  loopCount: number;
  detections: Detection[];
  summary: DetectionSummary | null;
  scannedAt: string;
};

export type MeasureResult = {
  baseline: EnergySnapshot;
  snapshots: EnergySnapshot[];
  measuredAt: string;
};

export type ImproveResult = {
  candidates: Candidate[];
  result: PipelineResult | null;
  ranAt: string;
};

export type DecisionAction = "ACCEPTED" | "REJECTED";

type StageState = "empty" | "active" | "done";

export type StageProgress = {
  state: StageState;
  /** Short right-aligned label: a count, a check, or "Next". */
  badge?: string;
  hint: string;
};

type WorkspaceValue = {
  settings: WorkspaceSettings;
  updateSettings: (patch: Partial<WorkspaceSettings>) => void;
  scan: ScanResult | null;
  setScan: (scan: ScanResult | null) => void;
  measure: MeasureResult | null;
  setMeasure: (measure: MeasureResult | null) => void;
  improve: ImproveResult | null;
  setImprove: (improve: ImproveResult | null) => void;
  decisions: Record<string, DecisionAction>;
  recordDecision: (candidateId: string, action: DecisionAction) => void;
  progress: Record<StageId, StageProgress>;
  recommendedStage: StageId;
  resetWorkspace: () => void;
};

const DEFAULT_SETTINGS: WorkspaceSettings = {
  projectPath: "",
  filePath: "",
  language: "auto",
  command: "",
  timeout: 300,
  continuous: false,
};

const SETTINGS_KEY = "oasis-workspace";

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

function readStoredSettings(): WorkspaceSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<WorkspaceSettings>;
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  // Start from defaults so the server render and first client render match,
  // then adopt the stored settings after mount.
  const [settings, setSettings] = useState<WorkspaceSettings>(DEFAULT_SETTINGS);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [measure, setMeasure] = useState<MeasureResult | null>(null);
  const [improve, setImprove] = useState<ImproveResult | null>(null);
  const [decisions, setDecisions] = useState<Record<string, DecisionAction>>({});

  useEffect(() => {
    setSettings(readStoredSettings());
  }, []);

  const updateSettings = useCallback((patch: Partial<WorkspaceSettings>) => {
    setSettings((previous) => {
      const next = { ...previous, ...patch };
      try {
        window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
      } catch {
        /* private mode: settings still work for this session */
      }
      return next;
    });
  }, []);

  const recordDecision = useCallback(
    (candidateId: string, action: DecisionAction) => {
      setDecisions((previous) => ({ ...previous, [candidateId]: action }));
    },
    [],
  );

  const resetWorkspace = useCallback(() => {
    setScan(null);
    setMeasure(null);
    setImprove(null);
    setDecisions({});
  }, []);

  const progress = useMemo<Record<StageId, StageProgress>>(() => {
    const detectionCount = scan?.detections.length ?? 0;
    const candidateCount = improve?.candidates.length ?? 0;
    const decidedCount = Object.keys(decisions).length;

    const scanState: StageProgress =
      scan === null
        ? { state: "active", badge: "Start", hint: "No scan yet" }
        : {
            state: "done",
            badge: String(detectionCount),
            hint:
              detectionCount === 0
                ? "No smells matched"
                : `${detectionCount} smell${detectionCount === 1 ? "" : "s"} found`,
          };

    const measureState: StageProgress =
      measure === null
        ? {
            state: scan === null ? "empty" : "active",
            badge: scan === null ? undefined : "Next",
            hint: scan === null ? "Waiting for a scan" : "No measurement yet",
          }
        : {
            state: "done",
            badge: "✓",
            hint: "Baseline recorded",
          };

    const improveState: StageProgress =
      improve === null
        ? {
            state: measure === null ? "empty" : "active",
            badge: measure === null ? undefined : "Next",
            hint:
              scan === null
                ? "Waiting for a scan"
                : measure === null
                  ? "Waiting for a measurement"
                  : "No candidates yet",
          }
        : {
            state: "done",
            badge: String(candidateCount),
            hint: `${candidateCount} candidate${candidateCount === 1 ? "" : "s"}`,
          };

    const decideState: StageProgress =
      candidateCount === 0
        ? {
            state: "empty",
            badge: undefined,
            hint: "Waiting for candidates",
          }
        : decidedCount >= candidateCount
          ? {
              state: "done",
              badge: "✓",
              hint: `All ${candidateCount} decided`,
            }
          : {
              state: "active",
              badge: decidedCount > 0 ? `${decidedCount}/${candidateCount}` : "Next",
              hint:
                decidedCount > 0
                  ? `${candidateCount - decidedCount} left to review`
                  : "Ready to review",
            };

    return {
      scan: scanState,
      measure: measureState,
      improve: improveState,
      decide: decideState,
    };
  }, [scan, measure, improve, decisions]);

  const recommendedStage: StageId = useMemo(() => {
    if (scan === null) return "scan";
    if (measure === null) return "measure";
    if (improve === null) return "improve";
    if (progress.decide.state !== "done") return "decide";
    return "scan";
  }, [scan, measure, improve, progress.decide.state]);

  const value = useMemo<WorkspaceValue>(
    () => ({
      settings,
      updateSettings,
      scan,
      setScan,
      measure,
      setMeasure,
      improve,
      setImprove,
      decisions,
      recordDecision,
      progress,
      recommendedStage,
      resetWorkspace,
    }),
    [
      settings,
      updateSettings,
      scan,
      measure,
      improve,
      decisions,
      recordDecision,
      progress,
      recommendedStage,
      resetWorkspace,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const value = useContext(WorkspaceContext);
  if (!value) {
    throw new Error("useWorkspace must be used inside a WorkspaceProvider.");
  }
  return value;
}

/** File name of the current target, for compact labels. */
export function targetName(path: string): string {
  const trimmed = path.trim().replace(/[\\/]+$/, "");
  if (!trimmed) return "";
  const parts = trimmed.split(/[\\/]/);
  return parts[parts.length - 1] || trimmed;
}
