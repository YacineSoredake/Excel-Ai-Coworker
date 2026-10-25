export type WorkbookStatus =
  | "uploaded" | "validating" | "validated" | "analyzing" | "profiled" | "rejected" | "failed";

export interface Workbook {
  id: string;
  filename: string;
  size_bytes: number;
  status: WorkbookStatus;
  sheet_count: number | null;
  hidden_sheets: number | null;
  has_external_links: boolean | null;
  rejection_reason: string | null;
  created_at: string;
}

export const BUCKET = "workbooks";
export const ARTIFACTS = "artifacts";
export const MAX_BYTES = 10 * 1024 * 1024;
export const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ---------- Phase 2: the workbook profile (report §13: Sheet, ColumnProfile, Finding) ---------- */

export type Severity = "high" | "medium" | "low" | "info";

export interface SheetRow {
  id: string; position: number; name: string; hidden: boolean; row_count: number; column_count: number;
  formula_count: number; error_count: number; merged_count: number; is_empty: boolean; notes: string[];
}
export interface DataTableRow {
  id: string; sheet_id: string; position: number; name: string; source: "detected" | "excel_table";
  cell_range: string; header_row: number | null; first_data_row: number; last_data_row: number;
  row_count: number; column_count: number; confidence: number; header_confidence: number | null;
  total_rows: number[]; blank_rows: number; truncated: boolean; artifact_path: string | null;
}
export interface ColumnRow {
  id: string; table_id: string; position: number; col_letter: string | null; name: string;
  data_type: string; role: string; role_subtype: string | null; role_confidence: number | null;
  type_confidence: number | null; currency: string | null; unit: string | null;
  missing_count: number; missing_rate: number; distinct_count: number; uniqueness: number;
  formula_share: number | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  stats: Record<string, any>;
}
export interface FindingRow {
  id: string; sheet_id: string | null; table_id: string | null; column_id: string | null; code: string;
  severity: Severity; title: string; detail: string | null; affected_count: number | null;
  total_count: number | null; sample_rows: number[];
}
export interface ProfileSummary {
  sheet_count: number; table_count: number; total_rows: number;
  measures: { table: string; column: string; subtype: string | null }[];
  dimensions: { table: string; column: string; subtype: string | null }[];
  identifiers: { table: string; column: string }[];
  time: { table: string; column: string; min: string | null; max: string | null; granularity: string | null }[];
  findings_by_severity: Record<Severity, number>;
}
export interface Relationship {
  from_table_name: string; from_column: string; to_table_name: string; to_column: string;
  containment: number; confidence: number;
}
export interface AnalyticsStatus {
  error?: string | null; facts?: number; dropped_unverified?: number;
  skipped_tables?: { table: string; reason: string }[];
}
export interface ProfileRow {
  summary: ProfileSummary; relationships: Relationship[]; engine_ms: number | null; analytics: AnalyticsStatus;
}

/* ---------- Phase 3: verified facts ---------- */

export type FactKind =
  | "kpi" | "ranking" | "trend" | "period_change" | "swing" | "anomaly_period" | "anomaly_values"
  | "breakdown" | "correlation" | "derivation" | "target";

export interface FactRow {
  id: string; table_id: string | null; kind: FactKind; key: string; rank: number; title: string; headline: string;
  definition: string; measure: string | null; dimension: string | null; time_column: string | null; agg: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  source: Record<string, any>;
  caveats: string[]; sample_rows: number[]; usefulness: number; reliability: number; score: number; verified: boolean;
}

export const TYPE_LABEL: Record<string, string> = {
  integer: "Whole number", decimal: "Decimal", currency: "Currency", percentage: "Percentage", date: "Date",
  datetime: "Date & time", boolean: "Yes / No", text: "Text", identifier: "Identifier", empty: "Empty",
};
export const ROLE_LABEL: Record<string, string> = {
  measure: "Measure", dimension: "Dimension", time: "Time", identifier: "Identifier", text: "Free text", ignore: "Ignored",
};
export const SEVERITY_ORDER: Severity[] = ["high", "medium", "low", "info"];
export const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High", medium: "Medium", low: "Low", info: "Note",
};

/* ---------- Phase 4: visualization specs ---------- */

export type ChartKind = "kpi" | "line" | "multi_line" | "hbar" | "donut" | "stacked_bar" | "target" | "scatter" | "histogram";

export interface ChartRow {
  id: string; table_id: string | null; key: string; kind: ChartKind; role: string;
  placement: "kpi" | "primary" | "secondary" | "explore"; position: number; title: string; why: string;
  fact_keys: string[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  encoding: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  query: Record<string, any> | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  options: Record<string, any>;
  usefulness: number; reliability: number; readability: number; score: number; caveats: string[];
}

/* ---------- Phase 5: AI layer ---------- */

export interface PlanLike { op: string; [k: string]: unknown }

export interface ContextRow {
  domain: { key: string; label: string; confidence: number; evidence: string[]; alternatives: { key: string; label: string; confidence: number }[] };
  purpose: string; rows: number; tables: number; sheets: number;
  entities: { kind: string; label: string; columns: string[] }[];
  measures: { name: string; subtype: string | null; currency: string | null }[];
  time: { column: string; from: string; to: string; granularity: string | null } | null;
  potential_analyses: string[]; assumptions: string[]; uncertainty: string | null;
  suggested_questions: { text: string; plan: PlanLike }[];
}

export interface InsightRow {
  id: string; table_id: string | null; key: string; category: string; priority: number; statement: string;
  interpretation: string; next_check: string; next_plan: PlanLike | null; caveats: string[]; fact_keys: string[];
  source: "template" | "ai";
}

export interface Answer {
  status: "ok" | "clarify" | "unsupported" | "error";
  text: string;
  plan: PlanLike | null; plan_summary: string | null; definition: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: { kind: string; data: Record<string, any>; rows_used: number; rows_after_filters: number } | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  chart: { kind: string; why?: string; data: Record<string, any>; options: Record<string, any> } | null;
  caveats: string[]; notes: string[]; sample_rows: number[];
  followups: { text: string; plan: PlanLike }[];
  suggestions?: { text: string; plan: PlanLike }[];
  options: string[] | null;
  source: { plan: "ai" | "rules" | "suggested" | null; text: "ai" | "template"; text_issues?: string[] };
}

export interface QuestionRow {
  id: string; workbook_id: string; text: string; status: "queued" | "answering" | "answered" | "failed";
  answer: Answer | null; created_at: string;
}

/* ---------- Phase 6: guided analysis ---------- */

export interface GuideAction { label: string; kind: "ask" | "details" | "ask_tab"; text: string | null; plan: PlanLike | null }
export interface GuideStep {
  id: string; kind: string; title: string; narrative: string; notes?: string[]; chart_keys: string[]; fact_keys: string[];
  actions: GuideAction[]; value: number;
}
export interface GuideRow { version: number; table: string; table_index: number; steps: GuideStep[] }
