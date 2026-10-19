import { useState } from "react";
import type { Config, Measured } from "../api";
import { LineChart } from "../components/LineChart";
import { Card, NumberField, Slider, Stat } from "../components/ui";
import type { Provenance } from "../components/ui";
import { ago, count, ms, pct, usd, usdPrecise } from "../format";
import { computeRoi, HOURS_PER_MONTH, indexGb, requiredCu } from "../roi";
import type { RoiInputs, SweepPoint } from "../roi";

type Props = { config: Config; measured: Measured; threshold: number; setThreshold: (t: number) => void };

const VOLUMES = [1e4, 3e4, 1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8];

function initialInputs(config: Config, m: Measured): RoiInputs {
  return {
    lakebaseAlwaysOn: true,
    volumePerMonth: 1_000_000,
    repeatShare: 0.5,
    threshold: config.threshold,
    priceInPerM: config.price_in_per_m,
    priceOutPerM: config.price_out_per_m,
    inputTokens: Math.round(m.llm.input_tokens ?? 100),
    outputTokens: Math.round(m.llm.output_tokens ?? 150),
    llmMs: Math.round(m.llm.llm_ms ?? 3500),
    embedMs: Math.round(m.overhead.embed_ms ?? 200),
    lookupMs: Math.round(m.overhead.lookup_ms ?? 10),
    writeMs: Math.round(m.llm.write_ms ?? 15),
    queryTokens: 20,
    embedPricePerM: 0.02,
    lakebaseCu: requiredCu(1_000_000),
    activeHours: HOURS_PER_MONTH,
    alwaysOnCuHourPrice: 0.069,
    cuHourPrice: 0.092,
    cacheEntries: 1_000_000,
    bytesPerEntry: 13_000,
    storagePerGbMonth: 0.545,
  };
}

