import { useState } from "react";
import { api } from "../api";
import type { AskResult, Config, Measured, ReplayResult } from "../api";
import { Badge, Card, Empty, ErrorBox, Slider } from "../components/ui";
import { ms, pct } from "../format";

type Props = { config: Config; measured: Measured; threshold: number; setThreshold: (t: number) => void };

const PHASES = [
  { key: "embed_ms", name: "Embed", color: "var(--series-1)" },
  { key: "lookup_ms", name: "Lookup", color: "var(--series-2)" },
  { key: "generate_ms", name: "LLM", color: "var(--series-3)" },
  { key: "write_ms", name: "Cache write", color: "var(--series-4)" },
] as const;

export function PlaygroundPage({ config, measured, threshold, setThreshold }: Props) {
  const [question, setQuestion] = useState("");
  const [label, setLabel] = useState<string | null>(null);
  const [writeBack, setWriteBack] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [history, setHistory] = useState<AskResult[]>([]);

  const ask = async () => {
    if (!question.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await api.ask(question, threshold, writeBack);
      setHistory((h) => [r, ...h].slice(0, 20));
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const sample = async () => {
    try {
      const q = await api.sampleQuestion();
      setQuestion(q.question);
      setLabel(q.cacheable ? `held-out paraphrase of FAQ "${q.expected_intent}"` : "account-specific: should miss");
    } catch (e) { setError(e); }
  };

  const last = history[0];
  const baselineMs = measured.llm.llm_p50_ms;

  return (
    <div className="stack">
      <Card title="Ask the cached support assistant"
            subtitle={<>Lookups search the {config.entries} cached entries (seeded FAQs plus questions asked here).
              On a miss, {config.llm_endpoint} answers{writeBack ? <> and the answer is cached under tenant "{config.app_tenant}"</> : null}.</>}>
        <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(); }}>
          <input className="ask-input" value={question} placeholder="e.g. How do I change my PIN?"
                 onChange={(e) => { setQuestion(e.target.value); setLabel(null); }} aria-label="Question" />
          <button type="submit" className="primary" disabled={busy || !question.trim()}>{busy ? "Asking…" : "Ask"}</button>
          <button type="button" onClick={sample} disabled={busy}>Sample question</button>
        </form>
        {label && <p className="hint">{label}</p>}
        <div className="row">
          <Slider label="Similarity threshold" value={threshold} onChange={setThreshold} min={0.5} max={0.95} step={0.01}
                  format={(v) => v.toFixed(2)} />
          <label className="check"><input type="checkbox" checked={writeBack} onChange={(e) => setWriteBack(e.target.checked)} />
            Cache new answers</label>
        </div>
        {error !== null && <ErrorBox error={error} />}
      </Card>

      {busy && !last && <div className="skeleton" style={{ height: 180 }} aria-busy="true" />}
      {last && <ResultCard r={last} baselineMs={baselineMs} />}

      {history.length > 1 && (
        <Card title="This session">
          <table className="table">
            <thead><tr><th>Question</th><th>Result</th><th className="num">Similarity</th><th className="num">Total</th></tr></thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td>{h.question}</td>
                  <td>{h.hit ? <Badge tone="good">hit</Badge> : <Badge tone="neutral">miss</Badge>}</td>
                  <td className="num">{h.similarity?.toFixed(3) ?? "—"}</td>
                  <td className="num">{ms(h.total_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Replay threshold={threshold} />
    </div>
  );
}

function ResultCard({ r, baselineMs }: { r: AskResult; baselineMs: number | null }) {
  const total = PHASES.reduce((s, p) => s + (r[p.key] || 0), 0);
  const scaleMax = Math.max(total, baselineMs ?? 0) || 1;
  return (
    <Card title={r.hit ? <>Cache hit: served in {ms(r.total_ms)}</> : <>Cache miss: answered by the LLM in {ms(r.total_ms)}</>}
          subtitle={r.hit ? <>Matched “{r.matched_question}”</>
                          : r.matched_question ? <>Nearest entry “{r.matched_question}” was below the threshold</> : "The cache had no entries in scope"}>
      <SimilarityMeter similarity={r.similarity} threshold={r.threshold ?? 0} />
      <div className="timing" aria-label="Latency breakdown">
        <div className="timing-row">
          <span className="timing-label">This request</span>
          <div className="timing-bar">
            {PHASES.filter((p) => r[p.key] > 0).map((p) => (
              <span key={p.key} style={{ width: `${(r[p.key] / scaleMax) * 100}%`, background: p.color }}
                    title={`${p.name}: ${ms(r[p.key])}`} />
            ))}
          </div>
          <span className="timing-value">{ms(total)}</span>
        </div>
        {baselineMs !== null && (
          <div className="timing-row">
            <span className="timing-label">LLM alone (p50)</span>
            <div className="timing-bar"><span style={{ width: `${(baselineMs / scaleMax) * 100}%`, background: "var(--baseline)" }} /></div>
            <span className="timing-value">{ms(baselineMs)}</span>
          </div>
        )}
        <div className="legend">
          {PHASES.filter((p) => r[p.key] > 0).map((p) => (
            <span key={p.key}><i style={{ background: p.color }} />{p.name} {ms(r[p.key])}</span>
          ))}
        </div>
      </div>
      <div className="answer">{r.answer}</div>
      {!r.hit && r.output_tokens > 0 && <p className="source">{r.input_tokens} input + {r.output_tokens} output tokens</p>}
    </Card>
  );
}

function SimilarityMeter({ similarity, threshold }: { similarity: number | null; threshold: number }) {
  const s = similarity ?? 0;
  return (
    <div className="meter" aria-label={`Similarity ${s.toFixed(3)} against threshold ${threshold.toFixed(2)}`}>
      <div className="meter-track">
        <span className="meter-fill" style={{ width: `${s * 100}%` }} />
        <span className="meter-threshold" style={{ left: `${threshold * 100}%` }} title={`threshold ${threshold.toFixed(2)}`} />
      </div>
      <div className="meter-labels">
        <span>similarity <b>{similarity === null ? "—" : similarity.toFixed(3)}</b></span>
        <span>threshold <b>{threshold.toFixed(2)}</b></span>
      </div>
    </div>
  );
}

function Replay({ threshold }: { threshold: number }) {
  const [n, setN] = useState(50);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [res, setRes] = useState<ReplayResult | null>(null);

  const run = async () => {
    setBusy(true); setError(null);
    try { setRes(await api.replay(n, threshold)); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const hits = res ? res.rows.filter((r) => r.hit).sort((a, b) => (a.similarity ?? 0) - (b.similarity ?? 0)) : [];

  return (
    <Card title="Replay labeled traffic"
          subtitle="Look up a random sample of the held-out paraphrases (and the account-specific probes) at the current threshold: no LLM calls. Each is labeled with its true FAQ, so wrong hits are known; the hits feed the false-hit judge."
          actions={<>
            <select value={n} onChange={(e) => setN(parseInt(e.target.value))} aria-label="Sample size">
              {[25, 50, 100, 150].map((v) => <option key={v} value={v}>{v} queries</option>)}
            </select>
            <button className="primary" onClick={run} disabled={busy}>{busy ? "Replaying…" : "Replay"}</button>
          </>}>
      {error !== null && <ErrorBox error={error} onRetry={run} />}
      {busy && <div className="skeleton" style={{ height: 120 }} aria-busy="true" />}
      {!busy && !res && !error && <Empty title="No replay yet">Run one to see hit rate and wrong hits at {threshold.toFixed(2)}.</Empty>}
      {res && !busy && (
        <>
          <p>
            <b>{res.hits}</b> of {res.n} hit ({pct(res.hits / res.n)}) at {res.threshold.toFixed(2)};{" "}
            <b>{res.wrong_hits}</b> served the wrong FAQ ({pct(res.hits ? res.wrong_hits / res.hits : 0, 1)} of hits).
            Lowest-similarity hits first:
          </p>
          <table className="table">
            <thead><tr><th>Question</th><th>Served answer for</th><th className="num">Similarity</th><th>Label</th></tr></thead>
            <tbody>
              {hits.slice(0, 15).map((h, i) => (
                <tr key={i}>
                  <td>{h.question}</td><td>{h.matched_question}</td>
                  <td className="num">{h.similarity?.toFixed(3)}</td>
                  <td>{h.correct ? <Badge tone="good">right FAQ</Badge>
                                 : <Badge tone="critical">{h.cacheable ? "wrong FAQ" : "account-specific"}</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}
