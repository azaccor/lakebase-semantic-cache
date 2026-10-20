// Typed fetch helpers for the FastAPI backend.

export type Config = {
  backend: string;
  llm_endpoint: string;
  embedding_endpoint: string;
  threshold: number;
  scope: Record<string, string>;
  app_tenant: string;
  price_in_per_m: number;
  price_out_per_m: number;
  cache_table: string;
  lakebase_instance: string;
  entries: number;
  total_hits: number;
};

export type Measured = {
  backend: string;
  llm: {
    source: string; n: number; last_ts: string | null;
    llm_ms: number | null; llm_p50_ms: number | null; llm_p95_ms: number | null;
    input_tokens: number | null; output_tokens: number | null; write_ms: number | null;
  };
  overhead: {
    source: string; n: number; last_ts: string | null;
    embed_ms: number | null; lookup_ms: number | null; embed_p50_ms: number | null; lookup_p50_ms: number | null;
  };
  sweep: {
    source: string; run_id: string | null;
    points: { threshold: number; hit_rate: number; cacheable_hit_rate: number; precision: number | null;
              false_hit_rate: number; cacheable_false_hit_rate: number | null; novel_hit_rate: number | null;
              account_specific_hits: number }[];
  };
};

export type AskResult = {
  question: string;
  answer: string | null;
  hit: boolean;
  similarity: number | null;
  cache_id: string | null;
  matched_question: string | null;
  threshold: number | null;
  embed_ms: number;
  lookup_ms: number;
  generate_ms: number;
  write_ms: number;
  total_ms: number;
  input_tokens: number;
  output_tokens: number;
};

export type ReplayResult = {
  n: number;
  hits: number;
  wrong_hits: number;
  threshold: number;
  rows: { question: string; hit: boolean; similarity: number | null; matched_question: string | null;
          cacheable: boolean; correct: boolean; lookup_ms: number }[];
};

export type JudgeJob = { id: string; state: "running" | "done" | "error"; total: number | null; done: number;
                         error: string | null };

export type JudgeRow = {
  judged_ts: string; source: string; question: string; matched_question: string; similarity: number | null;
  threshold: number | null; cached_answer: string; fresh_answer: string; verdict: string; reason: string;
  expected_intent: string | null; matched_intent: string | null; label_correct: boolean | null;
};

export type JudgeSummary = {
  source: string; judge_model: string; judge_version: string; prompt_version: string; last_ts: string | null;
  judged: number; incorrect: number; false_hit_rate: number | null; ci95: [number, number] | null;
  labeled: number; agreement: number | null; label_false_hit_rate: number | null;
  rows: JudgeRow[];
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body && body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON error body (e.g. a proxy timeout page)
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

export type GenieQuery = {
  title: string | null; description: string | null; sql: string | null;
  columns: string[]; rows: (string | null)[][]; row_count: number;
};
export type GenieAnswer = {
  conversation_id: string; message_id: string; status: string | null; error: string | null;
  text: string[]; queries: GenieQuery[]; suggested_questions: string[];
};

const post = <T>(path: string, body: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  config: () => call<Config>("/api/config"),
  measured: (refresh = false) => call<Measured>(`/api/measured${refresh ? "?refresh=true" : ""}`),
  ask: (question: string, threshold: number, write_back: boolean) =>
    post<AskResult>("/api/ask", { question, threshold, write_back }),
  sampleQuestion: () => call<{ question: string; expected_intent: string | null; cacheable: boolean }>("/api/sample-question"),
  replay: (n: number, threshold: number) => post<ReplayResult>("/api/replay", { n, threshold }),
  judgeRun: (n: number, sources: string[]) => post<{ job_id: string }>("/api/judge/run", { n, sources }),
  judgeJob: (id: string) => call<JudgeJob>(`/api/judge/job/${id}`),
  judgeResults: () => call<JudgeSummary>("/api/judge/results"),
  genieConfig: () => call<{ enabled: boolean; space_id: string | null }>("/api/genie/config"),
  genieAsk: (question: string, conversation_id: string | null) =>
    post<GenieAnswer>("/api/genie/ask", { question, conversation_id }),
};
