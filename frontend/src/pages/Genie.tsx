import { useEffect, useState } from "react";
import { api } from "../api";
import type { GenieAnswer, GenieQuery } from "../api";
import { Card, Empty, ErrorBox, Skeleton } from "../components/ui";

// The same questions as the space's sample questions (resources/genie.yml).
const SAMPLES = [
  "What was our deflection rate and cost per question last week?",
  "Is the false-hit monitor OK right now?",
  "Which FAQ categories get the most wrong answers at a 0.75 threshold?",
  "How many repeat questions would we catch at 0.70 vs 0.80, and how many wrong answers?",
  "Show the cached answers the judge marked wrong",
];

type Turn = { question: string; answer?: GenieAnswer; error?: unknown };

export function GeniePage() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.genieConfig().then((c) => setEnabled(c.enabled)).catch(() => setEnabled(false)); }, []);

  const ask = async (q: string) => {
    q = q.trim();
    if (!q || busy) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [...t, { question: q }]);
    try {
      const a = await api.genieAsk(q, conversationId);
      setConversationId(a.conversation_id);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, answer: a } : x)));
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: e } : x)));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => { setTurns([]); setConversationId(null); };

  if (enabled === null) return <Skeleton height={200} />;
  if (!enabled) return <Empty title="No Genie space attached">Deploy the bundle: it creates the space (resources/genie.yml) and attaches it to the app.</Empty>;

  return (
    <div className="stack">
      <Card title="Ask Genie about the cache"
            subtitle="Plain-English questions over the governed cache metrics: a Genie space on the gold tables the semantic_cache_metrics pipeline builds. Every answer shows the SQL Genie ran."
            actions={turns.length ? <button onClick={reset} disabled={busy}>New conversation</button> : null}>
        <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(question); }}>
          <input className="ask-input" value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Question for Genie"
                 placeholder="e.g. What did the cache save us this week?" />
          <button type="submit" className="primary" disabled={busy || !question.trim()}>{busy ? "Asking…" : "Ask"}</button>
        </form>
        {!turns.length && (
          <div className="chips">
            {SAMPLES.map((s) => <button key={s} type="button" onClick={() => ask(s)} disabled={busy}>{s}</button>)}
          </div>
        )}
      </Card>

      {turns.map((t, i) => (
        <Card key={i} title={t.question}>
          {!t.answer && !t.error && <Skeleton height={80} />}
          {t.error !== undefined && <ErrorBox error={t.error} />}
          {t.answer && <AnswerView a={t.answer} onAsk={ask} busy={busy} last={i === turns.length - 1} />}
        </Card>
      ))}
    </div>
  );
}

function AnswerView({ a, onAsk, busy, last }: { a: GenieAnswer; onAsk: (q: string) => void; busy: boolean; last: boolean }) {
  return (
    <>
      {a.error && <p className="hint"><b>Genie couldn't answer:</b> {a.error}</p>}
      {a.text.map((t, i) => <p key={i} className="answer">{t}</p>)}
      {a.queries.map((q, i) => <QueryView key={i} q={q} />)}
      {last && a.suggested_questions.length > 0 && (
        <div className="chips">
          {a.suggested_questions.map((s) => <button key={s} type="button" onClick={() => onAsk(s)} disabled={busy}>{s}</button>)}
        </div>
      )}
    </>
  );
}

function QueryView({ q }: { q: GenieQuery }) {
  return (
    <div className="genie-query">
      {q.description && <p className="muted">{q.description}</p>}
      {q.rows.length > 0 ? (
        <div className="table-wrap">
          <table className="table">
            <thead><tr>{q.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {q.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v ?? "—"}</td>)}</tr>)}
            </tbody>
          </table>
          {q.row_count > q.rows.length && <p className="hint">First {q.rows.length} of {q.row_count} rows.</p>}
        </div>
      ) : <p className="hint">The query returned no rows.</p>}
      {q.sql && (
        <details>
          <summary>SQL Genie ran</summary>
          <pre className="sql">{q.sql}</pre>
        </details>
      )}
    </div>
  );
}
