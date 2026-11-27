// Typed client for the Signal Lab API.

export type Capability = "traces" | "metrics" | "logs";

export interface BackendLink { id: string; label: string; url: string; description?: string }
export interface Backend {
  id: string;
  title: string;
  description: string;
  vendor: string;
  capabilities: Capability[];
  query_languages: string[];
  components: { id: string; title: string; role: string }[];
  enabled: boolean;
  links: BackendLink[];
  link_templates: Record<string, string>;
  color?: string;
  settings: Record<string, string>;
  path?: string;
}

export interface ScenarioService { id: string; title: string; description: string; calls: string[]; role: string; online?: boolean; stats?: ServiceStats | null; changed?: { by: string; at: number; expires: number | null } }
export interface ServiceStats { chaos: { latency_ms: number; error_rate: number }; requests: number; errors: number; p50_ms: number | null; p95_ms: number | null; rps?: number }
export interface Scenario { id: string; title: string; description: string; services: ScenarioService[]; runner_env: string[] }

export interface Meta {
  version: string;
  backends: Backend[];
  scenario: Scenario | null;
  runs_enabled: boolean;
  runner: "local" | "remote";
  otlp_endpoint: string;
  collector: boolean;
  plugin_errors: string[];
  capabilities: Capability[];
}

export interface ComponentHealth { ok: boolean; detail: string; mode?: string }
export interface Health {
  collector: ComponentHealth;
  runner: ComponentHealth;
  backends: Record<string, Record<string, ComponentHealth>>;
  tap: Record<string, number>;
}

export type LessonKind = "code" | "collector" | "query" | "quiz" | "task" | "read" | "experiment" | "incident";
export interface LessonOutline {
  id: string; slug: string; title: string; summary: string; kind: LessonKind; minutes: number;
  requires: string[]; concepts: string[]; assumes: string[];
}
export interface Module { id: string; title: string; description: string; assumes: string[]; lessons: LessonOutline[] }
export interface Pack {
  id: string; title: string; description: string; order: number; icon?: string;
  requires: { backends?: string[]; capabilities?: string[] };
  locked: boolean; missing: { backends: string[]; capabilities: string[] };
  modules: Module[];
}

export interface LessonFile { filename: string; language: string; content: string }
export interface QuizQuestion { id: string; prompt: string; options?: { id: string; label: string }[]; multiple?: boolean; input?: "text"; kind?: "time" | "query"; language?: string; backend?: string; placeholder?: string }
export interface Lesson extends LessonOutline {
  module: string; pack: string; body: string;
  checks: { id: string; title: string; type: string }[];
  hints: string[];
  starter?: LessonFile; solution?: LessonFile; traffic?: LessonFile;
  query?: { backend: string; language: string; range_s?: number; examples?: { label: string; query: string }[] };
  quiz?: { questions: QuizQuestion[] };
  tools: string[];
  scenario?: { chaos?: Record<string, { latency_ms?: number; error_rate?: number }>; load?: number; note?: string };
  runtime: { service?: string; auto_instrument?: boolean; timeout?: number };
  env: Record<string, string>;
  experiment?: { hypothesis?: string; baseline_s?: number; duration_s?: number; recovery_s?: number; steady_state?: Record<string, unknown> } | null;
  incident?: { duration_s?: number; metrics_only?: boolean } | null;
}

export type CheckStatus = "pass" | "fail" | "pending";
export interface CheckResult { id: string; title: string; type: string; status: CheckStatus; detail: string }

