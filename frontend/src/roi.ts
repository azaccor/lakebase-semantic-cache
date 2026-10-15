// ROI model for a semantic cache in front of an LLM endpoint. Pure functions, so the page
// recomputes on every input change.
//
// Baseline: every request calls the LLM. With the cache, every request pays one embedding call and
// a lookup; misses also pay the LLM call and a cache write. The cache's Lakebase compute and storage
// are a fixed monthly cost. Compute is billed one of two ways: always-on (every hour, never scales to
// zero, lower rate) or autoscaling (only active hours, scales to zero, higher rate).
// Traffic is split into repeat questions (their answer is cached) and the rest. From 02_evaluate's sweep:
// a repeat question hits with cacheable_hit_rate, and gets a wrong answer with cacheable_false_hit_rate;
// a question whose answer isn't cached still hits, always wrongly, with novel_hit_rate (leave-one-FAQ-out).
// All three are shares of a fixed set of queries, so they only fall as the threshold rises.

export type SweepPoint = {
  threshold: number;
  hit_rate: number;
  cacheable_hit_rate: number;
  precision: number | null;
  false_hit_rate: number;
  cacheable_false_hit_rate: number | null;
  novel_hit_rate: number | null;
};

export type RoiInputs = {
  lakebaseAlwaysOn: boolean;
  volumePerMonth: number;
  repeatShare: number; // 0..1
  threshold: number;
  priceInPerM: number;
  priceOutPerM: number;
  inputTokens: number;
  outputTokens: number;
  llmMs: number;
  embedMs: number;
  lookupMs: number;
  writeMs: number;
  queryTokens: number;
  embedPricePerM: number;
  lakebaseCu: number;          // average compute units while running
  activeHours: number;         // autoscaling only: hours per month with traffic
  alwaysOnCuHourPrice: number;
  cuHourPrice: number;         // autoscaling
  cacheEntries: number;
  bytesPerEntry: number;       // vector + text + index
  storagePerGbMonth: number;   // storage + point-in-time restore
};

export const HOURS_PER_MONTH = 730;

/** Linear interpolation over the sweep; clamps outside the measured range. */
type RateKey = "cacheable_hit_rate" | "precision" | "cacheable_false_hit_rate" | "novel_hit_rate";

export function interpolate(points: SweepPoint[], t: number, key: RateKey): number | null {
  const pts = points.filter((p) => p[key] !== null).sort((a, b) => a.threshold - b.threshold);
  if (!pts.length) return null;
  if (t <= pts[0].threshold) return pts[0][key] as number;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i];
    if (t <= b.threshold) {
      const f = (t - a.threshold) / (b.threshold - a.threshold);
      return (a[key] as number) + f * ((b[key] as number) - (a[key] as number));
    }
  }
  return pts[pts.length - 1][key] as number;
}

export function computeRoi(x: RoiInputs, sweep: SweepPoint[]) {
  const recall = interpolate(sweep, x.threshold, "cacheable_hit_rate") ?? 0;
  // Sweeps from before 02_evaluate measured these: repeat wrong-hits from precision; non-repeat unknown.
  const hasNovel = sweep.some((p) => p.novel_hit_rate !== null && p.novel_hit_rate !== undefined);
  const repeatWrong = hasNovel
    ? interpolate(sweep, x.threshold, "cacheable_false_hit_rate") ?? 0
    : recall * (1 - (interpolate(sweep, x.threshold, "precision") ?? 1));
  const novelHit = hasNovel ? interpolate(sweep, x.threshold, "novel_hit_rate") ?? 0 : 0;
  const hitRate = x.repeatShare * recall + (1 - x.repeatShare) * novelHit;
  const wrongRate = x.repeatShare * repeatWrong + (1 - x.repeatShare) * novelHit;   // per request
  const precision = hitRate > 0 ? 1 - wrongRate / hitRate : 1;

  const llmCostPerCall = (x.inputTokens * x.priceInPerM + x.outputTokens * x.priceOutPerM) / 1e6;
  const embedCostPerCall = (x.queryTokens * x.embedPricePerM) / 1e6;
  const computeMonthly = x.lakebaseAlwaysOn
    ? x.lakebaseCu * x.alwaysOnCuHourPrice * HOURS_PER_MONTH
    : x.lakebaseCu * x.cuHourPrice * Math.min(x.activeHours, HOURS_PER_MONTH);
  const storageMonthly = ((x.cacheEntries * x.bytesPerEntry) / 1e9) * x.storagePerGbMonth;
  const lakebaseMonthly = computeMonthly + storageMonthly;

  const monthly = (volume: number, h: number) => {
    const baseline = volume * llmCostPerCall;
    const cached = volume * embedCostPerCall + volume * (1 - h) * llmCostPerCall + lakebaseMonthly;
    return { baseline, cached, savings: baseline - cached };
  };
  const m = monthly(x.volumePerMonth, hitRate);

  const variableBreakEven = x.volumePerMonth * llmCostPerCall;
  const breakEvenHitRate = variableBreakEven > 0
    ? (x.volumePerMonth * embedCostPerCall + lakebaseMonthly) / variableBreakEven
    : Infinity;
  const perRequestSaving = hitRate * llmCostPerCall - embedCostPerCall;
  const breakEvenVolume = perRequestSaving > 0 ? lakebaseMonthly / perRequestSaving : Infinity;

  const overheadMs = x.embedMs + x.lookupMs;
  const missMs = overheadMs + x.llmMs + x.writeMs;
  const avgMs = overheadMs + (1 - hitRate) * (x.llmMs + x.writeMs);

  return {
    recall, precision, hitRate, repeatWrong, novelHit, hasNovel, wrongRate,
    llmCostPerCall, embedCostPerCall, lakebaseMonthly, computeMonthly, storageMonthly,
    baselineMonthly: m.baseline, cachedMonthly: m.cached, savingsMonthly: m.savings,
    savingsPct: m.baseline > 0 ? m.savings / m.baseline : 0,
    breakEvenHitRate, breakEvenVolume,
    falseHitsPerMonth: x.volumePerMonth * wrongRate,
    repeatWrongPerMonth: x.volumePerMonth * x.repeatShare * repeatWrong,
    novelWrongPerMonth: x.volumePerMonth * (1 - x.repeatShare) * novelHit,
    hitMs: overheadMs, missMs, avgMs, baselineMs: x.llmMs,
    missPenaltyMs: missMs - x.llmMs,
    savingsAt: (volume: number) => monthly(volume, hitRate).savings,
  };
}

export type Roi = ReturnType<typeof computeRoi>;
