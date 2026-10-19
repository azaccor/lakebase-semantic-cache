import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { JudgeJob, JudgeRow, JudgeSummary } from "../api";
import { Badge, Card, Empty, ErrorBox, Skeleton, Stat } from "../components/ui";
import { ago, pct } from "../format";

const SOURCES = [
  { key: "app", label: "Playground questions" },
  { key: "app-replay", label: "Replayed labeled paraphrases" },
];

export function JudgePage() {
  const [summary, setSummary] = useState<JudgeSummary | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [n, setN] = useState(10);
  const [sources, setSources] = useState<string[]>(["app", "app-replay"]);
  const [job, setJob] = useState<JudgeJob | null>(null);
  const [runError, setRunError] = useState<unknown>(null);
  const [open, setOpen] = useState<number | null>(null);
  const timer = useRef<number | null>(null);

  const load = async () => {
    setLoadError(null);
    try { setSummary(await api.judgeResults()); } catch (e) { setLoadError(e); }
  };
  useEffect(() => { load(); return () => { if (timer.current) window.clearInterval(timer.current); }; }, []);

  const run = async () => {
    setRunError(null);
    try {
      const { job_id } = await api.judgeRun(n, sources);
      setJob({ id: job_id, state: "running", total: null, done: 0, error: null });
      timer.current = window.setInterval(async () => {
        try {
          const j = await api.judgeJob(job_id);
          setJob(j);
          if (j.state !== "running") {
            if (timer.current) window.clearInterval(timer.current);
            load();
          }
        } catch (e) {
          if (timer.current) window.clearInterval(timer.current);
          setRunError(e);
        }
      }, 2000);
    } catch (e) { setRunError(e); }
  };

  const running = job?.state === "running";

  return (
    <div className="stack">
      <Card title="Measure the false-hit rate"
            subtitle="For a sample of recent cache hits, the LLM writes a fresh answer to the user's question, then judges whether the answer the cache served is a correct, sufficient answer to it. Results are stored in Delta next to the request log."
            actions={<>
              <select value={n} onChange={(e) => setN(parseInt(e.target.value))} aria-label="Hits to judge" disabled={running}>
                {[5, 10, 25, 50].map((v) => <option key={v} value={v}>{v} hits</option>)}
              </select>
              <button className="primary" onClick={run} disabled={running || !sources.length}>{running ? "Judging…" : "Judge hits"}</button>
            </>}>
        <div className="row">
          {SOURCES.map((s) => (
            <label key={s.key} className="check">
              <input type="checkbox" checked={sources.includes(s.key)} disabled={running}
                     onChange={(e) => setSources((cur) => e.target.checked ? [...cur, s.key] : cur.filter((x) => x !== s.key))} />
              {s.label}
            </label>
          ))}
        </div>
        <p className="hint">Each judged hit costs two LLM calls. Hits already judged are skipped.</p>
        {job && (
          <div className="progress" role="status">
            {job.state === "running" && <>Judging {job.done} of {job.total ?? "…"} hits</>}
            {job.state === "done" && <>Judged {job.done} {job.done === 1 ? "hit" : "hits"}{job.total === 0 && ": no unjudged hits. Ask questions or replay traffic in the Playground first"}.</>}
            {job.state === "error" && <ErrorBox error={job.error} />}
            {job.total ? <div className="progress-track"><span style={{ width: `${(job.done / job.total) * 100}%` }} /></div> : null}
          </div>
        )}
        {runError !== null && <ErrorBox error={runError} />}
      </Card>

      {loadError !== null && <ErrorBox error={loadError} onRetry={load} />}
      {!summary && loadError === null && <Skeleton height={220} />}
      {summary && summary.judged === 0 && (
        <Empty title="No judged hits yet">Ask questions or replay labeled traffic in the Playground, then judge the hits here.</Empty>
      )}
      {summary && summary.judged > 0 && (
        <>
          <div className="stats">
            <Stat label="False-hit rate (judge)" value={pct(summary.false_hit_rate, 1)}
                  detail={<>{summary.incorrect} of {summary.judged} hits{summary.ci95 && <>; 95% CI {pct(summary.ci95[0], 1)}–{pct(summary.ci95[1], 1)}</>}</>}
                  tone={(summary.false_hit_rate ?? 0) > 0.05 ? "warning" : undefined} />
            <Stat label="False-hit rate (labels)" value={pct(summary.label_false_hit_rate, 1)}
                  detail={summary.labeled ? `on the ${summary.labeled} judged replay hits with a known FAQ` : "no labeled hits judged yet"} />
            <Stat label="Judge agrees with labels" value={pct(summary.agreement)}
                  detail={summary.labeled ? `${summary.labeled} labeled hits` : "replay labeled traffic to measure"} />
            <Stat label="Last judged" value={ago(summary.last_ts)} detail={`${summary.judge_model}, judge prompt ${summary.judge_version}, cache prompt ${summary.prompt_version}`} />
          </div>

          <Card title="Judged hits" subtitle={`Most recent first. Source: ${summary.source}`}>
            <table className="table">
              <thead><tr><th>Question</th><th>Served answer for</th><th className="num">Similarity</th><th>Judge</th><th>Label</th></tr></thead>
              <tbody>
                {summary.rows.map((r, i) => (
                  <JudgedRow key={i} r={r} open={open === i} onToggle={() => setOpen(open === i ? null : i)} />
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}

function JudgedRow({ r, open, onToggle }: { r: JudgeRow; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="clickable" onClick={onToggle} aria-expanded={open}>
        <td>{r.question}</td>
        <td>{r.matched_question}</td>
        <td className="num">{r.similarity?.toFixed(3) ?? "—"}</td>
        <td>{r.verdict === "correct" ? <Badge tone="good">correct</Badge>
             : r.verdict === "incorrect" ? <Badge tone="critical">incorrect</Badge>
             : <Badge tone="warning">unparsed</Badge>}</td>
        <td>{r.label_correct === null ? <span className="muted">—</span>
             : r.label_correct ? <Badge tone="good">right FAQ</Badge> : <Badge tone="critical">wrong FAQ</Badge>}</td>
      </tr>
      {open && (
        <tr className="detail">
          <td colSpan={5}>
            <p><b>Judge:</b> {r.reason}</p>
            <div className="compare">
              <div><h4>Served from cache</h4><p>{r.cached_answer}</p></div>
              <div><h4>Fresh answer</h4><p>{r.fresh_answer}</p></div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
