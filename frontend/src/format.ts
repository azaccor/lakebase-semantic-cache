export const usd = (v: number, digits = 0) => {
  const sign = v < 0 ? "−" : "";
  const a = Math.abs(v);
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(a >= 1e7 ? 1 : 2)}M`;
  if (a >= 1e4) return `${sign}$${(a / 1e3).toFixed(1)}K`;
  return `${sign}$${a.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
};

export const usdPrecise = (v: number) => (v >= 0.01 ? `$${v.toFixed(4)}` : `$${v.toPrecision(2)}`);

export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || !isFinite(v) ? "—" : `${(v * 100).toFixed(digits)}%`;

export const ms = (v: number | null | undefined) => {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${Math.round(v)} ms`;
};

export const count = (v: number) => {
  if (!isFinite(v)) return "—";
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(v >= 1e4 ? 0 : 1)}K`;
  return `${Math.round(v)}`;
};

export const ago = (iso: string | null) => {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
};
