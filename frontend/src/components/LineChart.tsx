import { useEffect, useRef, useState } from "react";

// Small SVG line chart: one y-axis, 2px lines, recessive grid, crosshair + tooltip on hover,
// direct labels at line ends, an optional vertical marker for the current setting.

export type Series = { name: string; color: string; points: { x: number; y: number | null }[] };

type Props = {
  series: Series[];
  xDomain: [number, number];
  yDomain: [number, number];
  xTicks: number[];
  yTicks: number[];
  xFormat: (v: number) => string;
  yFormat: (v: number) => string;
  xLog?: boolean;
  height?: number;
  marker?: { x: number; label: string };
  zeroLine?: boolean;
  onPick?: (x: number) => void;
  ariaLabel: string;
};

const M = { top: 16, right: 112, bottom: 34, left: 56 };

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function LineChart(p: Props) {
  const [ref, width] = useWidth();
  const height = p.height ?? 260;
  const iw = width - M.left - M.right, ih = height - M.top - M.bottom;
  const [hover, setHover] = useState<number | null>(null);

  const tx = (v: number) => (p.xLog ? Math.log10(v) : v);
  const [x0, x1] = [tx(p.xDomain[0]), tx(p.xDomain[1])];
  const sx = (v: number) => ((tx(v) - x0) / (x1 - x0)) * iw;
  const sy = (v: number) => ih - ((v - p.yDomain[0]) / (p.yDomain[1] - p.yDomain[0])) * ih;
  const invX = (px: number) => {
    const t = x0 + (px / iw) * (x1 - x0);
    return p.xLog ? 10 ** t : t;
  };

  const xs = Array.from(new Set(p.series.flatMap((s) => s.points.map((pt) => pt.x)))).sort((a, b) => a - b);
  const nearest = (x: number) => xs.reduce((best, v) => (Math.abs(tx(v) - tx(x)) < Math.abs(tx(best) - tx(x)) ? v : best), xs[0]);

  const path = (s: Series) => {
    let d = "", pen = false;
    for (const pt of s.points) {
      if (pt.y === null) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${sx(pt.x).toFixed(1)},${sy(Math.max(p.yDomain[0], Math.min(p.yDomain[1], pt.y))).toFixed(1)}`;
      pen = true;
    }
    return d;
  };

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    setHover(nearest(invX(e.clientX - r.left)));
  };

  // Direct labels at each line's last point, nudged apart so they don't collide.
  const ends = p.series
    .map((s) => {
      const last = [...s.points].reverse().find((pt) => pt.y !== null);
      return last ? { name: s.name, y: sy(last.y as number) } : null;
    })
    .filter(Boolean) as { name: string; y: number }[];
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;

  const tip = hover === null ? null : {
    x: hover,
    rows: p.series.map((s) => ({ s, y: s.points.find((pt) => pt.x === hover)?.y ?? null })),
  };
  const tipLeft = tip ? Math.min(M.left + sx(tip.x) + 12, width - 190) : 0;

  return (
    <div ref={ref} className="chart">
      {p.series.length > 1 && (
        <div className="legend" aria-hidden="true">
          {p.series.map((s) => (
            <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>
          ))}
        </div>
      )}
      <svg width={width} height={height} role="img" aria-label={p.ariaLabel}>
        <g transform={`translate(${M.left},${M.top})`}>
          {p.yTicks.map((t) => (
            <g key={`y${t}`}>
              <line className="grid" x1={0} x2={iw} y1={sy(t)} y2={sy(t)} />
              <text className="tick" x={-8} y={sy(t)} dy="0.32em" textAnchor="end">{p.yFormat(t)}</text>
            </g>
          ))}
          {p.xTicks.map((t) => (
            <text key={`x${t}`} className="tick" x={sx(t)} y={ih + 20} textAnchor="middle">{p.xFormat(t)}</text>
          ))}
          <line className="axis" x1={0} x2={iw} y1={ih} y2={ih} />
          {p.zeroLine && p.yDomain[0] < 0 && <line className="zero" x1={0} x2={iw} y1={sy(0)} y2={sy(0)} />}
          {p.marker && (
            <g>
              <line className="marker" x1={sx(p.marker.x)} x2={sx(p.marker.x)} y1={0} y2={ih} />
              <text className="marker-label" x={sx(p.marker.x) + 6} y={10}>{p.marker.label}</text>
            </g>
          )}
          {p.series.map((s) => (
            <path key={s.name} d={path(s)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" />
          ))}
          {ends.map((e) => {
            const s = p.series.find((x) => x.name === e.name)!;
            return <text key={e.name} className="direct-label" x={iw + 8} y={e.y} dy="0.32em" fill="currentColor">
              <tspan fill={s.color}>■ </tspan>{e.name}</text>;
          })}
          {tip && (
            <g pointerEvents="none">
              <line className="crosshair" x1={sx(tip.x)} x2={sx(tip.x)} y1={0} y2={ih} />
              {tip.rows.map(({ s, y }) => y !== null && (
                <circle key={s.name} cx={sx(tip.x)} cy={sy(y)} r={4.5} fill={s.color} className="dot" />
              ))}
            </g>
          )}
          <rect width={iw} height={ih} fill="transparent" style={{ cursor: p.onPick ? "pointer" : "crosshair" }}
                onMouseMove={onMove} onMouseLeave={() => setHover(null)}
                onClick={(e) => {
                  if (!p.onPick) return;
                  const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
                  p.onPick(nearest(invX(e.clientX - r.left)));
                }} />
        </g>
      </svg>
      {tip && (
        <div className="tooltip" style={{ left: tipLeft, top: M.top }}>
          <div className="tooltip-title">{p.xFormat(tip.x)}</div>
          {tip.rows.map(({ s, y }) => (
            <div key={s.name} className="tooltip-row">
              <i style={{ background: s.color }} /><span>{s.name}</span><b>{y === null ? "—" : p.yFormat(y)}</b>
            </div>
          ))}
          {p.onPick && <div className="tooltip-hint">Click to use this value</div>}
        </div>
      )}
    </div>
  );
}
