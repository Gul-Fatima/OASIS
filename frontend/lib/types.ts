/**
 * Types mirroring the backend response contracts.
 *
 * Everything here is what the API actually returns; where the backend is
 * loose (CodeCarbon rows) fields stay optional. Note the deliberate split
 * between `predicted*` and `measured*` fields — CLAUDE.md forbids mixing
 * predictions with measurements.
 */

/* ============================================================
   ENERGY
   ============================================================ */

export type EnergySnapshot = {
  energy_consumed?: number | null; // kWh (CodeCarbon)
  emissions?: number | null; // kg CO2eq
  emissions_rate?: number | null;
  cpu_power?: number | null;
  gpu_power?: number | null;
  ram_power?: number | null;
  cpu_energy?: number | null;
  gpu_energy?: number | null;
  ram_energy?: number | null;
  water_consumed?: number | null;
  duration?: number | null;
  execution_time_seconds?: number | null;
  execution_status?: "success" | "failed" | "measuring" | "monitoring" | string;
  baseline_valid?: boolean;
  continuous?: boolean;
  final?: boolean;
  snapshot_index?: number;
  process_running?: boolean;
  stop_reason?: string | null;
  stopped_by_user?: boolean;
  return_code?: number | null;
  pid?: number | null;
  stdout?: string;
  stderr?: string;
  project_path?: string;
  file_count?: number;
  cpu_count?: number | null;
  gpu_count?: number | null;
  ram_total_size?: number | null;
  tracking_mode?: string | null;
  on_cloud?: boolean | null;
  pue?: number | null;
  wue?: number | null;
  country_name?: string | null;
  timestamp?: string | null;
  run_id?: string | null;
  experiment_id?: string | null;
  project_name?: string | null;
  error?: string;
  detail?: string;
};

/* ============================================================
   CODE UNDERSTANDING
   ============================================================ */

export type Complexity = {
  measured?: number;
  max?: number;
  total?: number;
};

export type FileDetail = {
  file: string;
  language?: string | null;
  functions?: number;
  classes?: number;
  loops?: number;
  conditionals?: number;
  calls?: number;
  dependencies?: number;
  complexity?: Complexity;
  failed?: boolean;
  error?: string | null;
};

export type FunctionEntry = {
  name: string;
  file?: string;
  start_line?: number;
  end_line?: number;
  complexity?: number | null;
  arguments?: string[];
  decorators?: string[];
};

export type ClassEntry = {
  name: string;
  file?: string;
  start_line?: number;
  end_line?: number;
  methods?: string[];
};

export type LoopEntry = {
  kind: string;
  line?: number;
  file?: string;
};

export type CallEntry = {
  name: string;
  line?: number;
  file?: string;
  argument_count?: number;
};

export type IoOperation = {
  file: string;
  operation: string;
};

export type FolderAnalysisResult = {
  mode: "file" | "folder";
  language: string | null;
  language_filter?: string;
  languages?: Record<string, number>;
  scan_path?: string;
  project_path?: string;
  file_count?: number;
  analyzed_files?: number;
  failed_files?: number;
  total_files_found?: number;
  total_lines?: number;
  functions?: FunctionEntry[];
  classes?: ClassEntry[];
  loops?: LoopEntry[];
  conditionals?: number;
  function_calls?: CallEntry[];
  io_operations?: IoOperation[];
  data_structures?: string[];
  dependencies?: string[];
  allocations?: number;
  complexity?: Complexity;
  files?: FileDetail[];
  failures?: { file: string; language?: string | null; error?: string | null }[];
  notes?: string[];
};

/* ============================================================
   ENERGY SMELL DETECTION
   ============================================================ */

export type Detection = {
  category_id: string;
  subcategory_id: string;
  category_name: string;
  subcategory_name: string;
  location?: { function?: string; file?: string; line?: number };
  description: string;
  severity: "high" | "medium" | "low" | string;
  suggestion?: string;
  evidence?: string;
};

export type DetectionSummary = {
  detection_count: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  categories_detected: string[];
};

export type TaxonomySubcategory = {
  id: string;
  name: string;
  description: string;
};