export interface Span {
  trace_id: string; span_id: string; parent_span_id: string | null; name: string; kind: string;
  start_ms: number; end_ms: number; duration_ms: number;
  status: { code: "unset" | "ok" | "error"; message: string };
  attributes: Record<string, unknown>;
  events: { name: string; time_ms: number; attributes: Record<string, unknown> }[];
  links: { trace_id: string; span_id: string; attributes: Record<string, unknown> }[];
  resource: Record<string, unknown>; service: string; scope: { name: string; version: string };
}
export interface Series {
  key: string; type: string; instrument: string; service: string; attributes: Record<string, unknown>; time_ms: number;
  value?: number; count?: number; sum?: number | null; min?: number | null; max?: number | null;
  bounds?: number[]; bucket_counts?: number[]; scale?: number;
  positive?: { offset: number; bucket_counts: number[] };
  exemplars?: { value: number; trace_id: string | null; span_id: string | null }[];
  history: { time_ms: number; value?: number; count?: number; sum?: number }[];
}
export interface Metric { name: string; description: string; unit: string; type: string; instrument: string; temporality: string | null; service: string; series: Series[] }
export interface LogRecord {
  time_ms: number; severity_text: string; severity_number: number; body: unknown;
  attributes: Record<string, unknown>; trace_id: string | null; span_id: string | null;
  resource: Record<string, unknown>; service: string; scope: { name: string };
}
export interface Telemetry { spans: Span[]; metrics: Metric[]; logs: LogRecord[] }
export interface OutputLine { stream: "stdout" | "stderr" | "system"; text: string; t?: number }
export interface SignalConfirm { state: "pending" | "found" | "missing" | "unsupported"; url?: string | null; after_ms?: number; trace_id?: string; metric?: string }
export interface RunSummary {
  id: string; lesson: string; created: number;
  status: "queued" | "running" | "collecting" | "done" | "error";
  exit_code: number | null; duration_ms: number | null;
  counts: { spans: number; traces: number; metrics: number; series: number; logs: number };
  checks: CheckResult[];
  backends: Record<string, { title: string; signals: Partial<Record<Capability, SignalConfirm>> }>;
}
export interface RunSnapshot extends RunSummary { output: OutputLine[]; telemetry: Telemetry }

export interface QueryResult { columns: string[]; rows: unknown[][]; series: { name: string; labels: Record<string, string>; points: [number, number][] }[]; stats: Record<string, unknown>; error: string | null }

export interface CollectorInfo { files: { name: string; path: string; content: string }[]; pipelines: Record<string, { receivers?: string[]; processors?: string[]; exporters?: string[] }>; components: Record<string, string[]> }
export interface PluginsInfo { backends: Backend[]; lesson_packs: { id: string; title: string; description: string; lessons: number; requires: Pack["requires"]; path: string }[]; scenarios: (Scenario & { path: string })[]; check_types: string[]; errors: string[] }

export interface User { id: string; username: string; display_name: string; role: "admin" | "learner" }
export interface Me { auth: "open" | "accounts"; user: User | null; signup: boolean; storage: string; scenario_control: "everyone" | "admins" }
export interface AdminUser extends User { created: number; last_seen: number | null; done: number; known: number; runs: number; last_lesson: string | null }

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not json */ }
    if (res.status === 401) window.dispatchEvent(new Event("sl:unauthorized"));
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  me: () => request<Me>("/api/me"),
  login: (username: string, password: string) => post<{ user: User }>("/api/auth/login", { username, password }),
  signup: (username: string, password: string, display_name?: string) => post<{ user: User }>("/api/auth/signup", { username, password, display_name }),
  logout: () => post("/api/auth/logout"),
  adminUsers: () => request<AdminUser[]>("/api/admin/users"),
  adminCreate: (username: string, password: string, role: string) => post<User>("/api/admin/users", { username, password, role }),
  adminPatch: (id: string, body: { role?: string; password?: string }) => request(`/api/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  adminDelete: (id: string) => request(`/api/admin/users/${id}`, { method: "DELETE" }),
  meta: () => request<Meta>("/api/meta"),
  health: () => request<Health>("/api/health"),
  course: () => request<Pack[]>("/api/course"),
  lesson: (id: string) => request<Lesson>(`/api/lessons/${id}`),
  run: (lesson: string, code: string) => post<RunSummary>("/api/runs", { lesson, code }),
  query: (backend: string, language: string, query: string, lesson?: string, range_s?: number) =>
    post<{ result: QueryResult; checks: CheckResult[] }>("/api/query", { backend, language, query, lesson, range_s }),
  answer: (lesson: string, question: string, answer: string | string[]) => post<{ correct: boolean; explanation: string }>(`/api/lessons/${lesson}/answer`, { question, answer }),
  verify: (lesson: string) => post<{ checks: CheckResult[] }>(`/api/lessons/${lesson}/verify`),
  setup: (lesson: string) => post<{ applied: string[] }>(`/api/lessons/${lesson}/setup`),
  scenario: () => request<Scenario>("/api/scenario"),
  chaos: (service: string, body: { latency_ms?: number; error_rate?: number }) => post(`/api/scenario/services/${service}/chaos`, body),
  load: (rps: number) => post("/api/scenario/load", { rps }),
  resetScenario: () => post("/api/scenario/reset"),
  collector: () => request<CollectorInfo>("/api/collector"),
  plugins: () => request<PluginsInfo>("/api/plugins"),
  suggest: (backend: string, language: string, kind = "metric") => request<string[]>(`/api/suggest/${backend}?language=${language}&kind=${kind}`),
};