export function RoiPage({ config, measured, threshold, setThreshold }: Props) {
  const [x, setX] = useState<RoiInputs>(() => initialInputs(config, measured));
  const set = (k: keyof RoiInputs) => (v: number | boolean) => setX((prev) => ({ ...prev, [k]: v }));
  // Compute follows the cache size until the user sets it.
  const [cuAuto, setCuAuto] = useState(true);
  const minCu = requiredCu(x.cacheEntries);
  const cu = cuAuto ? minCu : x.lakebaseCu;
  const sweep = measured.sweep.points as SweepPoint[];
  const r = computeRoi({ ...x, lakebaseCu: cu, threshold }, sweep);

  const llmProv = (v: number | null, what: string): Provenance =>
    v === null ? { kind: "assumption", text: "no misses logged yet" }
      : { kind: "measured", text: `${what}, ${measured.llm.n} ${config.llm_endpoint} misses` };
  const ohProv = (v: number | null): Provenance =>
    v === null ? { kind: "assumption", text: "no requests logged yet" }
      : { kind: "measured", text: `mean of ${measured.overhead.n} requests (${measured.backend})` };

  const saves = r.savingsMonthly > 0;
  const minT = sweep.length ? sweep[0].threshold : 0.5;
  const maxT = sweep.length ? sweep[sweep.length - 1].threshold : 0.95;
  const savingsSeries = VOLUMES.map((v) => ({ x: v, y: r.savingsAt(v) }));
  const ys = savingsSeries.map((p) => p.y);
  const yLo = Math.min(0, ...ys), yHi = Math.max(0, ...ys);
  const yStep = niceStep((yHi - yLo) / 4 || 1);

  return (
    <div className="roi">
      <aside className="inputs">
        <Card title="Your traffic">
          <NumberField label="Requests per month" value={x.volumePerMonth} onChange={set("volumePerMonth")} step={10000} min={0} prov={{ kind: "input" }} />
          <Slider label="Share of traffic that repeats a cached question" value={x.repeatShare} onChange={set("repeatShare")}
                  min={0} max={1} step={0.05} format={(v) => pct(v)} />
          <p className="hint">FAQ-style support traffic is highly repetitive; open-ended chat isn't. This is the biggest lever.</p>
        </Card>
        <Card title="Match threshold">
          <Slider label="Similarity threshold" value={threshold} onChange={setThreshold} min={minT} max={maxT} step={0.01}
                  format={(v) => v.toFixed(2)} />
          <p className="hint">Shared with the Playground. Measured at this threshold: the cache catches {pct(r.recall)} of
            repeat questions; {pct(r.repeatWrong, 1)} of repeat questions
            {r.hasNovel ? <> and {pct(r.novelHit, 1)} of questions it doesn't hold</> : null} get a wrong answer.</p>
        </Card>
        <Card title="LLM">
          <NumberField label="Input price" value={x.priceInPerM} onChange={set("priceInPerM")} suffix="$/1M tok"
                       prov={{ kind: "price", text: `${config.llm_endpoint} list; use your contract rate` }} />
          <NumberField label="Output price" value={x.priceOutPerM} onChange={set("priceOutPerM")} suffix="$/1M tok"
                       prov={{ kind: "price", text: `${config.llm_endpoint} list; use your contract rate` }} />
          <NumberField label="Input tokens per call" value={x.inputTokens} onChange={set("inputTokens")} prov={llmProv(measured.llm.input_tokens, "mean")} />
          <NumberField label="Output tokens per call" value={x.outputTokens} onChange={set("outputTokens")} prov={llmProv(measured.llm.output_tokens, "mean")} />
          <NumberField label="Latency per call" value={x.llmMs} onChange={set("llmMs")} suffix="ms" prov={llmProv(measured.llm.llm_ms, "mean")} />
        </Card>
        <Card title="Cache">
          <NumberField label="Embedding latency" value={x.embedMs} onChange={set("embedMs")} suffix="ms" prov={ohProv(measured.overhead.embed_ms)} />
          <NumberField label="Lookup latency" value={x.lookupMs} onChange={set("lookupMs")} suffix="ms" prov={ohProv(measured.overhead.lookup_ms)} />
          <NumberField label="Write latency (misses)" value={x.writeMs} onChange={set("writeMs")} suffix="ms" prov={llmProv(measured.llm.write_ms, "mean")} />
          <NumberField label="Embedding price" value={x.embedPricePerM} onChange={set("embedPricePerM")} suffix="$/1M tok"
                       prov={{ kind: "price", text: `${config.embedding_endpoint} list price` }} />
          <NumberField label="Tokens per question" value={x.queryTokens} onChange={set("queryTokens")}
                       prov={{ kind: "assumption", text: "typical short support question" }} />
        </Card>
        <Card title="Lakebase">
          <div className="segmented" role="radiogroup" aria-label="Compute billing">
            <button type="button" role="radio" aria-checked={x.lakebaseAlwaysOn} className={x.lakebaseAlwaysOn ? "active" : ""}
                    onClick={() => set("lakebaseAlwaysOn")(true)}>Always-on</button>
            <button type="button" role="radio" aria-checked={!x.lakebaseAlwaysOn} className={!x.lakebaseAlwaysOn ? "active" : ""}
                    onClick={() => set("lakebaseAlwaysOn")(false)}>Autoscaling</button>
          </div>
          <p className="hint">{x.lakebaseAlwaysOn
            ? "Billed every hour; never scales to zero. Cheaper when traffic runs all day."
            : "Billed only for active hours; scales to zero when idle. Pays off only if traffic stops for long stretches."}</p>
          <NumberField label="Compute units" value={cu} onChange={(v) => { setCuAuto(false); set("lakebaseCu")(v); }}
                       step={0.5} min={0.5}
                       prov={cuAuto ? { kind: "assumption", text: "sized to keep the index in memory" } : { kind: "input" }} />
          <p className="hint">
            At {count(x.cacheEntries)} entries the HNSW index is ≈{indexGb(x.cacheEntries).toFixed(1)} GB (8.2 KB per entry,
            measured in 03b). Keeping it in memory takes ≥{minCu} CU (~2 GB RAM per CU, half for the index).
            {!cuAuto && cu < minCu && <> <b>Below that, lookups read from storage and slow down.</b></>}
            {!cuAuto && <> <button type="button" className="link" onClick={() => setCuAuto(true)}>Size to the cache</button></>}
          </p>
          {x.lakebaseAlwaysOn
            ? <NumberField label="Always-on price" value={x.alwaysOnCuHourPrice} onChange={set("alwaysOnCuHourPrice")} step={0.001}
                           suffix="$/CU-hour" prov={{ kind: "price", text: "Lakebase always-on, list" }} />
            : <>
                <NumberField label="Active hours per month" value={x.activeHours} onChange={set("activeHours")} step={10} min={0}
                             max={HOURS_PER_MONTH} prov={{ kind: "input" }} />
                <NumberField label="Autoscaling price" value={x.cuHourPrice} onChange={set("cuHourPrice")} step={0.001}
                             suffix="$/CU-hour" prov={{ kind: "price", text: "Lakebase autoscaling, list" }} />
              </>}
          <NumberField label="Cache entries" value={x.cacheEntries} onChange={set("cacheEntries")} step={10000} min={0}
                       prov={{ kind: "assumption", text: "about a month of misses (30-day TTL)" }} />
          <NumberField label="Storage per entry" value={x.bytesPerEntry} onChange={set("bytesPerEntry")} step={1000}
                       suffix="bytes" prov={{ kind: "assumption", text: "8.2 KB index (03b) + ~4.7 KB row (vector + text)" }} />
          <NumberField label="Storage price" value={x.storagePerGbMonth} onChange={set("storagePerGbMonth")} step={0.005}
                       suffix="$/GB-month" prov={{ kind: "price", text: "storage $0.345 + PITR $0.200, list" }} />
        </Card>
      </aside>

      <div className="results">
        <div className={`verdict ${saves ? "verdict-good" : "verdict-critical"}`} role="status">
          <span className="verdict-icon" aria-hidden="true">{saves ? "✓" : "✕"}</span>
          <div>
            <div className="verdict-title">
              {saves
                ? <>Yes: the cache saves {usd(r.savingsMonthly)} a month ({pct(r.savingsPct)} of LLM spend)</>
                : <>Not at this volume: the cache costs {usd(-r.savingsMonthly)} a month more than it saves</>}
            </div>
            <div className="verdict-detail">
              {isFinite(r.breakEvenVolume)
                ? <>Breaks even at {count(r.breakEvenVolume)} requests/month at a {pct(r.hitRate)} hit rate
                    {r.breakEvenHitRate < 1 && <>; at {count(x.volumePerMonth)} requests/month it needs a {pct(r.breakEvenHitRate, 1)} hit rate</>}.</>
                : <>A hit doesn't save more than the embedding call costs, so no volume breaks even.</>}
            </div>
          </div>
        </div>

        <div className="stats">
          <Stat label="LLM spend per month" value={<>{usd(r.cachedMonthly)} <span className="was">vs {usd(r.baselineMonthly)}</span></>}
                detail="with cache vs. without; includes embeddings + Lakebase" />
          <Stat label="Hit rate" value={pct(r.hitRate)}
                detail={<>{pct(x.repeatShare)} repeat traffic × {pct(r.recall)} caught
                  {r.hasNovel && r.novelHit > 0 ? <>, plus {pct((1 - x.repeatShare) * r.novelHit, 1)} wrong hits on the rest</> : null}</>} />
          <Stat label="Average latency" value={<>{ms(r.avgMs)} <span className="was">vs {ms(r.baselineMs)}</span></>}
                detail={<>hits {ms(r.hitMs)} · misses {ms(r.missMs)} (+{ms(r.missPenaltyMs)})</>}
                tone={r.avgMs < r.baselineMs ? "good" : "critical"} />
          <Stat label="Wrong answers served" value={`${count(r.falseHitsPerMonth)} / month`}
                detail={r.falseHitsPerMonth <= 0 ? "none measured at this threshold"
                  : r.hasNovel ? <>1 in {count(1 / r.wrongRate)} requests: {count(r.repeatWrongPerMonth)} on repeat questions,
                                   {" "}{count(r.novelWrongPerMonth)} on questions the cache doesn't hold</>
                  : <>1 in {count(1 / r.wrongRate)} requests, repeat questions only (rerun 02_evaluate to include the rest)</>}
                tone={r.wrongRate > 0.01 ? "warning" : undefined} />
        </div>

        <Card title={r.hasNovel
                ? `At ${threshold.toFixed(2)}, the cache catches ${pct(r.recall)} of repeat questions; ${pct(r.novelHit, 1)} of questions it doesn't hold get a wrong answer`
                : `At ${threshold.toFixed(2)}, the cache catches ${pct(r.recall)} of repeat questions; ${pct(r.repeatWrong, 1)} get a wrong answer`}
              subtitle={<>Measured by 02_evaluate: held-out paraphrases looked up against the seeded FAQs; "not cached" looks each up
                with its own FAQ removed (plus account-specific probes). Each line is a share of its own query set, so all three
                only fall as the threshold rises. Click the chart to set the threshold.</>}>
          {sweep.length ? (
            <LineChart
              ariaLabel="Share of questions caught and answered wrongly, by similarity threshold"
              series={[
                { name: "Repeat questions caught", color: "var(--series-1)", points: sweep.map((p) => ({ x: p.threshold, y: p.cacheable_hit_rate })) },
                ...(r.hasNovel ? [{ name: "Wrong: not cached", color: "var(--series-2)",
                                    points: sweep.map((p) => ({ x: p.threshold, y: p.novel_hit_rate })) }] : []),
                { name: "Wrong: repeat questions", color: "var(--series-3)",
                  points: sweep.map((p) => ({ x: p.threshold, y: r.hasNovel ? p.cacheable_false_hit_rate
                                                                             : p.cacheable_hit_rate * (1 - (p.precision ?? 1)) })) },
              ]}
              xDomain={[minT, maxT]} yDomain={[0, 1]}
              xTicks={sweep.map((p) => p.threshold).filter((_, i) => i % 2 === 0)} yTicks={[0, 0.25, 0.5, 0.75, 1]}
              xFormat={(v) => v.toFixed(2)} yFormat={(v) => pct(v)}
              marker={{ x: threshold, label: `threshold ${threshold.toFixed(2)}` }}
              onPick={setThreshold}
            />
          ) : <p className="muted">No threshold sweep yet: run 02_evaluate.</p>}
          <p className="source">Source: {measured.sweep.source}, run {measured.sweep.run_id?.slice(0, 8) ?? "—"}</p>
        </Card>

        <Card title={saves ? `Net savings grow with volume: ${usd(r.savingsAt(x.volumePerMonth))}/month at ${count(x.volumePerMonth)} requests`
                           : `Below ${isFinite(r.breakEvenVolume) ? count(r.breakEvenVolume) : "any"} requests/month, Lakebase costs more than the cache saves`}
              subtitle={`Net monthly savings by request volume, at a ${pct(r.hitRate)} hit rate`}>
          <LineChart
            ariaLabel="Net monthly savings by request volume"
            series={[{ name: "Net savings", color: "var(--series-1)", points: savingsSeries }]}
            xLog xDomain={[VOLUMES[0], VOLUMES[VOLUMES.length - 1]]}
            yDomain={[Math.floor(yLo / yStep) * yStep, Math.ceil(yHi / yStep) * yStep]}
            xTicks={[1e4, 1e5, 1e6, 1e7, 1e8]} yTicks={ticks(Math.floor(yLo / yStep) * yStep, Math.ceil(yHi / yStep) * yStep, yStep)}
            xFormat={(v) => count(v)} yFormat={(v) => usd(v)} zeroLine
            marker={{ x: Math.min(Math.max(x.volumePerMonth, VOLUMES[0]), VOLUMES[VOLUMES.length - 1]), label: "your volume" }}
          />
        </Card>

        <Card title="Monthly cost breakdown">
          <table className="table">
            <thead><tr><th></th><th className="num">Without cache</th><th className="num">With cache</th></tr></thead>
            <tbody>
              <tr><td>LLM calls ({usdPrecise(r.llmCostPerCall)} each)</td><td className="num">{usd(r.baselineMonthly)}</td>
                  <td className="num">{usd(r.baselineMonthly * (1 - r.hitRate))}</td></tr>
              <tr><td>Embedding calls ({usdPrecise(r.embedCostPerCall)} each)</td><td className="num">—</td>
                  <td className="num">{usd(r.embedCostPerCall * x.volumePerMonth, 2)}</td></tr>
              <tr><td>Lakebase compute ({x.lakebaseCu} CU, {x.lakebaseAlwaysOn ? "always-on" : `autoscaling, ${Math.round(Math.min(x.activeHours, HOURS_PER_MONTH))} h`})</td>
                  <td className="num">—</td><td className="num">{usd(r.computeMonthly)}</td></tr>
              <tr><td>Lakebase storage ({count(x.cacheEntries)} entries, {((x.cacheEntries * x.bytesPerEntry) / 1e9).toFixed(2)} GB)</td>
                  <td className="num">—</td><td className="num">{usd(r.storageMonthly, 2)}</td></tr>
              <tr className="total"><td>Total</td><td className="num">{usd(r.baselineMonthly)}</td><td className="num">{usd(r.cachedMonthly)}</td></tr>
            </tbody>
          </table>
          <p className="source">
            LLM and latency figures: {measured.llm.source}, last miss {ago(measured.llm.last_ts)}. Excludes the app or gateway
            hosting the cache, and on-demand Lakebase snapshots ($0.090/GB-month).
          </p>
        </Card>
      </div>
    </div>
  );
}

function niceStep(raw: number) {
  const p = 10 ** Math.floor(Math.log10(Math.abs(raw)));
  const f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
}

function ticks(lo: number, hi: number, step: number) {
  const out: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) out.push(Math.round(v / step) * step);
  return out;
}