export type TaxonomyCategory = {
  id: string;
  name: string;
  description: string;
  subcategories: TaxonomySubcategory[];
};

export type TaxonomyResponse = {
  categories: TaxonomyCategory[];
  total_categories: number;
  total_subcategories: number;
};

/* ============================================================
   OPTIMIZE (developer-facing analysis)
   ============================================================ */

export type OptimizeIssue = {
  id: string;
  rule_id: string | null;
  category_id: string;
  category_name?: string | null;
  subcategory_id: string;
  subcategory_name?: string | null;
  title: string;
  line: number | null;
  function?: string | null;
  strategy: string;
  example?: string;
  origin: "structural" | "pattern" | string;
};

export type OptimizeResponse = {
  filename: string;
  language: string;
  line_count: number;
  issue_count: number;
  issues: OptimizeIssue[];
  prompt: string;
  file_path?: string | null;
};

/* ============================================================
   RULE BASE (okeb.json) + STRUCTURAL MATCHER
   ============================================================ */

export type RuleEntry = {
  rule_id: string;
  source_id?: string | null;
  category_id: string;
  category_name?: string | null;
  subcategory_id?: string | null;
  subcategory_name?: string | null;
  pattern: string;
  strategy: string;
  preconditions?: string;
  detection_mode?: "static" | "hybrid" | "profiling" | string;
  has_matcher: boolean;
  duplicate_of?: string | null;
};

export type RuleValidationProblem = {
  level: "error" | "warning" | string;
  code: string;
  message: string;
};

export type RuleBaseResponse = {
  rule_count: number;
  implemented_count: number;
  implemented_rule_ids: string[];
  per_category: Record<string, { rules: number; implemented: number }>;
  subcategories_without_rules: string[];
  subcategories_without_matcher: string[];
  categories: { id: string; name: string; subcategory_count: number }[];
  validation: RuleValidationProblem[];
  rules: RuleEntry[];
};

export type RuleGuard = {
  name: string;
  status: "passed" | "failed" | "unresolved" | string;
  detail?: string;
};

export type RuleIssue = {
  rule_id: string;
  category_id?: string | null;
  category_name?: string | null;
  subcategory_id?: string | null;
  subcategory_name?: string | null;
  pattern: string;
  location: { file?: string; line?: number; end_line?: number; function?: string | null };
  capture: Record<string, string>;
  rewrite_hint?: string;
  guards: RuleGuard[];
  guard_status: string;
  confidence: string;
  evidence_strength?: string;
  evidence?: string;
  strategy: string;
  preconditions?: string;
  expected_benefit?: string;
  fix_mode?: string;
  kb_rule_found: boolean;
};

export type RuleSelfTestCase = {
  rule_id: string;
  name: string;
  should_match: boolean;
  expected: "match" | "no match" | string;
  detected: boolean;
  detected_rules: string[];
  passed: boolean;
  note: string;
  source: string;
  error: string | null;
};

export type RuleSelfTestResponse = {
  case_count: number;
  passed_count: number;
  failed_count: number;
  results: RuleSelfTestCase[];
  implemented_rule_ids: string[];
  rules_with_cases: string[];
  rules_without_cases: string[];
  requires_measurement: boolean;
  note: string;
};

export type RuleTestResponse = {
  file: string;
  language: string;
  issues: RuleIssue[];
  summary: {
    issue_count: number;
    rule_count: number;
    by_rule: Record<string, number>;
    by_category: Record<string, number>;
    requires_measurement: boolean;
    matcher_failures: { matcher?: string; error?: string }[];
  };
  supported_rule_ids: string[];
  matched_rule_ids: string[];
  unmatched_rule_ids: string[];
};

/* ============================================================
   CANDIDATES
   ============================================================ */

export type CandidateChange = {
  smell_id?: string;
  description?: string;
  before?: string;
  after?: string;
};

export type VerificationCheck = {
  name: string;
  passed: boolean | null;
  detail?: string;
};

export type VerificationResult = {
  status: string;
  passed: boolean;
  inconclusive?: boolean;
  syntax_ok?: boolean | null;
  behaviour_ok?: boolean | null;
  checks?: VerificationCheck[];
  tests_total?: number;
  tests_passed?: number;
  tests_failed?: number;
  errors?: string[];
  notes?: string[];
};

export type BenchmarkRun = {
  label: string;
  index: number;
  success: boolean;
  energy_kwh?: number | null;
  energy_joules?: number | null;
  duration_seconds?: number | null;
  average_watts?: number | null;
  return_code?: number | null;
  error?: string | null;
};

export type BenchmarkSummary = {
  label?: string;
  runs?: number;
  mean_energy_joules?: number | null;
  min_energy_joules?: number | null;
  max_energy_joules?: number | null;
  mean_duration_seconds?: number | null;
  average_watts?: number | null;
  energy_spread_percent?: number | null;
};

export type BenchmarkResult = {
  status: string;
  verdict?: string;
  runs_per_version?: number;
  warmup_runs?: number;
  original?: BenchmarkRun[];
  candidate?: BenchmarkRun[];
  original_summary?: BenchmarkSummary;
  candidate_summary?: BenchmarkSummary;
  improvement_percent?: number | null;
  notes?: string[];
  errors?: string[];
  duration_seconds?: number;
};

export type DecisionResult = {
  status: string;
  recommendation: string;
  rationale: string[];
  measured_improvement_percent?: number | null;
  predicted_impact?: string | null;
  considered_noise_floor_percent?: number;
  correctness_status?: string | null;
  benchmark_status?: string | null;
  decided_at?: string;
  evidence?: {
    time_change_percent?: number | null;
    benchmark?: BenchmarkResult;
    verification?: VerificationResult;
  };
};

export type Candidate = {
  candidate_id: string;
  source_code: string;
  parent_code_id?: string;
  opportunity_id?: string;
  strategy?: string;
  generation_method?: string;
  model?: string;
  target_smells?: string[];
  changes_made?: CandidateChange[];
  explanation?: string;
  predicted_impact?: string;
  predicted_impact_score?: number;
  confidence?: number;
  correctness_status?: string;
  benchmark_status?: string;
  measured_energy?: {
    original_mean_joules?: number | null;
    candidate_mean_joules?: number | null;
    improvement_percent?: number | null;
  } | null;
  measured_time?: {
    original_mean_seconds?: number | null;
    candidate_mean_seconds?: number | null;
  } | null;
  measured_resources?: Record<string, unknown> | null;
  final_status?: string;
  created_at?: string;
  measurement_available?: boolean;
  // Ranking annotations
  rank?: number;
  score?: number;
  factors?: Record<string, number>;
  rationale?: string[];
  missing_inputs?: string[];
  // Pipeline annotations
  candidate_index?: number;
  verification?: VerificationResult;
  benchmark?: BenchmarkResult;
  decision?: DecisionResult;
};

export type GenerateResponse = {
  file_path: string;
  language: string;
  model?: string;
  detections: Detection[];
  detection_summary: DetectionSummary;
  candidates: Candidate[];
  candidate_count: number;
  note?: string;
};

export type PipelineResult = {
  file_path: string;
  project_path?: string;
  language: string;
  model?: string;
  detections: Detection[];
  detection_summary: DetectionSummary;
  candidates: Candidate[];
  benchmark_ran?: boolean;
  command?: string;
  stopped_reason?: string;
  message?: string;
  summary?: {
    candidates_generated?: number;
    verified?: number;
    measured?: number;
    improved?: number;
    best_improvement_percent?: number | null;
  };
  note?: string;
};

/* ============================================================
   LLM / HISTORY
   ============================================================ */

export type LlmStatus = {
  provider: string;
  configured: boolean;
  model: string;
  api_base: string;
  timeout_seconds: number;
  hint?: string | null;
};

export type DecisionRecord = {
  candidate_id: string;
  status: string;
  measured_improvement_percent?: number | null;
  rationale?: string[];
  developer_action: string;
  recorded_at?: string;
  timestamp?: number;
};

export type LanguagesResponse = {
  supported?: string[];
  extensions?: string[];
  [key: string]: unknown;
};
